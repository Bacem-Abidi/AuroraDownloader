# Preferences

## What preferences control

Aurora stores runtime configuration in `config/preferences.json`. The preferences page in the UI allows you to change defaults used for downloads and library operations.

## Key settings

- `audioQuality` — the `yt-dlp` audio quality parameter. Common values include `best`, `0` through `9`, or custom encoded quality values.
- `audioCodec` — default output audio format, such as `mp3`, `flac`, `wav`, `opus`, or `m4a`.
- `audioDir` — default folder for saving downloaded audio.
- `updateMpd` — if true, MPD integration will be triggered after downloads, playlist fixes, or relevant operations.

## Preferences API

The app exposes `/preferences`:

- `GET /preferences` returns current preferences.
- `POST /preferences` saves preferences, validating required fields.

Required fields in POST payload:

- `audioQuality`
- `audioCodec`
- `audioDir`
- `updateMpd`

## Example preferences file

```json
{
  "audioQuality": "best",
  "audioCodec": "mp3",
  "audioDir": "Downloads",
  "updateMpd": false
}
```

## Notes

- The app expands `~` and environment variables in file paths.
- If the preferences file is missing, default values are used.
- After editing the file manually, refresh the UI to make sure changes are loaded.

## Recommended workflow

1. Set preferences first.
2. Confirm output folders exist or let the app create them.
3. Use the same `audioDir`, `lyricsDir`, and `playlistDir` consistently to avoid stale path resolution.
