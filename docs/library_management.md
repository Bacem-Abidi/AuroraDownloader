# Library and Playlist Management

## Library scanning
Aurora scans the selected audio directory recursively, collecting supported audio files and metadata.

### Supported audio file extensions
- `.mp3`
- `.flac`
- `.wav`
- `.ogg`
- `.m4a`

### Library metadata
For each file, the app retrieves:
- title
- artist
- album
- track number
- year
- format
- duration
- artwork availability
- lyrics availability

This metadata is cached to speed up repeated operations.

## Library API details
The `/library` endpoint supports:
- `dir`  audio directory path (required)
- `lyricsDir`  lyrics directory path
- `offset`  pagination offset
- `limit`  pagination limit
- `reset`  if `true`, clear the library cache and force a fresh scan

## Cache logic
Aurora caches both file lists and metadata. It validates cache freshness by comparing directory modification times with the cache timestamp.

### Cache management endpoints
- `POST /cache/invalidate`  invalidate a specific cache key or all caches.
- `GET /cache/status`  inspect current cache sizes and keys.

## Playlist discovery
Aurora lists playlist files from the configured playlist directory using `/playlists`.

### Supported playlist formats
- `.m3u`
- `.m3u8`
- `.pls`

### Playlist loading
The `/playlist/<name>` endpoint loads a playlist and resolves each entry to the local audio library.

### Playlist resolution rules
The app resolves playlist entries in this order:
1. absolute paths
2. paths relative to the playlist file location
3. filename-only entries by searching `audio_dir` recursively

This helps Aurora handle playlists created with absolute, relative, or bare filenames.

## Failed downloads view
Aurora aggregates failed entries saved in the `fail/` directory.

### Failed item details
Each failed entry includes:
- original URL
- playlist title
- playlist index
- quality and format
- timestamp

### Retry options
- retry a single failed entry via `/failed/retry`
- retry multiple entries via `/failed/retry/bulk`

## History tracking
The app stores download history in `history/`.

### History endpoints
- `GET /history_files`  list available weekly history files.
- `GET /history`  return history entries for the current or selected week.

## Artwork and lyrics
- `/artwork` serves embedded artwork from local audio files.
- `/lyrics` loads saved lyrics from `.lrc` files using the audio filename.

If artwork or lyrics are not found, the app returns a 404 response.
