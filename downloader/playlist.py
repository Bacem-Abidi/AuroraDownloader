import os
from datetime import datetime, timedelta

class PlaylistManager:
    def create_m3u_playlist(self, playlist_title, file_paths, playlist_dir, 
                           playlist_options, log_queue):
        """Create or update an M3U playlist file with change tracking"""
        try:
            # Create playlist filename
            playlist_file = os.path.join(playlist_dir, f"{playlist_title}.m3u")
            
            # Read existing playlist if it exists
            existing_entries = {}
            created_time = datetime.now().isoformat()
            if os.path.exists(playlist_file):
                with open(playlist_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for line in lines:
                        # Extract creation time if available
                        if line.startswith("#CREATED:"):
                            created_time = line.split(":", 1)[1].strip()
                        # Extract file entries
                        elif not line.startswith("#") and line.strip():
                            entry = line.strip()
                            # Normalize path for comparison
                            normalized = self._normalize_playlist_path(entry, playlist_dir)
                            existing_entries[normalized] = entry
            
            # Prepare new entries
            new_entries = {}
            for file_path in file_paths:
                # Handle different path formats
                if playlist_options.get('filenames_only'):
                    entry = os.path.basename(file_path)
                elif playlist_options.get('relative_paths'):
                    entry = os.path.relpath(file_path, playlist_dir)
                else:
                    entry = file_path
                normalized = self._normalize_playlist_path(entry, playlist_dir)
                new_entries[normalized] = entry
            
            # Compare existing vs new entries
            added = set(new_entries.keys()) - set(existing_entries.keys())
            removed = set(existing_entries.keys()) - set(new_entries.keys())
            unchanged = set(new_entries.keys()) & set(existing_entries.keys())
            
            # Generate change log
            change_log = []
            change_log.append(f"#UPDATED: {datetime.now().isoformat()}")
            
            if added:
                change_log.append(f"#ADDED: {len(added)} files")
            if removed:
                change_log.append(f"#REMOVED: {len(removed)} files")
            
            # Write M3U file with change tracking
            with open(playlist_file, 'w', encoding='utf-8') as f:
                # Write metadata headers
                f.write("#EXTM3U\n")
                f.write(f"#PLAYLIST:{playlist_title}\n")
                f.write(f"#CREATED:{created_time}\n")
                
                # Write change log
                f.write("\n".join(change_log) + "\n")

                if added:
                    f.write(f"#NEW: {datetime.now().isoformat()}\n")

                
                # Write file entries with change comments
                for normalized_path in new_entries:
                    entry = new_entries[normalized_path]
                    
                    # Add comment for new files
                    
                    f.write(f"{entry}\n")
            
            # Log results
            action = "Updated" if os.path.exists(playlist_file) else "Created"
            log_msg = (f"[PLAYLIST] {action} playlist: {os.path.basename(playlist_file)} "
                    f"({len(unchanged)} unchanged, {len(added)} added, {len(removed)} removed)")
            log_queue.put(log_msg)
            
            return True
        except Exception as e:
            log_queue.put(f"[ERROR] Failed to update M3U playlist: {str(e)}")
            return False

    def _normalize_playlist_path(self, path, base_dir):
        """Normalize playlist path for consistent comparison"""
        # Expand relative paths to absolute
        if not os.path.isabs(path):
            abs_path = os.path.normpath(os.path.join(base_dir, path))
        else:
            abs_path = os.path.normpath(path)
        
        # Case-insensitive comparison
        return abs_path.lower()
