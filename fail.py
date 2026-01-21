import os
import json
from datetime import datetime, timedelta


class FailLogger:
    def __init__(self, fail_dir):
        self.fail_dir = fail_dir
        os.makedirs(fail_dir, exist_ok=True)

    def get_week_file(self):
        """Get the error file for the current week"""
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        filename = f"fail_{start_of_week.strftime('%Y-%m-%d')}_to_{end_of_week.strftime('%Y-%m-%d')}.json"
        return os.path.join(self.fail_dir, filename)

    def load_week_entries(self):
        """Load current week's failed entries"""
        file_path = self.get_week_file()
        if not os.path.exists(file_path):
            return [], file_path

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f), file_path
        except Exception:
            return [], file_path

    def remove_entry(self, entry_to_remove):
        """Remove a failed entry after successful retry"""
        entries, file_path = self.load_week_entries()
        if not entries:
            return False

        new_entries = [
            e
            for e in entries
            if not (
                e.get("type") == entry_to_remove.get("type")
                and e.get("url") == entry_to_remove.get("url")
                and e.get("playlist_title") == entry_to_remove.get("playlist")
            )
        ]

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(new_entries, f, indent=2, ensure_ascii=False)

        return True

    def log_fail(self, entry):
        """Log a failed entry to the fail file with merge support"""
        try:
            file_path = self.get_week_file()

            # Load existing entries
            entries = []
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        entries = json.load(f)
                    except json.JSONDecodeError:
                        entries = []

            merged = False

            for existing in entries:
                if (
                    existing.get("type") == entry.get("type")
                    and existing.get("url") == entry.get("url")
                    and existing.get("playlist_title") == entry.get("playlist_title")
                ):
                    # ---- MERGE ----

                    # Prefer non-null index
                    if existing.get("index") is None and entry.get("index") is not None:
                        existing["index"] = entry["index"]

                    # Merge statuses
                    existing_statuses = existing.get("statuses")
                    if not existing_statuses:
                        existing_statuses = [existing.get("status")]

                    if entry.get("status") not in existing_statuses:
                        existing_statuses.append(entry.get("status"))

                    existing.pop("status", None)
                    existing["statuses"] = existing_statuses

                    # Update timestamp to latest
                    existing["timestamp"] = entry.get("timestamp")

                    merged = True
                    break

            # If no merge happened, add as new entry
            if not merged:
                entry = entry.copy()
                entry["statuses"] = [entry.pop("status")]
                entries.append(entry)

            # Write back
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            print(f"Error logging fail: {str(e)}")
            return False
