import os
import json
from datetime import datetime, timedelta


class MigrationLogger:
    def __init__(self, migrate_dir):
        self.migrate_dir = migrate_dir
        os.makedirs(migrate_dir, exist_ok=True)

    def get_week_file(self):
        now = datetime.now()
        start = now - timedelta(days=now.weekday())
        end = start + timedelta(days=6)

        filename = (
            f"migration_{start.strftime('%Y-%m-%d')}_to_{end.strftime('%Y-%m-%d')}.json"
        )
        return os.path.join(self.migrate_dir, filename)

    def log_migration(self, entry):
        try:
            file_path = self.get_week_file()

            # Read existing entries
            entries = []
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        entries = json.load(f)
                    except json.JSONDecodeError:
                        entries = []

            # Add new entry
            entries.append(entry)

            # Write back to file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)

            return True
        except Exception as e:
            print(f"Error logging Migration: {str(e)}")
            return False
