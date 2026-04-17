# App Reference

This document summarizes the main AuroraDownloader backend endpoints, payloads, and behavior.

## General notes

- The app uses Flask routes defined in `app.py`.
- Most operations run in background threads so the UI remains responsive.
- `download_id` and `operation_id` values are used to stream logs and track operations.
- Paths are expanded using user home and environment variables.

## `/` — Home page

- Returns the main application UI.

## `/docs` — Built-in documentation viewer

- Reads markdown files from the `docs/` directory.
- `?doc=filename.md` loads a specific document.

## `/preferences`

### GET

- Returns current preferences.

### POST

- Saves preferences.
- Required fields:
  - `audioQuality`
  - `audioCodec`
  - `audioDir`
  - `updateMpd`

## `/start_download` — start a new download

### Method

- `POST`

### Payload

- `url` (required)
- `quality`
- `codec`
- `audio_dir`
- `lyrics_dir`
- `playlist_dir`
- `playlist_options`
- `mpd_options`
- `overwrite`
- `resume`
- `save_logs`

### Response

- `download_id`
- `message`
- configured output directories

## `/failed/retry/bulk` — retry multiple failed downloads

### Method

- `POST`

### Payload

- `entries` (optional list)
- `audio_dir`
- `lyrics_dir`
- `playlist_dir`
- `save_logs`
- `mode` (`all`, `playlist`, `count`)
- `playlist`
- `count`

### Notes

If `entries` is omitted, the app selects failed records from the `fail/` directory using the selected mode.

## `/failed/retry` — retry a single failed download

### Method

- `POST`

### Payload

- `entry` (must contain `url`)
- `audio_dir`
- `lyrics_dir`
- `playlist_dir`
- `save_logs`

## `/migrate/start` — start library migration

### Method

- `POST`

### Payload

- `audio_dir`
- `lyrics_dir`
- `playlist_dir`
- `match_perc`
- `fallback`
- `save_logs`

### Response

- `migration_id`

## `/migrate/choice` — submit a manual migration choice

### Method

- `POST`

### Payload

- `migration_id`
- `video_id` (or null to skip)
- `action`

## `/logs/<download_id>` — stream logs

- Streams server-sent events (SSE) for active operations.
- Used by the UI to display real-time progress.

## `/history_files`

- Returns available `history_*.json` files from `history/`.

## `/history`

### Query parameters

- `week` — `current` or a filename.

### Response

- Sorted history entries with timestamps.

## `/artwork`

### Query parameters

- `path` — path to a local audio file.

### Response

- Returns embedded artwork image bytes with appropriate MIME type.

## `/lyrics`

### Query parameters

- `path` — path to a local audio file.
- `lyricsDir` — path to lyrics directory.

### Response

- JSON with `content` and `format`.

## `/playlists`

### Query parameters

- `dir` — playlist directory path.

### Response

- List of playlist filenames with supported extensions.

## `/playlist/<name>` — load playlist metadata

### Query parameters

- `audioDir`
- `playlistDir`
- `lyricsDir`
- `offset`
- `limit`
- `reset`

### Behavior

- Reads the playlist file
- Resolves each playlist entry to the local audio library
- Caches playlist results for performance

## `/library`

### Query parameters

- `dir` — required audio directory path
- `lyricsDir`
- `offset`
- `limit`
- `reset`

### Behavior

- Scans audio files recursively
- Gathers metadata and lyrics status
- Uses cached results when possible

## `/cache/invalidate`

### Method

- `POST`

### Payload

- `key` — specific cache key to invalidate (optional)

### Behavior

- Invalidates a specific cache entry or all caches if no key is provided.

## `/cache/status`

### Method

- `GET`

### Response

- cache entry counts
- cached keys
- max cache size

## `/failed`

### Query parameters

- `offset`
- `limit`

### Behavior

- Reads failed entries from JSON files in `fail/`
- Returns normalized items for UI display

## `/metadata/update`

### Method

- `POST`

### Supported payloads

- `multipart/form-data` for artwork upload and metadata updates
- JSON body for metadata-only updates

### Supported artwork actions

- `upload`
- `url`
- `remove`
- `keep`

### Supported metadata fields

- `title`
- `artist`
- `album`
- `year`

## `/proxy-image`

### Query parameters

- `url` — remote image URL

### Behavior

- Downloads the remote image server-side
- Returns it with safe headers for browser display

## `/fix_playlist`

### Method

- `POST`

### Payload

- `url` — playlist URL
- `options`
- `audio_dir`
- `lyrics_dir`
- `playlist_dir`
- `playlist_options`
- `mpd_options`
- `save_logs`

### Behavior

- Inspects the remote playlist with `yt-dlp`
- Scans local audio files
- Repairs playlist references as needed

## `/logs/settings`

### GET

- Returns whether log saving is enabled.

### POST

- Updates `save_logs` preference.

## `/logs/files`

- Lists saved log files.

## `/logs/file/<filename>`

### GET

- Returns file content and stats.

### DELETE

- Deletes the specified log file.

## `/logs/clear`

### POST

- Clears all saved logs.

## `/move_copy/start`

### Method

- `POST`

### Payload

- `source_audio`
- `source_lyrics`
- `source_playlists`
- `dest_audio`
- `dest_lyrics`
- `dest_playlists`
- `process_audio`
- `process_lyrics`
- `process_playlists`
- `update_playlists`
- `mode` — `move` or `copy`
- `save_logs`

### Behavior

- Starts a move/copy operation in a background thread
- Ensures destination directories exist
- Updates audio, lyrics, and playlist references as requested

## Notes

- Most operations are asynchronous; use the returned `download_id` or `operation_id` to watch logs.
- Logs are useful for debugging download failures, metadata updates, migration, and file operations.
- The app automatically creates required runtime directories when needed.
