import os
import json
from datetime import datetime, timedelta


class Logs:
    def __init__(self, log_dir):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

    def save_fix_log(
        self,
        results,
        log_dir,
    ):
        """Save fix operation results to a log file"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"fix_playlist_{timestamp}.log")

        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"Playlist Fix Log - {timestamp}\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Playlist: {results['playlist_title']}\n")
            f.write(f"Operation completed: {datetime.now().isoformat()}\n\n")

            f.write("Summary:\n")
            f.write(f"  Total tracks in playlist: {results['total_tracks']}\n")
            f.write(f"  Existing tracks found: {results['existing_tracks']}\n")
            f.write(f"  New tracks downloaded: {results['downloaded_tracks']}\n")
            f.write(f"  Tracks metadata updated: {results['updated_tracks']}\n")
            f.write(f"  Extra files removed: {results['removed_tracks']}\n")
            f.write(f"  Tracks still missing: {results['missing_tracks']}\n\n")

            f.write("Detailed Log:\n")
            f.write("-" * 30 + "\n")
            for entry in results.get("log_entries", []):
                f.write(f"{entry}\n")

        return log_file
