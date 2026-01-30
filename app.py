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
from mutagen.flac import Picture
from datetime import datetime
from ytmusicapi import YTMusic
from mutagen.id3 import ID3

from metadata_helpers import (
    update_audio_metadata,
    embed_artwork_from_file,
    embed_artwork_from_url,
    remove_artwork,
)

from history import HistoryLogger
from cache import LibraryCache
from flask_bootstrap import Bootstrap5
from mutagen import File as MutagenFile
from downloader import download_manager
from flask import Flask, render_template, request, jsonify, Response
from difflib import SequenceMatcher


CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
PREFS_FILE = os.path.join(CONFIG_DIR, "preferences.json")
AUDIO_EXTENSIONS = (".mp3", ".flac", ".wav", ".ogg", ".m4a")
LIBRARY_CACHE = LibraryCache()

# progress_tracker = ProgressTracker(CONFIG_DIR)
app = Flask(__name__)
app.config["REDIS_URL"] = "redis://localhost"  # For production, use a real Redis server
app.register_blueprint(sse, url_prefix="/stream")
Bootstrap5(app)


# Helper function:
# Expand paths and convert to absolute paths
def expand_path(path):
    # Handle ~ and relative paths
    expanded = os.path.expanduser(path)
    # Convert to absolute path
    return os.path.abspath(expanded)


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


def get_lyrics_info(audio_path, lyrics_dir):
    base = os.path.splitext(os.path.basename(audio_path))[0]
    lrc_path = os.path.join(lyrics_dir, base + ".lrc")

    if os.path.isfile(lrc_path):
        return {
            "hasLyrics": True,
            "lyricsFile": os.path.basename(lrc_path),
            "mtime": os.path.getmtime(lrc_path),
        }

    return {
        "hasLyrics": False,
        "lyricsFile": None,
        "mtime": None,
    }


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


def format_bytes(size):
    if size is None:
        return None
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def format_duration_human(seconds):
    if not seconds or seconds <= 0:
        return "0m"

    seconds = int(seconds)

    m, _ = divmod(seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)

    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m or not parts:
        parts.append(f"{m}m")

    return " ".join(parts)


def format_hours(seconds):
    if not seconds:
        return "0:00"
    h, rem = divmod(int(seconds), 3600)
    m, _ = divmod(rem, 60)
    return f"{h}:{m:02d}"


def get_audio_stats(path):
    """Fast stats only: duration + file size"""
    size = os.path.getsize(path)
    duration = 0
    try:
        audio = MutagenFile(path)
        if audio and audio.info:
            duration = int(audio.info.length)
    except Exception:
        pass

    return size, duration


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


