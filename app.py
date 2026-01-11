import os
import re
import time
import uuid
import glob
import json
import posixpath
from pathlib import Path
from flask_sse import sse
from datetime import datetime
from ytmusicapi import YTMusic
from history import HistoryLogger
from flask_bootstrap import Bootstrap5
from mutagen import File as MutagenFile
from downloader import download_manager
from flask import Flask, render_template, request, jsonify, Response

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
PREFS_FILE = os.path.join(CONFIG_DIR, "preferences.json")
AUDIO_EXTENSIONS = (".mp3", ".flac", ".wav", ".ogg", ".m4a")
LIBRARY_CACHE = {}

# progress_tracker = ProgressTracker(CONFIG_DIR)
app = Flask(__name__)
app.config["REDIS_URL"] = "redis://localhost"  # For production, use a real Redis server
app.register_blueprint(sse, url_prefix="/stream")
Bootstrap5(app)


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

    # Expand paths and convert to absolute paths
    def expand_path(path):
        # Handle ~ and relative paths
        expanded = os.path.expanduser(path)
        # Convert to absolute path
        return os.path.abspath(expanded)

    audio_dir = expand_path(audio_dir)
    lyrics_dir = expand_path(lyrics_dir)
    playlist_dir = expand_path(playlist_dir)

    # Create directories if they don't exist
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(lyrics_dir, exist_ok=True)

    # Create history directory
    history_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history")
    os.makedirs(history_dir, exist_ok=True)

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


def get_audio_metadata(path):
    try:
        audio = MutagenFile(path, easy=True)
        if not audio:
            raise Exception("Unsupported format")

        def tag(name):
            return audio.get(name, [None])[0]

        return {
            "title": tag("title") or os.path.splitext(os.path.basename(path))[0],
            "artist": tag("artist") or "Unknown Artist",
            "album": tag("album") or "Unknown Album",
            "track": tag("tracknumber"),
            "year": tag("date") or tag("year"),
            "format": os.path.splitext(path)[1][1:],
        }

    except Exception:
        return {
            "title": os.path.splitext(os.path.basename(path))[0],
            "artist": "Unknown Artist",
            "album": "Unknown Album",
            "format": os.path.splitext(path)[1][1:],
        }


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

        playlist_dir = os.path.expanduser(os.path.expandvars(playlist_dir))
        audio_dir = os.path.expanduser(os.path.expandvars(audio_dir))

        playlist_path = os.path.join(playlist_dir, name)

        if not os.path.isfile(playlist_path):
            return jsonify({"error": "Playlist not found"}), 404

        items = []
        playlist_base_dir = os.path.dirname(playlist_path)

        with open(playlist_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                resolved = resolve_playlist_entry(line, playlist_base_dir, audio_dir)

                if not resolved:
                    continue

                meta = get_audio_metadata(resolved)

                items.append(
                    {
                        **meta,
                        "filename": os.path.basename(resolved),
                        "path": resolved,
                        "type": "playlist",
                    }
                )

        return jsonify(
            {
                "name": name,
                "count": len(items),
                "items": items,
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

        if not audio_dir:
            return jsonify({"error": "Missing audio directory"}), 400

        audio_dir = os.path.expanduser(os.path.expandvars(audio_dir))

        if not os.path.isdir(audio_dir):
            return jsonify({"error": "Invalid audio directory"}), 400

        # Scan once and cache
        if audio_dir not in LIBRARY_CACHE:
            files = []
            for root, _, filenames in os.walk(audio_dir):
                for f in filenames:
                    if f.lower().endswith(AUDIO_EXTENSIONS):
                        files.append(os.path.join(root, f))

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


if __name__ == "__main__":
    app.run(debug=True)
