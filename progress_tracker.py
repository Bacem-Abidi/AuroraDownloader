import json
import os
from urllib.parse import urlparse, parse_qs, urlunparse

class ProgressTracker:
    def __init__(self, config_dir):
        self.progress_file = os.path.join(config_dir, 'progress.json')
        os.makedirs(config_dir, exist_ok=True)
        
        # Initialize empty progress if file doesn't exist
        if not os.path.exists(self.progress_file):
            with open(self.progress_file, 'w') as f:
                json.dump({}, f)

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Internal helper to trim playlist URLs."""
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        if 'list' in query_params:
            clean_query = f"list={query_params['list'][0]}"
            trimmed = parsed._replace(query=clean_query)
            return urlunparse(trimmed)
        return url

    def get_progress(self, playlist_url):
        playlist_url = self._normalize_url(playlist_url)
        try:
            with open(self.progress_file, 'r') as f:
                progress_data = json.load(f)
                return progress_data.get(playlist_url)
        except Exception:
            return None

    def save_progress(self, playlist_url, playlist_title, current_index, total):
        playlist_url = self._normalize_url(playlist_url)
        try:
            with open(self.progress_file, 'r') as f:
                progress_data = json.load(f)
                
            progress_data[playlist_url] = {
                "playlist_title": playlist_title,
                "last_index": current_index,
                "total": total
            }
            
            with open(self.progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving progress: {e}")

    def clear_progress(self, playlist_url):
        playlist_url = self._normalize_url(playlist_url)
        try:
            with open(self.progress_file, 'r') as f:
                progress_data = json.load(f)
                
            if playlist_url in progress_data:
                del progress_data[playlist_url]
                
            with open(self.progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
                
        except Exception as e:
            print(f"Error clearing progress: {e}")
