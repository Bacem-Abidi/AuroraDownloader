import os
import re
import time
import uuid
import glob
import json
import base64
import posixpath
from pathlib import Path
import fail
from flask_sse import sse
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from datetime import datetime
from ytmusicapi import YTMusic
from mutagen.id3 import ID3, APIC
from history import HistoryLogger
from flask_bootstrap import Bootstrap5
from mutagen import File as MutagenFile
from downloader import download_manager
from flask import Flask, render_template, request, jsonify, Response
from difflib import SequenceMatcher


CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
PREFS_FILE = os.path.join(CONFIG_DIR, "preferences.json")
AUDIO_EXTENSIONS = (".mp3", ".flac", ".wav", ".ogg", ".m4a")
LIBRARY_CACHE = {}

# progress_tracker = ProgressTracker(CONFIG_DIR)
app = Flask(__name__)
app.config["REDIS_URL"] = "redis://localhost"  # For production, use a real Redis server
app.register_blueprint(sse, url_prefix="/stream")
Bootstrap5(app)


# Expand paths and convert to absolute paths
def expand_path(path):
    # Handle ~ and relative paths
    expanded = os.path.expanduser(path)
    # Convert to absolute path
    return os.path.abspath(expanded)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/preferences", methods=["GET"])
def get_preferences():
    try:
        if os.path.exists(PREFS_FILE):
            with open(PREFS_FILE, "r") as f:
                return jsonify(json.load(f))
        else:
            # Return default config structure
            return jsonify(
                {
                    "audioQuality": "best",
                    "audioCodec": "mp3",
                    "audioDir": "~/Music",
                    "lyricsDir": "~/Music/lyrics",
                    "playlistDir": "~/.config/mpd/playlists",
                    "updateMpd": True,
                    "mpcPath": "mpc",
                    "mpcCommand": "update",
                    "matchThreshold": "85",
                    "fallback": "skip",
                }
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/preferences", methods=["POST"])
def save_preferences():
    try:
        prefs = request.json

        # Validate required fields
        required = ["audioQuality", "audioCodec", "audioDir", "updateMpd"]
        if not all(field in prefs for field in required):
            return jsonify({"error": "Missing required fields"}), 400

        # Save to file
        with open(PREFS_FILE, "w") as f:
            json.dump(prefs, f, indent=2)

        return jsonify({"message": "Preferences saved successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/start_download", methods=["POST"])
def start_download():
    data = request.get_json()
    url = data.get("url")
    quality = data.get("quality", "best")
    codec = data.get("codec", "mp3")
    audio_dir = data.get("audio_dir", "Downloads")
    lyrics_dir = data.get("lyrics_dir", "Lyrics")
    playlist_dir = data.get("playlist_dir", "Playlists")
    playlist_options = data.get("playlist_options", {})
    mpd_options = data.get("mpd_options", {})
    overwrite = data.get("overwrite", False)
    resume = data.get("resume", False)

    audio_dir = expand_path(audio_dir)
    lyrics_dir = expand_path(lyrics_dir)
    playlist_dir = expand_path(playlist_dir)

    # Create directories if they don't exist
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(lyrics_dir, exist_ok=True)

    # Create history directory
    history_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history")
    os.makedirs(history_dir, exist_ok=True)

    fail_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fail")
    os.makedirs(fail_dir, exist_ok=True)

    if not url:
        return jsonify({"error": "URL is required"}), 400

    # Generate a unique ID for this download
    download_id = str(uuid.uuid4())

    # Start the download in a background thread
    download_manager.start_download(
        url,
        download_id,
        quality=quality,
        codec=codec,
        audio_dir=audio_dir,
        lyrics_dir=lyrics_dir,
        playlist_dir=playlist_dir,
        playlist_options=playlist_options,
        mpd_options=mpd_options,
        history_dir=history_dir,
        fail_dir=fail_dir,
        overwrite=overwrite,
        resume=resume,
        config_dir=CONFIG_DIR,
    )

    return jsonify(
        {
            "download_id": download_id,
            "message": "Download started",
            "audio_dir": audio_dir,
            "lyrics_dir": lyrics_dir,
            "playlist_dir": playlist_dir,
        }
    )


@app.route("/failed/retry", methods=["POST"])
def retry_failed():
    data = request.get_json()
    entry = data.get("entry")
    audio_dir = data.get("audio_dir", "Downloads")
    lyrics_dir = data.get("lyrics_dir", "Downloads/lyrics")
    playlist_dir = data.get("playlist_dir", "Downloads/playlists")

    audio_dir = expand_path(audio_dir)
    lyrics_dir = expand_path(lyrics_dir)
    playlist_dir = expand_path(playlist_dir)

    if not entry or "url" not in entry:
        return jsonify({"error": "Invalid failed entry"}), 400

    download_id = f"retry-{int(time.time() * 1000)}"

    fail_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fail")

    try:
        download_manager.retry_failed_entry(
            failed_entry=entry,
            download_id=download_id,
            audio_dir=audio_dir,
            lyrics_dir=lyrics_dir,
            playlist_dir=playlist_dir,
            fail_dir=fail_dir,
            overwrite=False,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"status": "started", "download_id": download_id})


@app.route("/migrate/start", methods=["POST"])
def start_migration():
    data = request.get_json()
    audio_dir = data.get("audio_dir", "Downloads")
    lyrics_dir = data.get("lyrics_dir", "Downloads/lyrics")
    playlist_dir = data.get("playlist_dir", "Downloads/playlists")
    match_perc = data.get("match_perc", "85")
    fallback = data.get("fallback", "manual")

    audio_dir = expand_path(audio_dir)
    lyrics_dir = expand_path(lyrics_dir)
    playlist_dir = expand_path(playlist_dir)

    os.makedirs(audio_dir, exist_ok=True)

    migrate_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migration")
    os.makedirs(migrate_dir, exist_ok=True)

    migration_id = str(uuid.uuid4())

    download_manager.start_migration(
        migration_id,
        audio_dir,
        lyrics_dir,
        playlist_dir,
        match_perc,
        fallback,
        migrate_dir,
    )

    return jsonify({"migration_id": migration_id})


@app.route("/migrate/choice", methods=["POST"])
def migrate_choice():
    data = request.get_json()
    migration_id = data["migration_id"]
    video_id = data.get("video_id")  # None = skip
    action = data["action"]

    mgr = download_manager

    if migration_id not in mgr.migration_choices:
        return jsonify({"error": "No pending choice"}), 400

    mgr.migration_choices[migration_id]["action"] = action
    mgr.migration_choices[migration_id]["video_id"] = video_id
    mgr.migration_choices[migration_id]["event"].set()

    return jsonify({"status": "ok"})


@app.route("/logs/<download_id>")
def stream_logs(download_id):
    def generate():
        # Get the log generator
        log_generator = download_manager.get_logs(download_id)

        # Stream logs as they come in
        for log in log_generator:
            # Format as SSE message
            yield f"data: {log}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/history_files")
