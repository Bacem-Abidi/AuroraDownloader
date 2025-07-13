import os
import json
from datetime import datetime, timedelta


class HistoryLogger:
    def __init__(self, history_dir):
        self.history_dir = history_dir
        os.makedirs(history_dir, exist_ok=True)
        
    def get_week_file(self):
        """Get the history file for the current week"""
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        filename = f"history_{start_of_week.strftime('%Y-%m-%d')}_to_{end_of_week.strftime('%Y-%m-%d')}.json"
        return os.path.join(self.history_dir, filename)
        
    def log_download(self, entry):
        """Log a download entry to the history file"""
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
            
            # Add new entry
            entries.append(entry)
            
            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
                
            return True
        except Exception as e:
            print(f"Error logging history: {str(e)}")
            return False
