# Getting Started

## What AuroraDownloader does

AuroraDownloader is a self-hosted Flask web application for downloading audio from YouTube videos and playlists. It converts streams to audio formats, embeds metadata and artwork, saves lyrics, and helps you manage a local audio library.

## Core architecture

- `app.py` is the main Flask entrypoint.
- `downloader/download.py` contains download, retry, migration, and move/copy logic.
- `metadata_helpers.py` handles metadata editing and artwork embedding.
- `history/`, `fail/`, `logs/`, and `migration/` are created automatically for runtime tracking.
- The `docs/` directory contains the built-in documentation files.

## Requirements

- Python 3.8 or newer
- `yt-dlp` installed and available on `PATH`
- `ffmpeg` installed and available on `PATH`
- Optional: `redis-server` for production SSE streaming and improved real-time log support

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Bacem-Abidi/AuroraDownloader.git
cd AuroraDownloader
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Install system binaries:

- `yt-dlp`
- `ffmpeg`

On Ubuntu/Debian:

```bash
sudo apt install ffmpeg
pip install yt-dlp
```

On Windows:

- Download `ffmpeg` from the official site and add it to `PATH`.
- Install `yt-dlp` using `pip install yt-dlp`.

## Configuration directories

Aurora uses several directories at runtime:

- `history/` for download history files
- `fail/` for failed download entries
- `logs/` for saved log files
- `migration/` for migration metadata
- `config/` for `preferences.json`

The app will create these directories automatically when needed.

## Run the application

```bash
flask --app app run
```

Then visit `http://127.0.0.1:5000/` in your browser.

## Built-in documentation

Open the documentation viewer at `/docs` to read the markdown docs from the `docs/` folder.

## Quick first steps

1. Open the app in a browser.
2. Set your download preferences.
3. Paste a YouTube URL and choose quality, codec, and output folders.
4. Start the download and watch the live log stream.

## Troubleshooting basics

- Confirm `yt-dlp --version` and `ffmpeg -version` work.
- Use the Logs page to inspect operation output.
- If library or playlist data is stale, reset the cache.
- If downloads fail repeatedly, check the `fail/` folder and use retry tools.
