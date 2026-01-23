import os


from collections import OrderedDict
from threading import Lock

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
PREFS_FILE = os.path.join(CONFIG_DIR, "preferences.json")
AUDIO_EXTENSIONS = (".mp3", ".flac", ".wav", ".ogg", ".m4a")


# Enhanced cache structure with locks for thread safety
class LibraryCache:
    def __init__(self, max_size=10):  # Cache up to 10 different directories/playlists
        self.cache = OrderedDict()
        self.metadata_cache = OrderedDict()
        self.max_size = max_size
        self.lock = Lock()

    def get_cache_key(self, dir_path, source_type="library"):
        """Generate a consistent cache key"""
        return f"{source_type}:{os.path.abspath(dir_path)}"

    def get(self, key):
        """Get item from cache and mark as recently used"""
        with self.lock:
            if key in self.cache:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                return self.cache[key]
        return None

    def set(self, key, value):
        """Set item in cache with LRU eviction"""
        with self.lock:
            if key in self.cache:
                # Update existing
                self.cache[key] = value
                self.cache.move_to_end(key)
            else:
                # Add new, evict if needed
                if len(self.cache) >= self.max_size:
                    self.cache.popitem(last=False)  # Remove least recently used
                self.cache[key] = value

    def invalidate(self, key):
        """Remove item from cache"""
        with self.lock:
            self.cache.pop(key, None)

    def clear(self):
        """Clear all cache"""
        with self.lock:
            self.cache.clear()
            self.metadata_cache.clear()

    def get_metadata(self, filepath):
        """Get cached metadata for a file"""
        with self.lock:
            return self.metadata_cache.get(filepath)

    def set_metadata(self, filepath, metadata):
        """Cache metadata for a file"""
        with self.lock:
            # Store metadata with file modification time
            stat = os.stat(filepath)
            self.metadata_cache[filepath] = {
                "metadata": metadata,
                "mtime": stat.st_mtime,
                "size": stat.st_size,
            }

    def is_metadata_stale(self, filepath):
        """Check if cached metadata is stale"""
        with self.lock:
            cached = self.metadata_cache.get(filepath)
            if not cached:
                return True

            try:
                stat = os.stat(filepath)
                return (
                    stat.st_mtime != cached["mtime"] or stat.st_size != cached["size"]
                )
            except Exception as e:
                return True


# Initialize cache
LIBRARY_CACHE = LibraryCache()
