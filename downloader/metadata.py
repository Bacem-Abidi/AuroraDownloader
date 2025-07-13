import json
import subprocess
import re
from urllib.parse import urlparse, parse_qs
from .utils import sanitize_filename

class MetadataManager:
    def __init__(self, temp_dir):
        self.temp_dir = temp_dir

    def get_playlist_metadata(self, url, log_queue):
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        playlist_id = query_params.get('list', [''])[0]
        
        cmd = [
            'yt-dlp',
            f'https://www.youtube.com/playlist?list={playlist_id}',
            '--dump-json',
            '--flat-playlist'
        ]
        
        log_queue.put("[PLAYLIST] Retrieving playlist metadata...")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        entries = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        if entries:
            playlist_title = entries[0].get('playlist_title', 'Playlist')
            sanitized_title = re.sub(r'[^\w\-_\. ]', '', playlist_title)
            log_queue.put(f"[PLAYLIST] Found {len(entries)} videos in '{sanitized_title}'")
            return sanitized_title, entries
        return "Playlist", []

    def get_video_metadata(self, url, log_queue):
        cmd = ['yt-dlp', url, '--dump-json', '--skip-download']
        log_queue.put("[METADATA] Retrieving video metadata...")
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        
        title = metadata.get('title', 'Unknown Title')
        uploader = metadata.get('uploader', 'Unknown Artist')
        upload_date = metadata.get('upload_date', '')
        year = upload_date[:4] if upload_date else ''
        video_id = metadata.get('id', '')
        thumbnail_url = metadata.get('thumbnail', '')
        
        log_queue.put(f"[METADATA] Title: {title}")
        log_queue.put(f"[METADATA] Artist: {uploader}")
        log_queue.put(f"[METADATA] Year: {year if year else 'Unknown'}")
        
        return {
            'title': title,
            'sanitized_title': sanitize_filename(title),
            'uploader': uploader,
            'year': year,
            'video_id': video_id,
            'thumbnail_url': thumbnail_url
        }
