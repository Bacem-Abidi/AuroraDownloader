# Downloading Audio

## How audio downloads are handled

When a download is started, Aurora uses the `/start_download` endpoint to launch a background thread. This thread:

- fetches video or playlist metadata
- downloads audio using `yt-dlp`
- converts audio to the selected codec
- embeds metadata and artwork
- saves lyrics if available
- writes history and optional logs

## Supported download sources

- YouTube video URLs
- YouTube playlist URLs
- any source supported by `yt-dlp` for audio extraction

## Request fields and behavior

The download endpoint accepts these parameters:

- `url` — required source URL
- `quality` — audio quality setting for `yt-dlp` (default: `best`)
- `codec` — output format such as `mp3`, `flac`, `wav`, `opus`, or `m4a`
- `audio_dir` — download destination for audio files
- `lyrics_dir` — destination for lyrics files
- `playlist_dir` — destination for generated playlist files
- `playlist_options` — optional playlist writing options
- `mpd_options` — optional MPD integration options, including `update_mpd`
- `overwrite` — if true, existing files may be replaced
- `resume` — if true, resume partially completed downloads when supported
- `save_logs` — whether to persist logs to disk

## Output directories

Aurora expands and resolves all directory paths, including `~` and environment variables. If directories are missing, it creates them automatically.

### Default paths

- `audio_dir`: `Downloads`
- `lyrics_dir`: `Lyrics`
- `playlist_dir`: `Playlists`

## Playlist downloads

Playlist URLs are handled as a batch operation. The app:

- processes each playlist item individually
- records playlist metadata in history
- saves any playlist file references generated during download
- supports retrying failed playlist items later

## Metadata embedding

Aurora attempts to write the following metadata into downloaded audio files:

- title
- artist/uploader
- album
- year

Artwork is embedded when available or when provided manually through the metadata editor.

## Lyrics support

If lyrics are available from YouTube Music, Aurora downloads and stores them as `.lrc` files in `lyrics_dir`. The lyrics endpoint then loads these files for display in the UI.

## Logging and monitoring

Each download generates a unique `download_id`. This ID is used to stream logs from `/logs/<download_id>` while the download is active.

If `save_logs` is enabled, log files are also persisted under the `logs/` directory. These can be viewed, deleted, or cleared from the Logs page.

## Common download issues

- Invalid or unsupported URL
- Missing `yt-dlp` or `ffmpeg`
- Permission issues in output directories
- Network errors while downloading
- Unsupported audio format conversion

If issues occur, check the operation log and use the failed downloads screen to retry items.