@app.route("/failed/retry/bulk", methods=["POST"])
def retry_failed_bulk():
    data = request.get_json()
    entries = data.get("entries")
    audio_dir = data.get("audio_dir", "Downloads")
    lyrics_dir = data.get("lyrics_dir", "Downloads/lyrics")
    playlist_dir = data.get("playlist_dir", "Downloads/playlists")

    audio_dir = expand_path(audio_dir)
    lyrics_dir = expand_path(lyrics_dir)
    playlist_dir = expand_path(playlist_dir)

    download_id = f"retry-{int(time.time() * 1000)}"

    fail_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fail")
    if not entries:
        mode = data.get("mode")  # all | playlist | count
        playlist = data.get("playlist")
        count = data.get("count")
        entries = download_manager._select_failed_entries(
            fail_dir=fail_dir,
            mode=mode,
            playlist=playlist,
            count=count,
        )

    if not entries:
        return jsonify({"error": "No matching failed entries"}), 400

    try:
        download_manager.retry_failed_entries(
            failed_entries=entries,
            download_id=download_id,
            audio_dir=audio_dir,
            lyrics_dir=lyrics_dir,
            playlist_dir=playlist_dir,
            fail_dir=fail_dir,
            overwrite=False,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(
        {
            "status": "started",
            "download_id": download_id,
            "count": len(entries),
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


@app.route("/lyrics")
def get_lyrics():
    path = request.args.get("path")
    lyrics_dir = expand_path(request.args.get("lyricsDir"))

    if not path:
        return jsonify({"error": "Missing path"}), 400

    base = os.path.splitext(os.path.basename(path))[0]
    lrc_path = os.path.join(lyrics_dir, base + ".lrc")

    if not os.path.isfile(lrc_path):
        return jsonify({"error": "Lyrics not found"}), 404

    with open(lrc_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    return jsonify(
        {"content": content, "format": "lrc" if "[" in content[:200] else "text"}
    )


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


@app.route("/playlist/<name>", methods=["GET"])
def load_playlist(name):
    try:
        audio_dir = request.args.get("audioDir", "Downloads")
        playlist_dir = request.args.get("playlistDir", "Downloads/playlists")
        lyrics_dir = request.args.get("lyricsDir", "Downloads/lyrics")

        offset = int(request.args.get("offset", 0))
        limit = int(request.args.get("limit", 30))
        reset = request.args.get("reset", "false").lower() == "true"
        used_cache = False

        audio_dir = expand_path(audio_dir)
        playlist_dir = expand_path(playlist_dir)
        lyrics_dir = expand_path(lyrics_dir)

        playlist_path = os.path.join(playlist_dir, name)
        if not os.path.isfile(playlist_path):
            return jsonify({"error": "Playlist not found"}), 404

        # Generate cache key for this playlist
        playlist_key = f"playlist:{playlist_path}:{audio_dir}"
        playlist_mtime = os.path.getmtime(playlist_path)

        # Clear cache if reset requested
        if reset:
            LIBRARY_CACHE.invalidate(playlist_key)

        # Check cache
        cached_data = LIBRARY_CACHE.get(playlist_key)
        if cached_data and cached_data.get("playlist_mtime") == playlist_mtime:
            # Cache is valid
            resolved_paths = cached_data["resolved_paths"]
            used_cache = True
            total_size = cached_data["total_size"]
            total_duration = cached_data["total_duration"]
        else:
            # Need to resolve playlist
            playlist_base_dir = os.path.dirname(playlist_path)
            resolved_paths = []
            total_size = 0
            total_duration = 0

            with open(playlist_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    resolved = resolve_playlist_entry(
                        line, playlist_base_dir, audio_dir
                    )
                    if resolved and os.path.exists(resolved):
                        resolved_paths.append(resolved)
                        size, duration = get_audio_stats(resolved)
                        total_size += size
                        total_duration += duration

            # Cache the resolved playlist
            LIBRARY_CACHE.set(
                playlist_key,
                {
                    "resolved_paths": resolved_paths,
                    "total_size": total_size,
                    "total_duration": total_duration,
                    "playlist_mtime": playlist_mtime,
                    "cache_time": time.time(),
                },
            )

        total = len(resolved_paths)
        slice_paths = resolved_paths[offset : offset + limit]

        items = []
        for path in slice_paths:
            # Check metadata cache
            metadata = LIBRARY_CACHE.get_metadata(path)
            if metadata and not LIBRARY_CACHE.is_metadata_stale(path, lyrics_dir):
                meta = metadata["metadata"]
                lyrics_info = metadata.get(
                    "lyrics", {"hasLyrics": False, "lyricsFile": None}
                )
            else:
                meta = get_audio_metadata(path)
                lyrics_info = get_lyrics_info(path, lyrics_dir)
                LIBRARY_CACHE.set_metadata(path, meta, lyrics_info)

            items.append(
                {
                    **meta,
                    "hasLyrics": lyrics_info["hasLyrics"],
                    "lyricsFile": lyrics_info["lyricsFile"],
                    "filename": os.path.basename(path),
                    "path": path,
                    "type": "playlist",
                }
            )

        cache_age = None
        if used_cache and cached_data.get("cache_time"):
            cache_age = int(time.time() - cached_data["cache_time"])

        return jsonify(
            {
                "name": name,
                "items": items,
                "offset": offset,
                "limit": limit,
                "total": total,
                "hasMore": offset + limit < total,
                "total_size": format_bytes(total_size),
                "total_duration": format_duration_human(total_duration),
                "cached": used_cache,
                "cache_age": cache_age,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/library", methods=["GET"])
def library():
    try:
        audio_dir = request.args.get("dir")
        lyrics_dir = request.args.get("lyricsDir", "Downloads/lyrics")
        offset = int(request.args.get("offset", 0))
        limit = int(request.args.get("limit", 30))
        reset = request.args.get("reset", "false").lower() == "true"
        used_cache = False

        if not audio_dir:
            return jsonify({"error": "Missing audio directory"}), 400

        audio_dir = expand_path(audio_dir)
        lyrics_dir = expand_path(lyrics_dir)

        if not os.path.isdir(audio_dir):
            return jsonify({"error": "Invalid audio directory"}), 400

        cache_key = LIBRARY_CACHE.get_cache_key(audio_dir, "library")

        # Clear cache if reset requested
        if reset:
            LIBRARY_CACHE.invalidate(cache_key)

        # Check if cache exists and is valid
        cached_data = LIBRARY_CACHE.get(cache_key)

        if cached_data:
            files = cached_data["files"]
            used_cache = True
            total_size = cached_data["total_size"]
            total_duration = cached_data["total_duration"]
            cache_time = cached_data["cache_time"]

            # Check if directory has been modified since cache
            try:
                dir_mtime = max(
                    os.path.getmtime(root) for root, _, _ in os.walk(audio_dir)
                )
                if dir_mtime <= cache_time:
                    # Cache is still valid
                    all_files = files
                else:
                    # Directory modified, rescan
                    raise Exception("Cache stale")
            except:
                # Force rescan
                cached_data = None

        if not cached_data:
            files = []
            total_size = 0
            total_duration = 0

            for root, _, filenames in os.walk(audio_dir):
                for f in filenames:
                    if f.lower().endswith(AUDIO_EXTENSIONS):
                        path = os.path.join(root, f)
                        files.append(path)

                        size, duration = get_audio_stats(path)
                        total_size += size
                        total_duration += duration

            files.sort(key=lambda p: os.path.basename(p).lower())

            # Cache with current time
            cached_data = {
                "files": files,
                "total_size": total_size,
                "total_duration": total_duration,
                "cache_time": time.time(),
            }
            LIBRARY_CACHE.set(cache_key, cached_data)

        all_files = cached_data["files"]
        slice_files = all_files[offset : offset + limit]

        items = []
        for path in slice_files:
            # Check metadata cache first
            metadata = LIBRARY_CACHE.get_metadata(path)
            if metadata and not LIBRARY_CACHE.is_metadata_stale(path, lyrics_dir):
                meta = metadata["metadata"]
                lyrics_info = metadata.get(
                    "lyrics", {"hasLyrics": False, "lyricsFile": None}
                )
            else:
                meta = get_audio_metadata(path)
                lyrics_info = get_lyrics_info(path, lyrics_dir)
                LIBRARY_CACHE.set_metadata(path, meta, lyrics_info)

            items.append(
                {
                    **meta,
                    **lyrics_info,
                    "filename": os.path.basename(path),
                    "path": path,
                    "quality": "—",
                    "type": "local",
                }
            )

        cache_age = None
        if used_cache and cached_data.get("cache_time"):
            cache_age = int(time.time() - cached_data["cache_time"])

        return jsonify(
            {
                "items": items,
                "offset": offset,
                "limit": limit,
                "total": len(all_files),
                "hasMore": offset + limit < len(all_files),
                "total_size": format_bytes(cached_data["total_size"]),
                "total_duration": format_duration_human(cached_data["total_duration"]),
                "cached": used_cache,
                "cache_age": cache_age,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/cache/invalidate", methods=["POST"])
def invalidate_cache():
    """Invalidate specific cache entries"""
    try:
        data = request.json
        cache_key = data.get("key")
        if cache_key:
            LIBRARY_CACHE.invalidate(cache_key)
            return jsonify({"message": f"Cache {cache_key} invalidated"})
        else:
            LIBRARY_CACHE.clear()
            return jsonify({"message": "All cache cleared"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/cache/status", methods=["GET"])
def cache_status():
    """Get cache status"""
    try:
        with LIBRARY_CACHE.lock:
            cache_info = {
                "library_cache_size": len(LIBRARY_CACHE.cache),
                "metadata_cache_size": len(LIBRARY_CACHE.metadata_cache),
                "cached_keys": list(LIBRARY_CACHE.cache.keys()),
                "max_size": LIBRARY_CACHE.max_size,
            }
        return jsonify(cache_info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Add cache invalidation when files are downloaded
def invalidate_cache_on_download(audio_dir):
    """Invalidate cache when new files are downloaded"""
    cache_key = LIBRARY_CACHE.get_cache_key(audio_dir, "library")
    LIBRARY_CACHE.invalidate(cache_key)


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


@app.route("/metadata/update", methods=["POST"])
def update_metadata():
    try:
        # Check if request is multipart/form-data
        if request.content_type and "multipart/form-data" in request.content_type:
            file_path = request.form.get("path")
            metadata_str = request.form.get("metadata")
            artwork_type = request.form.get(
                "artwork_type", "keep"
            )  # upload, url, remove, keep
            artwork_url = request.form.get("artwork_url")
            artwork_file = request.files.get("artwork_file")

            if not file_path or not os.path.exists(file_path):
                return jsonify({"error": "File not found"}), 404

            metadata = {}
            if metadata_str:
                metadata = json.loads(metadata_str)

            # Update metadata
            success = update_audio_metadata(file_path, metadata)

            # Handle artwork
            if artwork_type == "upload" and artwork_file:
                success = success and embed_artwork_from_file(file_path, artwork_file)
            elif artwork_type == "url" and artwork_url:
                success = success and embed_artwork_from_url(file_path, artwork_url)
            elif artwork_type == "remove":
                success = success and remove_artwork(file_path)
            elif artwork_type == "keep":
                # Keep existing artwork, nothing to do
                pass

        else:
            # Old JSON format (backward compatibility)
            data = request.json
            file_path = data.get("path")
            metadata = data.get("metadata", {})

            if not file_path or not os.path.exists(file_path):
                return jsonify({"error": "File not found"}), 404

            # Update metadata based on file type
            success = update_audio_metadata(file_path, metadata)

        if success:
            return jsonify({"success": True, "message": "Metadata updated"})
        else:
            return jsonify({"error": "Failed to update metadata"}), 500

    except Exception as e:
        print(f"Error in update_metadata: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/proxy-image")
def proxy_image():
    """Proxy image requests to avoid CORS issues"""
    try:
        import requests

        url = request.args.get("url")
        if not url:
            return "", 400

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.get(url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()

        # Return the image with appropriate headers
        return Response(
            response.iter_content(chunk_size=8192),
            content_type=response.headers.get("content-type", "image/jpeg"),
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as e:
        print(f"Error proxying image: {e}")
        return "", 404


@app.route("/fix_playlist", methods=["POST"])
def fix_playlist():
    try:
        data = request.json
        url = data.get("url")
        options = data.get("options", {})
        audio_dir = data.get("audio_dir", "Downloads")
        lyrics_dir = data.get("lyrics_dir", "Downloads/lyrics")
        playlist_dir = data.get("playlist_dir", "Downloads/playlists")
        playlist_options = data.get("playlist_options", {})
        mpd_options = data.get("mpd_options", {})

        if not url:
            return jsonify({"error": "Missing playlist URL"}), 400

        audio_dir = expand_path(audio_dir)
        lyrics_dir = expand_path(lyrics_dir)
        playlist_dir = expand_path(playlist_dir)

        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)

        history_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "history"
        )
        os.makedirs(history_dir, exist_ok=True)

        fail_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fail")
        os.makedirs(fail_dir, exist_ok=True)

        # Generate a unique ID for this operation
        operation_id = f"fix-{int(time.time() * 1000)}"

        # Start the fix in background thread
        download_manager.start_fix_playlist(
            url=url,
            operation_id=operation_id,
            audio_dir=audio_dir,
            lyrics_dir=lyrics_dir,
            playlist_dir=playlist_dir,
            options=options,
            playlist_options=playlist_options,
            mpd_options=mpd_options,
            log_dir=log_dir,
            history_dir=history_dir,
            fail_dir=fail_dir,
        )

        return jsonify(
            {
                "status": "started",
                "download_id": operation_id,
                "message": "Playlist fix operation started",
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
