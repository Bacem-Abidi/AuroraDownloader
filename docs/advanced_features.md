# Advanced Features

## Migration

Aurora supports migration for existing audio libraries. Migration attempts to identify local audio files against YouTube Music metadata and optionally rename them to include the matched video ID.

### What migration does

- Scans local audio files in `audio_dir`
- Searches YouTube Music for matching tracks using title and artist
- Offers automatic or manual matching depending on accuracy
- Renames matched files to include the YouTube video ID
- Updates related lyrics and playlist references

### Migration settings

- `match_perc` — minimum similarity percentage required for automatic matches
- `fallback` — fallback action when no confident match is found; options may include `manual` or `skip`

### Manual selection

When manual choice is needed, the app uses `/migrate/choice` to receive the selected `video_id` and action.

## Move / Copy tools

Aurora can move or copy your library folders while keeping audio, lyrics, and playlist links aligned.

### Options

- `mode` — `move` or `copy`
- `process_audio` — move/copy audio files
- `process_lyrics` — move/copy matching lyrics files
- `process_playlists` — move/copy playlist files
- `update_playlists` — update playlist paths when audio files move

### Destination handling

Destination directories are created automatically if they do not exist.

## Fix Playlist

The Fix Playlist feature repairs playlists against the local audio library.

### What it can do

- Scan a playlist URL via `yt-dlp`
- Compare playlist tracks against local audio files
- Rebuild playlist files with valid local paths
- Generate reports on existing, downloaded, updated, removed, or missing tracks

### Use cases

- Audio files were moved after playlist creation
- Playlist entries point to invalid file paths
- You want local playlists consistent with existing files

## Metadata editing

Aurora can update metadata and artwork on existing audio files.

### Supported audio formats

- MP3
- FLAC
- MP4/M4A
- WAV (via generic mutagen support)

### Artwork handling

The metadata editor supports:

- uploading a new artwork image
- embedding artwork from a remote URL
- removing existing artwork
- keeping existing artwork unchanged

### Metadata fields

- `title`
- `artist`
- `album`
- `year`

## Proxy image requests

The `/proxy-image` endpoint is available to fetch remote artwork images without browser CORS issues. It downloads the image server-side and returns it with safe response headers.

## Logs and diagnostics

Aurora keeps runtime logs for most operations and exposes them through the UI.

### Log endpoints

- `/logs/settings` — view or set log saving preferences
- `/logs/files` — list saved logs
- `/logs/file/<filename>` — read a single log file
- `DELETE /logs/file/<filename>` — remove a specific log file
- `/logs/clear` — remove all saved logs

### Operation logs

Each download, retry, migration, or move/copy operation can stream progress logs using the `download_id` or `operation_id`.
