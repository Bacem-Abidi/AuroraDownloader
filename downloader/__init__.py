from .download import DownloadManager
from .metadata import MetadataManager
from .lyrics import LyricsManager
from .playlist import PlaylistManager
from .thumbnail import ThumbnailManager
from .mpd_manager import MPDManager
from .history import HistoryManager
from .utils import get_quality_setting, get_extension

# Create a default global instance for backward compatibility
download_manager = DownloadManager()

__all__ = [
    'DownloadManager',
    'MetadataManager',
    'LyricsManager',
    'PlaylistManager',
    'ThumbnailManager',
    'MPDManager',
    'HistoryManager',
    'get_quality_setting',
    'get_extension',
    'download_manager'
]
