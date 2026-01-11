import os
import json
from datetime import datetime, timedelta


class ErrorLogger:
    def __init__(self, error_dir):
        self.error_dir = error_dir
        os.makedirs(error_dir, exist_ok=True)
        
    def get_week_file(self):
        """Get the error file for the current week"""
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        filename = f"error_{start_of_week.strftime('%Y-%m-%d')}_to_{end_of_week.strftime('%Y-%m-%d')}.json"
        return os.path.join(self.error_dir, filename)

    def _merge_entries(self, existing_entry, new_entry):
        """Merge two entries with the same URL"""
        merged_entry = existing_entry.copy()
        
        # Update timestamp to the latest one
        merged_entry["timestamp"] = new_entry["timestamp"]
        
        # Handle ID - keep the defined one, prefer existing if both defined
        if merged_entry.get("id") == "undefined" and new_entry.get("id") != "undefined":
            merged_entry["id"] = new_entry["id"]
        
        # Handle error_code - merge into a dictionary
        if isinstance(merged_entry.get("error_code"), dict):
            # If error_code is already a dict, find the next key
            next_key = max(merged_entry["error_code"].keys()) + 1
            merged_entry["error_code"][next_key] = new_entry["error_code"]
        else:
            # Convert to dict with sequential keys
            merged_entry["error_code"] = {
                1: merged_entry.get("error_code", ""),
                2: new_entry.get("error_code", "")
            }
        
    def log_error(self, entry):
        """Log a download error entry to the error file"""
        try:
            file_path = self.get_week_file()
            
            # Read existing entries
            entries = []
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        entries = json.load(f)
                    except json.JSONDecodeError:
                        entries = []
             
            # Check if entry with same URL already exists
            existing_index = None
            for i, existing_entry in enumerate(entries):
                if existing_entry.get("url") == entry.get("url"):
                    existing_index = i
                    break
            
            if existing_index is not None:
                # Merge with existing entry
                entries[existing_index] = self._merge_entries(entries[existing_index], entry)
            else:
                # Add new entry
                entries.append(entry)
            
            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
                
            return True
        except Exception as e:
            print(f"Error logging error: {str(e)}")
            return False
