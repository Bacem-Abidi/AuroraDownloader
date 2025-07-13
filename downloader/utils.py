import re
import unicodedata
import os

QUALITY_MAP = {
    'best': '0',
    '320': '320K',
    '256': '256K',
    '192': '192K',
    '128': '128K',
    '96': '96K',
    '64': '64K',
    '32': '32K'
}

EXTENSION_MAP = {
    'mp3': 'mp3',
    'aac': 'm4a',
    'flac': 'flac',
    'opus': 'opus',
    'wav': 'wav',
    'best': 'mp3'
}

def get_quality_setting(quality):
    return QUALITY_MAP.get(quality, '0')

def get_extension(codec):
    return EXTENSION_MAP.get(codec, 'mp3')


def sanitize_filename(filename, replace_spaces=True):
    """Sanitize filename by removing unsafe characters while preserving extension"""
    # Split into basename and extension
    base, ext = os.path.splitext(filename)
    
    # List of allowed characters (add more as needed)
    safe_chars = "-_.,'!@$%^&+=~` "
    allowed_chars = f"\\w\\s{re.escape(safe_chars)}"
    pattern = f"[^{allowed_chars}]"
    
    # Remove unsafe characters while preserving non-English characters
    base = re.sub(pattern, '', base, flags=re.UNICODE)
    
    # Remove control characters
    base = re.sub(r'[\x00-\x1F\x7F]', '', base)
    
    # Remove leading/trailing spaces and dots
    base = base.strip(' .')
    
    # Replace consecutive spaces with single space
    base = re.sub(r'\s+', ' ', base)

    if replace_spaces:
        base = base.replace(' ', '_')
    
    # If empty after sanitization, use fallback name
    if not base:
        base = "untitled_track"
    
    # Truncate long filenames
    if len(base) > 200:
        base = base[:200]
    
    # Return sanitized filename with original extension
    return base + ext