def history_files():
    history_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history")
    files = [
        os.path.basename(f)
        for f in glob.glob(os.path.join(history_dir, "history_*.json"))
    ]
    return jsonify(sorted(files, reverse=True))


@app.route("/history")
def history_data():
    week = request.args.get("week", "current")
    history_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history")

    if week == "current":
        logger = HistoryLogger(history_dir)
        file_path = logger.get_week_file()
    else:
        file_path = os.path.join(history_dir, week)

    if not os.path.exists(file_path):
        return jsonify([])

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            history = json.load(f)

        # Improved sorting with proper datetime conversion
        sorted_history = sorted(
            history, key=lambda x: datetime.fromisoformat(x["timestamp"]), reverse=True
        )

        return jsonify(sorted_history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def format_duration(seconds):
    if not seconds:
        return None
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def get_audio_metadata(path):
    try:
        audio = MutagenFile(path, easy=True)
        if not audio:
            raise Exception("Unsupported format")

        duration = None
        try:
            duration = int(audio.info.length)
        except Exception:
            pass

        def tag(name):
            return audio.get(name, [None])[0]

        has_artwork = False

        # MP3 (ID3)
        if path.lower().endswith(".mp3"):
            try:
                id3 = ID3(path)
                has_artwork = bool(id3.getall("APIC"))
            except Exception:
                pass

        # MP4 / M4A
        elif isinstance(audio, MP4):
            has_artwork = "covr" in audio.tags

        # FLAC
        elif isinstance(audio, FLAC):
            has_artwork = bool(audio.pictures)

        return {
            "title": tag("title") or os.path.splitext(os.path.basename(path))[0],
            "artist": tag("artist") or "Unknown Artist",
            "album": tag("album") or "Unknown Album",
            "track": tag("tracknumber"),
            "year": tag("date") or tag("year"),
            "format": os.path.splitext(path)[1][1:],
            "duration": format_duration(duration),
            "hasArtwork": has_artwork,
        }

    except Exception:
        return {
            "title": os.path.splitext(os.path.basename(path))[0],
            "artist": "Unknown Artist",
            "album": "Unknown Album",
            "format": os.path.splitext(path)[1][1:],
            "duration": "00:00",
            "hasArtwork": False,
        }


@app.route("/artwork")
def artwork():
    path = request.args.get("path")
    if not path or not os.path.isfile(path):
        return "", 404

    audio = MutagenFile(path)

    image = None
    mime = "image/jpeg"

    # MP3
    if audio and audio.tags and hasattr(audio.tags, "getall"):
        apic = audio.tags.getall("APIC")
        if apic:
            image = apic[0].data
            mime = apic[0].mime

    # MP4 / M4A
    if isinstance(audio, MP4) and "covr" in audio.tags:
        image = audio.tags["covr"][0]
        mime = "image/png" if image.imageformat == image.FORMAT_PNG else "image/jpeg"

    if not image:
        return "", 404

    return Response(image, mimetype=mime)


@app.route("/playlists", methods=["GET"])
def list_playlists():
    playlist_dir = request.args.get("dir")
    playlist_dir = os.path.expanduser(os.path.expandvars(playlist_dir))

    if not os.path.isdir(playlist_dir):
        return jsonify([])

    playlists = []

    for f in os.listdir(playlist_dir):
        if f.lower().endswith((".m3u", ".m3u8", ".pls")):
            playlists.append({"name": f})

    return jsonify(playlists)


def resolve_playlist_entry(entry, playlist_dir, audio_dir):
    entry = entry.strip()

    if not entry or entry.startswith("#"):
        return None

    # Expand env & user
    entry = os.path.expanduser(os.path.expandvars(entry))

    # 1. Absolute path
    if os.path.isabs(entry):
        return entry if os.path.isfile(entry) else None

    # 2. Relative to playlist file
    rel_to_playlist = os.path.join(playlist_dir, entry)
    if os.path.isfile(rel_to_playlist):
        return rel_to_playlist

    # 3. Filename only → relative to audio dir (recursive search)
    for root, _, files in os.walk(audio_dir):
        if os.path.basename(entry) in files:
            return os.path.join(root, os.path.basename(entry))

    return None


@app.route("/playlist/<name>", methods=["GET"])
def load_playlist(name):
    try:
        audio_dir = request.args.get("audioDir")
        playlist_dir = request.args.get("playlistDir")
        offset = int(request.args.get("offset", 0))
        limit = int(request.args.get("limit", 30))

        playlist_dir = os.path.expanduser(os.path.expandvars(playlist_dir))
        audio_dir = os.path.expanduser(os.path.expandvars(audio_dir))

        playlist_path = os.path.join(playlist_dir, name)
        if not os.path.isfile(playlist_path):
            return jsonify({"error": "Playlist not found"}), 404

        playlist_base_dir = os.path.dirname(playlist_path)
        resolved_paths = []

        # Resolve all entries first
        with open(playlist_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                resolved = resolve_playlist_entry(line, playlist_base_dir, audio_dir)
                if resolved:
                    resolved_paths.append(resolved)

        total = len(resolved_paths)
        slice_paths = resolved_paths[offset : offset + limit]

        items = []
        for path in slice_paths:
            meta = get_audio_metadata(path)
            items.append(
                {
                    **meta,
                    "filename": os.path.basename(path),
                    "path": path,
                    "type": "playlist",
                }
            )

        return jsonify(
            {
                "name": name,
                "items": items,
                "offset": offset,
                "limit": limit,
                "total": total,
                "hasMore": offset + limit < total,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/library", methods=["GET"])
def library():
    try:
        audio_dir = request.args.get("dir")
        offset = int(request.args.get("offset", 0))
        limit = int(request.args.get("limit", 30))
        reset = request.args.get("reset", "false").lower() == "true"

        if not audio_dir:
            return jsonify({"error": "Missing audio directory"}), 400

        audio_dir = os.path.expanduser(os.path.expandvars(audio_dir))

        if not os.path.isdir(audio_dir):
            return jsonify({"error": "Invalid audio directory"}), 400

        # Clear cache if reset requested
        if reset and audio_dir in LIBRARY_CACHE:
            del LIBRARY_CACHE[audio_dir]

        # Scan once and cache
        if audio_dir not in LIBRARY_CACHE:
            files = []
            for root, _, filenames in os.walk(audio_dir):
                for f in filenames:
                    if f.lower().endswith(AUDIO_EXTENSIONS):
                        files.append(os.path.join(root, f))

            files.sort(key=lambda p: os.path.basename(p).lower())
            LIBRARY_CACHE[audio_dir] = files

        all_files = LIBRARY_CACHE[audio_dir]
        slice_files = all_files[offset : offset + limit]

        items = []
        for path in slice_files:
            meta = get_audio_metadata(path)
            items.append(
                {
                    **meta,
                    "filename": os.path.basename(path),
                    "path": path,
                    "quality": "—",
                    "type": "local",
                }
            )

        return jsonify(
            {
                "items": items,
                "offset": offset,
                "limit": limit,
                "total": len(all_files),
                "hasMore": offset + limit < len(all_files),
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/failed", methods=["GET"])
def failed_library():
    try:
        offset = int(request.args.get("offset", 0))
        limit = int(request.args.get("limit", 30))

        fail_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fail")
        if not os.path.isdir(fail_dir):
            return jsonify({"items": [], "total": 0, "hasMore": False})

        entries = []

        # Load all weekly fail files
        for filename in sorted(os.listdir(fail_dir)):
            if not filename.startswith("fail_") or not filename.endswith(".json"):
                continue

            file_path = os.path.join(fail_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        entries.extend(data)
            except Exception:
                continue

        total = len(entries)
        slice_entries = entries[offset : offset + limit]

        # Normalize to library-like items
        items = []
        for entry in slice_entries:
            items.append(
                {
                    "id": entry.get("url", "").split("v=")[-1],
                    "url": entry.get("url", ""),
                    "playlist": entry.get("playlist_title", "None"),
                    "album": "-",
                    "duration": "—",
                    "type": entry.get("type"),
                    "quality": entry.get("quality", "—"),
                    "format": entry.get("format", "—"),
                    "statuses": entry.get("statuses", []),
                    "timestamp": entry.get("timestamp"),
                    "index": entry.get("index"),
                }
            )

        return jsonify(
            {
                "items": items,
                "offset": offset,
                "limit": limit,
                "total": total,
                "hasMore": offset + limit < total,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
