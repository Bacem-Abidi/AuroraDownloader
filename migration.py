import os
import json
from datetime import datetime, timedelta


class MigrationLogger:
    def __init__(self, migrate_dir):
        self.migrate_dir = migrate_dir
        os.makedirs(migrate_dir, exist_ok=True)

    def get_week_file(self):
        """Return JSON file path for current week"""
        now = datetime.now()
        start = now - timedelta(days=now.weekday())
        end = start + timedelta(days=6)
        filename = f"migration_{start.strftime('%Y-%m-%d')}_to_{end.strftime('%Y-%m-%d')}.json"
        return os.path.join(self.migrate_dir, filename)

    def log_migration(self, entry):
        """
        Log migration entry.
        Merge entries for the same file if repeated within the week.
        """
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

            # Merge if same file already exists
            merged = False
            for existing in entries:
                if existing["file"] == entry["file"]:
                    # Merge statuses
                    existing_statuses = set(existing.get("statuses", [existing.get("status")]))
                    existing_statuses.add(entry.get("status"))
                    existing["statuses"] = list(existing_statuses)

                    # Merge reasons
                    existing_reasons = set(existing.get("reasons", [existing.get("reason")]))
                    existing_reasons.add(entry.get("reason"))
                    existing["reasons"] = list(existing_reasons)

                    # Keep latest new_file/video_id if migrated
                    if entry.get("new_file"):
                        existing["new_file"] = entry["new_file"]
                    if entry.get("video_id"):
                        existing["video_id"] = entry["video_id"]

                    # Only store candidates if ambiguous
                    if entry.get("candidates"):
                        existing["candidates"] = entry["candidates"]

                    # Update timestamp to latest
                    existing["timestamp"] = entry.get("timestamp")

                    merged = True
                    break

            if not merged:
                # Only keep necessary fields
                cleaned = {
                    "file": entry.get("file"),
                    "new_file": entry.get("new_file"),
                    "video_id": entry.get("video_id"),
                    "statuses": [entry.get("status")],
                    "reasons": [entry.get("reason")],
                    "candidates": entry.get("candidates"),
                    "timestamp": entry.get("timestamp"),
                }
                entries.append(cleaned)

            # Write back compact JSON
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)

            return True
        except Exception as e:
            print(f"Error logging Migration: {e}")
            return False
