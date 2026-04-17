# Troubleshooting

## Dependency checks

### `yt-dlp` or `ffmpeg` not found

Verify that both binaries are installed and on your `PATH`:

```bash
yt-dlp --version
ffmpeg -version
```

If either command fails, downloads cannot proceed.

### Python dependencies

Install required Python packages:

```bash
pip install -r requirements.txt
```

If imports fail at runtime, missing packages are usually the cause.

## Download problems

### Downloads fail or stall

- Confirm the URL is valid.
- Ensure internet access.
- Check the live log output for `yt-dlp` error messages.
- If a playlist fails partially, use the failed downloads screen.

### No audio file appears

- Confirm `audio_dir` is writable.
- Verify that `yt-dlp` successfully completed and did not exit with errors.
- Inspect the log for missing file or permission errors.

### Playlist download issues

- Ensure playlist entries can be resolved by the app.
- Use the Fix Playlist tool if files were moved or renamed.
- Retry failed items using `/failed/retry` or `/failed/retry/bulk`.

## Metadata and artwork issues

### Metadata updates fail

- Confirm the audio file exists.
- Check that the file type is supported for metadata editing.
- If the file is locked or read-only, metadata cannot be saved.

### Artwork upload or URL embedding fails

- Ensure the image is a valid JPEG/PNG.
- If using a URL, verify that the URL is reachable from the server.
- The app fetches artwork through `/proxy-image` to avoid CORS issues.

## Lyrics issues

- Lyrics are only saved when available from YouTube Music.
- The app stores lyrics in `lyrics_dir` as `.lrc` files.
- If lyrics do not appear, check that the `.lrc` file exists and is readable.

## Cache and stale data

### Stale library or playlist views

- Use `reset=true` on `/library` or `/playlist/<name>`.
- Use `/cache/invalidate` to clear one or all caches.
- Use `/cache/status` to inspect the cache state.

### Manual file changes

If you move or rename files outside the app, clear the cache and refresh the library/playlist views.

## Log inspection

- `/logs/settings` controls whether logs are saved.
- `/logs/files` lists saved log files.
- `/logs/file/<filename>` reads log content.
- `DELETE /logs/file/<filename>` removes a file.
- `/logs/clear` removes all log files.

## Permissions

- On Linux, run the app with a user that can write the configured directories.
- On Windows, avoid protected folders such as `C:\Program Files`.
- Use paths the app can create if they do not already exist.

## Docs page issues

If the built-in docs viewer shows no content:

- Confirm the `docs/` directory contains markdown files.
- Confirm the Flask app can read those files.
- Check the browser console and server logs for read errors.
