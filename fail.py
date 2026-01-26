import os
import json
from datetime import datetime, timedelta


class FailLogger:
    def __init__(self, fail_dir):
        self.fail_dir = fail_dir
        os.makedirs(fail_dir, exist_ok=True)

    def load_all(self):
        """
        Load all failed entries across all weeks (chronological order)
        """
        all_entries = []

        files = [
            f
            for f in os.listdir(self.fail_dir)
            if f.startswith("fail_") and f.endswith(".json")
        ]

        # Sort by filename → chronological
        files.sort()

        for filename in files:
            path = os.path.join(self.fail_dir, filename)

            try:
                with open(path, "r", encoding="utf-8") as f:
                    entries = json.load(f)
                    for e in entries:
                        # ---- BACKWARD COMPATIBILITY ----
                        if "playlist" not in e and "playlist_title" in e:
                            e["playlist"] = e.pop("playlist_title")

                        all_entries.append(e)

            except Exception:
                continue

        return all_entries

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

    # def remove_entry(self, entry_to_remove):
    #     """Remove a failed entry after successful retry"""
    #     entries, file_path = self.load_week_entries()
    #     if not entries:
    #         return False
    #
    #     new_entries = [
    #         e
    #         for e in entries
    #         if not (
    #             e.get("type") == entry_to_remove.get("type")
    #             and e.get("url") == entry_to_remove.get("url")
    #             and e.get("playlist_title") == entry_to_remove.get("playlist")
    #         )
    #     ]
    #
    #     with open(file_path, "w", encoding="utf-8") as f:
    #         json.dump(new_entries, f, indent=2, ensure_ascii=False)
    #
    #     return True

    def _same_entry(self, a, b):
        return (
            a.get("type") == b.get("type")
            and a.get("url") == b.get("url")
            and a.get("playlist_title") == b.get("playlist")
        )

    def remove_entry(self, entry_to_remove):
        """Remove a failed entry from ALL week files"""
        removed = False

        for filename in os.listdir(self.fail_dir):
            if not filename.startswith("fail_") or not filename.endswith(".json"):
                continue

            path = os.path.join(self.fail_dir, filename)

            try:
                with open(path, "r", encoding="utf-8") as f:
                    entries = json.load(f)
            except Exception:
                continue

            new_entries = [
                e for e in entries if not self._same_entry(e, entry_to_remove)
            ]

            if len(new_entries) != len(entries):
                removed = True
                if new_entries:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(new_entries, f, indent=2, ensure_ascii=False)
                else:
                    # Remove empty week file
                    os.remove(path)

        return removed

    def log_fail(self, entry):
        """
        Log a failed entry with GLOBAL merge across all week files
        """
        try:
            entry = entry.copy()

            # Ensure statuses list
            status = entry.pop("status", None)
            if status:
                entry["statuses"] = [status]
            else:
                entry.setdefault("statuses", [])

            # ---- SEARCH ALL FILES FOR MERGE ----
            for filename in os.listdir(self.fail_dir):
                if not filename.startswith("fail_") or not filename.endswith(".json"):
                    continue

                path = os.path.join(self.fail_dir, filename)

                try:
                    with open(path, "r", encoding="utf-8") as f:
                        entries = json.load(f)
                except Exception:
                    continue

                for existing in entries:
                    if (
                        existing.get("type") == entry.get("type")
                        and existing.get("url") == entry.get("url")
                        and existing.get("playlist_title")
                        == entry.get("playlist_title")
                    ):
                        # ---- MERGE ----
                        if (
                            existing.get("index") is None
                            and entry.get("index") is not None
                        ):
                            existing["index"] = entry["index"]

                        existing_statuses = existing.get("statuses", [])
                        for s in entry["statuses"]:
                            if s not in existing_statuses:
                                existing_statuses.append(s)

                        existing["statuses"] = existing_statuses
                        existing["timestamp"] = entry.get("timestamp")

                        with open(path, "w", encoding="utf-8") as f:
                            json.dump(entries, f, indent=2, ensure_ascii=False)

                        return True

            # ---- NOT FOUND → APPEND TO CURRENT WEEK ----
            week_file = self.get_week_file()
            entries = []

            if os.path.exists(week_file):
                with open(week_file, "r", encoding="utf-8") as f:
                    try:
                        entries = json.load(f)
                    except json.JSONDecodeError:
                        entries = []

            entries.append(entry)

            with open(week_file, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            print(f"Error logging fail: {str(e)}")
            return False
