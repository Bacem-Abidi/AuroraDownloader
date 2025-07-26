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
from downloader import download_manager
from flask import Flask, render_template, request, jsonify, Response

PREFS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'preferences.json')
app = Flask(__name__)
app.config["REDIS_URL"] = "redis://localhost"  # For production, use a real Redis server
app.register_blueprint(sse, url_prefix='/stream')
Bootstrap5(app)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/preferences', methods=['GET'])
def get_preferences():
    try:
        if os.path.exists(PREFS_FILE):
            with open(PREFS_FILE, 'r') as f:
                return jsonify(json.load(f))
        else:
            # Return default config structure
            return jsonify({
                "audioQuality": "best",
                "audioCodec": "mp3",
                "audioDir": "~/Music",
                "lyricsDir": "~/Music/lyrics",
                "playlistDir": "~/.config/mpd/playlists",
                "updateMpd": True,
                "mpcPath": "mpc",
                "mpcCommand": "update"
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/preferences', methods=['POST'])
def save_preferences():
    try:
        prefs = request.json
        
        # Validate required fields
        required = ["audioQuality", "audioCodec", "audioDir", "updateMpd"]
        if not all(field in prefs for field in required):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Save to file
        with open(PREFS_FILE, 'w') as f:
            json.dump(prefs, f, indent=2)
            
        return jsonify({'message': 'Preferences saved successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/start_download', methods=['POST'])
def start_download():
    data = request.get_json()
    url = data.get('url')
    quality = data.get('quality', 'best')
    codec = data.get('codec', 'mp3')
    audio_dir = data.get('audio_dir', 'Downloads') 
    lyrics_dir = data.get('lyrics_dir', 'Lyrics')
    playlist_dir = data.get('playlist_dir', 'Playlists')
    playlist_options = data.get('playlist_options', {})
    mpd_options = data.get('mpd_options', {})
    overwrite = data.get('overwrite', False)
    
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
    history_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'history')
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
        overwrite=overwrite
    )
    
    return jsonify({
        "download_id": download_id,
        "message": "Download started",
        "audio_dir": audio_dir,
        "lyrics_dir": lyrics_dir,
        "playlist_dir": playlist_dir
    })

@app.route('/logs/<download_id>')
def stream_logs(download_id):
    def generate():
        # Get the log generator
        log_generator = download_manager.get_logs(download_id)
        
        # Stream logs as they come in
        for log in log_generator:
            # Format as SSE message
            yield f"data: {log}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/history_files')
def history_files():
    history_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'history')
    files = [os.path.basename(f) for f in glob.glob(os.path.join(history_dir, 'history_*.json'))]
    return jsonify(sorted(files, reverse=True))

@app.route('/history')
def history_data():
    week = request.args.get('week', 'current')
    history_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'history')
    
    if week == 'current':
        logger = HistoryLogger(history_dir)
        file_path = logger.get_week_file()
    else:
        file_path = os.path.join(history_dir, week)
    
    if not os.path.exists(file_path):
        return jsonify([])
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        # Improved sorting with proper datetime conversion
        sorted_history = sorted(
            history,
            key=lambda x: datetime.fromisoformat(x['timestamp']),
            reverse=True
        )
        
        return jsonify(sorted_history)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
