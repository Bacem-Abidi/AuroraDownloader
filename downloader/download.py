import os
import re
import time
import json
import logging
import requests
import tempfile
import threading
import subprocess
from pathlib import Path
from queue import Queue, Empty
from .metadata import MetadataManager
from .lyrics import LyricsManager
from .playlist import PlaylistManager
from .thumbnail import ThumbnailManager
from .mpd_manager import MPDManager
from history import HistoryLogger
from migration import MigrationLogger
from fail import FailLogger
from logs import LogManager
from ytmusicapi import YTMusic
from mutagen.id3 import ID3, APIC
from mutagen import File as MutagenFile
from difflib import SequenceMatcher
from progress_tracker import ProgressTracker
from .utils import get_extension, get_quality_setting
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs


class DownloadManager:
    def __init__(self, output_dir="Downloads"):
        self.log_queues = {}
        self.active_downloads = {}
        self.lock = threading.Lock()
        self.history_logger = None
        self.fail_logger = None
        self.ytmusic = YTMusic()
        self.migration_logger = None
        self.logs = None
        self.custom_temp_dir = "temp"
        os.makedirs(self.custom_temp_dir, exist_ok=True)
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")

        # Initialize helper classes
        self.metadata_manager = MetadataManager(self.custom_temp_dir)
        self.lyrics_manager = LyricsManager()
        self.playlist_manager = PlaylistManager()
        self.thumbnail_manager = ThumbnailManager()
        self.mpd_manager = MPDManager()

        self.log_manager = LogManager()

        self.migration_choices = {}

    def _forward_logs(self, source_queue, sse_queue, file_queue):
        """Forward logs to both SSE and file"""
        while True:
            try:
                message = source_queue.get(timeout=0.5)
                if message == "[END]":
                    sse_queue.put(message)
                    file_queue.put("[LOG_END]")
                    break
                sse_queue.put(message)
                file_queue.put(message)
            except Empty:
                continue

    def start_fix_playlist(
        self,
        url,
        operation_id,
        audio_dir,
        lyrics_dir,
        playlist_dir,
        options,
        playlist_options,
        mpd_options,
        log_dir,
        history_dir,
        fail_dir,
        save_logs=False,
        log_queue=None,
    ):
        """Start a playlist fix operation in a separate thread"""
        sse_log_queue = Queue()
        self.log_queues[operation_id] = sse_log_queue
        self.active_downloads[operation_id] = True

        if save_logs and log_queue:
            combined_queue = Queue()
            threading.Thread(
                target=self._forward_logs,
                args=(combined_queue, sse_log_queue, log_queue),
                daemon=True,
            ).start()
            thread_log_queue = combined_queue
        else:
            thread_log_queue = sse_log_queue

        thread = threading.Thread(
            target=self._fix_playlist_thread,
            args=(
                url,
                operation_id,
                thread_log_queue,
                audio_dir,
                lyrics_dir,
                playlist_dir,
                options,
                playlist_options,
                mpd_options,
                log_dir,
                history_dir,
                fail_dir,
                save_logs,
            ),
            daemon=True,
        )
        thread.start()

    def _fix_playlist_thread(
        self,
        url,
        operation_id,
        log_queue,
        audio_dir,
        lyrics_dir,
        playlist_dir,
        options,
        playlist_options,
        mpd_options,
        log_dir,
        history_dir,
        fail_dir,
        save_logs,
    ):
        if history_dir:
            self.history_logger = HistoryLogger(history_dir)

        if fail_dir:
            self.fail_logger = FailLogger(fail_dir)

        if playlist_options is None:
            playlist_options = {"relative_paths": True, "filenames_only": False}
        try:
            log_queue.put(f"[FIX PLAYLIST] Starting playlist fix for: {url}")

            # Get playlist info
            playlist_metadata_cmd = ["yt-dlp", url, "--dump-json", "--flat-playlist"]

            log_queue.put("[FIX PLAYLIST] Fetching playlist metadata...")
            result = subprocess.run(
                playlist_metadata_cmd, capture_output=True, text=True, check=True
            )

            playlist_entries = [
                json.loads(line) for line in result.stdout.splitlines() if line.strip()
            ]

            if not playlist_entries:
                log_queue.put("[ERROR] No playlist entries found")
                return

            playlist_title = playlist_entries[0].get(
                "playlist_title", "Unknown Playlist"
            )
            sanitized_title = re.sub(r"[^\w\-_\. ]", "", playlist_title)

            log_queue.put(
                f"[FIX PLAYLIST] Playlist: {playlist_title} ({len(playlist_entries)} tracks)"
            )

            # Scan local files for video IDs
            log_queue.put("[FIX PLAYLIST] Scanning local files...")
            local_files = self.playlist_manager._scan_local_files(audio_dir)
            local_files_by_id = self.playlist_manager._index_files_by_video_id(
                local_files
            )

            # Track operations
            results = {
                "playlist_title": playlist_title,
                "total_tracks": len(playlist_entries),
                "existing_tracks": 0,
                "downloaded_tracks": 0,
                "updated_tracks": 0,
                "removed_tracks": 0,
                "missing_tracks": 0,
                "log_entries": [],
            }

            # Process each playlist entry
            playlist_files = []

            for i, entry in enumerate(playlist_entries, 1):
                video_id = entry.get("id")
                title = entry.get("title", "Unknown")

                log_queue.put(
                    f"[FIX PLAYLIST] Processing {i}/{len(playlist_entries)}: {title}"
                )

                if video_id in local_files_by_id:
                    # File exists
                    results["existing_tracks"] += 1
                    local_file = local_files_by_id[video_id]
                    playlist_files.append(local_file["path"])

                    log_entry = f"Exists: {title}"

                else:
                    # File missing, download if requested
                    if options.get("download_missing", True):
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        log_queue.put(
                            f"[FIX PLAYLIST] Downloading missing track: {title}"
                        )

                        try:
                            output_file = self._download_video(
                                video_url,
                                log_queue,
                                "best",  # Use default quality
                                "mp3",  # Use default codec
                                audio_dir,
                                lyrics_dir,
                                True,  # is_playlist
                                False,  # overwrite
                                playlist_title,
                            )

                            if output_file:
                                playlist_files.append(output_file)
                                results["downloaded_tracks"] += 1
                                log_entry = f"Downloaded: {title}"
                            else:
                                results["missing_tracks"] += 1
                                log_entry = f"Download failed: {title}"
                                self._log_fail(
                                    True,
                                    playlist_title,
                                    i,
                                    video_url,
                                    "best",  # Use default quality
                                    "mp3",  # Use default codec
                                    "Failed (didn't download for some reason)",
                                )

                        except Exception as e:
                            results["missing_tracks"] += 1
                            log_entry = f"Download error: {title} - {str(e)}"
                            self._log_fail(
                                True,
                                playlist_title,
                                i,
                                video_url,
                                "best",  # Use default quality
                                "mp3",  # Use default codec
                                f"Failed: {str(e)}",
                            )
                    else:
                        results["missing_tracks"] += 1
                        log_entry = f"Missing: {title}"

                results["log_entries"].append(log_entry)

            # Update playlist file
            if playlist_files:
                self.playlist_manager.create_m3u_playlist(
                    sanitized_title,
                    playlist_files,
                    playlist_dir,
                    playlist_options,
                    log_queue,
                )
                log_queue.put(
                    f"[FIX PLAYLIST] Playlist file updated: {sanitized_title}.m3u"
                )

            # Send summary
            log_queue.put(f"[FIX PLAYLIST SUMMARY]")
            log_queue.put(f"Playlist: {results['playlist_title']}")
            log_queue.put(f"Total tracks: {results['total_tracks']}")
            log_queue.put(f"Existing: {results['existing_tracks']}")
            log_queue.put(f"Downloaded: {results['downloaded_tracks']}")
            log_queue.put(f"Updated: {results['updated_tracks']}")
            log_queue.put(f"Removed: {results['removed_tracks']}")
            log_queue.put(f"Missing: {results['missing_tracks']}")

            log_queue.put("[FIX PLAYLIST COMPLETE]")

        except Exception as e:
            log_queue.put(f"[ERROR] Playlist fix failed: {str(e)}")
        finally:
            if mpd_options and mpd_options.get("update_mpd"):
                self.mpd_manager.update_mpd(mpd_options, log_queue)

            if save_logs:
                self.log_manager.stop_logging(operation_id)

            self.active_downloads.pop(operation_id, None)
            log_queue.put("[END]")

    def _select_failed_entries(self, fail_dir, mode, playlist=None, count=0):
        if fail_dir:
            self.fail_logger = FailLogger(fail_dir)

        if not self.fail_logger:
            return []

        entries = self.fail_logger.load_all()

        if mode == "playlist":
            entries = [e for e in entries if e.get("playlist_title") == playlist]

        elif mode == "count":
            entries = entries[: int(count)]

        return entries

    def _get_best_audio_format_id(self, url, log_queue):
        cmd = ["yt-dlp", "--list-formats", url]

        log_queue.put("[FORMAT] Listing available formats")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            universal_newlines=True,
        )

        audio_formats = []

        for line in process.stdout:
            line = line.strip()
            if not line or line.startswith("ID"):
                continue

            # Typical line:
            # 251 webm audio only tiny 160k , opus @160k
            parts = line.split()
            if "audio" in line and "only" in line:
                format_id = parts[0]
                audio_formats.append(format_id)

        process.wait()

        if not audio_formats:
            log_queue.put("[FORMAT] No audio-only formats found")
            return None

        # yt-dlp lists worst → best, so take the last
        chosen = audio_formats[-1]
        log_queue.put(f"[FORMAT] Selected audio format id: {chosen}")
        return chosen

    def retry_failed_entries(
        self,
        failed_entries,
        download_id,
        audio_dir,
        lyrics_dir,
        playlist_dir,
        fail_dir,
        overwrite=False,
        save_logs=False,
        log_queue=None,
    ):
        sse_log_queue = Queue()
        self.log_queues[download_id] = sse_log_queue
        self.active_downloads[download_id] = True

        if save_logs and log_queue:
            combined_queue = Queue()
            threading.Thread(
                target=self._forward_logs,
                args=(combined_queue, sse_log_queue, log_queue),
                daemon=True,
            ).start()
            thread_log_queue = combined_queue
        else:
            thread_log_queue = sse_log_queue

        thread = threading.Thread(
            target=self._retry_failed_bulk_thread,
            args=(
                failed_entries,
                download_id,
                thread_log_queue,
                audio_dir,
                lyrics_dir,
                playlist_dir,
                fail_dir,
                overwrite,
                save_logs,
            ),
            daemon=True,
        )
        thread.start()

    def _retry_failed_bulk_thread(
        self,
        entries,
        download_id,
        log_queue,
        audio_dir,
        lyrics_dir,
        playlist_dir,
        fail_dir,
        overwrite,
        save_logs,
    ):
        if fail_dir:
            self.fail_logger = FailLogger(fail_dir)

        total = len(entries)
        success = 0
        failed = 0

        try:
            log_queue.put(f"[BULK RETRY] Retrying {total} failed downloads")

            for i, entry in enumerate(entries, 1):
                url = entry["url"]
                quality = entry.get("quality", "best")
                codec = entry.get("format", "mp3")
                playlist_title = entry.get("playlist")
                index = entry.get("index")
                is_playlist = entry.get("type") == "playlist"

                log_queue.put(f"[{i}/{total}] Retrying")
                log_queue.put(f"[URL] {url}")

                try:
                    output_file = self._download_video(
                        url,
                        log_queue,
                        quality,
                        codec,
                        audio_dir,
                        lyrics_dir,
                        is_playlist,
                        overwrite,
                        playlist_title,
                    )

                    if not output_file:
                        log_queue.put("[RETRY] Checking for different formats....")

                        format_id = self._get_best_audio_format_id(url, log_queue)

                        if not format_id:
                            failed += 1
                            log_queue.put("[RESULT] Retry failed (no formats)")
                            continue

                        log_queue.put(
                            f"[RETRY] Retrying with discovered format {format_id}"
                        )
                        output_file = self._download_video(
                            url,
                            log_queue,
                            quality,
                            codec,
                            audio_dir,
                            lyrics_dir,
                            is_playlist,
                            overwrite,
                            playlist_title,
                            format_id=format_id,
                        )

                        if not output_file:
                            failed += 1
                            log_queue.put("[RESULT] Retry failed (format retry)")
                            continue

                    # Remove from failed log
                    if self.fail_logger:
                        self.fail_logger.remove_entry(entry)

                    # Fix playlist order
                    if is_playlist and playlist_title and index is not None:
                        self._insert_into_playlist(
                            playlist_title,
                            output_file,
                            index,
                            playlist_dir,
                            log_queue,
                        )

                    success += 1
                    log_queue.put("[RESULT] Retry succeeded")

                except Exception as e:
                    failed += 1
                    log_queue.put(f"[ERROR] Retry failed: {str(e)}")

            log_queue.put("[BULK RETRY COMPLETE]")
            log_queue.put(f"[SUCCESS] Succussfull retries: {success}")
            log_queue.put(f"[FAILED] Failed retries: {failed}")

        finally:
            if save_logs:
                self.log_manager.stop_logging(download_id)

            self.active_downloads.pop(download_id, None)
            log_queue.put("[END]")

    def retry_failed_entry(
        self,
        failed_entry,
        download_id,
        audio_dir,
        lyrics_dir,
        playlist_dir,
        fail_dir,
        overwrite=False,
        save_logs=False,
        log_queue=None,
    ):
        """
        Retry a single failed download entry
        """
        sse_log_queue = Queue()
        self.log_queues[download_id] = sse_log_queue
        self.active_downloads[download_id] = True

        if save_logs and log_queue:
            combined_queue = Queue()
            threading.Thread(
                target=self._forward_logs,
                args=(combined_queue, sse_log_queue, log_queue),
                daemon=True,
            ).start()
            thread_log_queue = combined_queue
        else:
            thread_log_queue = sse_log_queue

        thread = threading.Thread(
            target=self._retry_failed_thread,
            args=(
                failed_entry,
                download_id,
                thread_log_queue,
                audio_dir,
                lyrics_dir,
                playlist_dir,
                fail_dir,
                overwrite,
                save_logs,
            ),
            daemon=True,
        )
        thread.start()

    def _retry_failed_thread(
        self,
        entry,
        download_id,
        log_queue,
        audio_dir,
        lyrics_dir,
        playlist_dir,
        fail_dir,
        overwrite,
        save_logs,
    ):
        if fail_dir:
            self.fail_logger = FailLogger(fail_dir)
        try:
            url = entry["url"]
            quality = entry.get("quality", "best")
            codec = entry.get("format", "mp3")
            playlist_title = entry.get("playlist")
            index = entry.get("index")
            is_playlist = entry.get("type") == "playlist"

            log_queue.put("[RETRY] Retrying failed download...")
            log_queue.put(f"[URL] {url}")

            output_file = self._download_video(
                url,
                log_queue,
                quality,
                codec,
                audio_dir,
                lyrics_dir,
                is_playlist,
                overwrite,
                playlist_title,
            )

            if not output_file:
                log_queue.put("[RETRY] Checking for different formats....")

                format_id = self._get_best_audio_format_id(url, log_queue)

                if not format_id:
                    log_queue.put("[RESULT] Retry failed (no formats)")
                    return

                log_queue.put(f"[RETRY] Retrying with discovered format {format_id}")
                output_file = self._download_video(
                    url,
                    log_queue,
                    quality,
                    codec,
                    audio_dir,
                    lyrics_dir,
                    is_playlist,
                    overwrite,
                    playlist_title,
                    format_id=format_id,
                )
                if not output_file:
                    log_queue.put("[RESULT] Retry failed (format retry)")
                    return

            log_queue.put("[RETRY] Download succeeded")

            # Remove from failed entries
            if self.fail_logger:
                self.fail_logger.remove_entry(entry)
                log_queue.put("[RETRY] Removed entry from failed log")

            # Fix playlist position if needed
            if is_playlist and playlist_title and index is not None:
                self._insert_into_playlist(
                    playlist_title,
                    output_file,
                    index,
                    playlist_dir,
                    log_queue,
                )

        except Exception as e:
            log_queue.put(f"[ERROR] Retry failed: {str(e)}")

        finally:
            if save_logs:
                self.log_manager.stop_logging(download_id)
            self.active_downloads.pop(download_id, None)
            log_queue.put("[END]")

    def _detect_playlist_path_style(self, lines):
        """
        Determine how paths are stored in the playlist.
        Returns: "absolute", "relative", or "filename"
        """
        for line in lines:
            if not line or line.startswith("#"):
                continue

            if os.path.isabs(line):
                return "absolute"

            if "/" in line or "\\" in line:
                return "relative"

            return "filename"

        return "filename"

    def _normalize_track_path(self, track_path, style, playlist_dir):
        if style == "absolute":
            return os.path.abspath(track_path)

        if style == "relative":
            return os.path.relpath(
                track_path,
                start=playlist_dir,
            )

        # filename-only
        return os.path.basename(track_path)

    def _insert_into_playlist(
        self,
        playlist_title,
        track_path,
        index,
        playlist_dir,
        log_queue,
    ):
        playlist_file = os.path.join(playlist_dir, f"{playlist_title}.m3u")

        if not os.path.exists(playlist_file):
            log_queue.put("[PLAYLIST] Playlist file not found, creating new one")
            with open(playlist_file, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write(track_path + "\n")
            return

        with open(playlist_file, "r", encoding="utf-8") as f:
            lines = [l.rstrip("\n") for l in f]

        # Separate track line positions
        track_line_indices = [
            i for i, line in enumerate(lines) if line and not line.startswith("#")
        ]

        style = self._detect_playlist_path_style(lines)

        # Normalize track path to match playlist
        normalized_track = self._normalize_track_path(track_path, style, playlist_dir)

        # Recompute after dedupe
        track_line_indices = [
            i for i, line in enumerate(lines) if line and not line.startswith("#")
        ]

        # Convert 1-based index → 0-based
        target_track_pos = max(0, index - 1)

        # Clamp to available track count
        if target_track_pos >= len(track_line_indices):
            # Append after last track
            insert_at = len(lines)
        else:
            insert_at = track_line_indices[target_track_pos]

        lines.insert(insert_at, normalized_track)

        with open(playlist_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        log_queue.put(
            f"[PLAYLIST] Inserted track at track position {target_track_pos + 1} in {playlist_title}"
        )

    def start_download(
        self,
        url,
        download_id,
        quality="best",
        codec="mp3",
        audio_dir="Downloads",
        lyrics_dir="Lyrics",
        playlist_dir="Playlists",
        playlist_options=None,
        mpd_options=None,
        history_dir=None,
        fail_dir=None,
        overwrite=False,
        resume=False,
        config_dir=None,
        save_logs=False,
        log_queue=None,
    ):
        """Start a download process in a separate thread"""
        if download_id in self.active_downloads:
            return

        # Create directories if needed
        Path(audio_dir).mkdir(parents=True, exist_ok=True)
        Path(lyrics_dir).mkdir(parents=True, exist_ok=True)
        Path(playlist_dir).mkdir(parents=True, exist_ok=True)

        self.progress_tracker = ProgressTracker(config_dir)

        if history_dir:
            self.history_logger = HistoryLogger(history_dir)

        if fail_dir:
            self.fail_logger = FailLogger(fail_dir)

        # Create a new queue for this download
        sse_log_queue = Queue()
        self.log_queues[download_id] = sse_log_queue
        self.active_downloads[download_id] = True

        if save_logs and log_queue:
            # We'll write to both queues
            combined_queue = Queue()
            # Start a thread to forward logs to both destinations
            threading.Thread(
                target=self._forward_logs,
                args=(combined_queue, sse_log_queue, log_queue),
                daemon=True,
            ).start()
            thread_log_queue = combined_queue
        else:
            thread_log_queue = sse_log_queue

        # Start the download in a new thread
        thread = threading.Thread(
            target=self._download_thread,
            args=(
                url,
                download_id,
                thread_log_queue,
                quality,
                codec,
                audio_dir,
                lyrics_dir,
                playlist_dir,
                playlist_options,
                mpd_options,
                overwrite,
                resume,
            ),
            daemon=True,
        )
        thread.start()

    def _download_thread(
        self,
        url,
        download_id,
        log_queue,
        quality,
        codec,
        audio_dir,
        lyrics_dir,
        playlist_dir,
        playlist_options,
        mpd_options,
        overwrite,
        resume=False,
        save_logs=False,
    ):
        """The actual download thread"""
        thumbnail_path = None
        output_file = None
        playlist_files = []

        try:
            is_playlist = False
            playlist_title = "Playlist"

            if playlist_options is None:
                playlist_options = {"relative_paths": True, "filenames_only": False}

            if "list=" in url and "playlist" in url:
                is_playlist = True
                parsed_url = urlparse(url)
                query_params = parse_qs(parsed_url.query)
                playlist_id = query_params.get("list", [""])[0]

                # Get playlist metadata
                playlist_metadata_cmd = [
                    "yt-dlp",
                    f"https://www.youtube.com/playlist?list={playlist_id}",
                    "--dump-json",
                    "--flat-playlist",
                ]

                log_queue.put("[PLAYLIST] Retrieving playlist metadata...")
                result = subprocess.run(
                    playlist_metadata_cmd, capture_output=True, text=True, check=True
                )

                playlist_entries = [
                    json.loads(line)
                    for line in result.stdout.splitlines()
                    if line.strip()
                ]

                if playlist_entries:
                    playlist_title = playlist_entries[0].get(
                        "playlist_title", "Playlist"
                    )
                    playlist_title = re.sub(
                        r"[^\w\-_\. ]", "", playlist_title
                    )  # Sanitize filename
                    log_queue.put(
                        f"[PLAYLIST] Found {len(playlist_entries)} videos in '{playlist_title}'"
                    )
                else:
                    log_queue.put(
                        "[WARNING] Failed to get playlist metadata, using default"
                    )

            if is_playlist:
                log_queue.put(
                    f"[PLAYLIST] Starting download of playlist: {playlist_title}"
                )

                # Generate playlist file path
                playlist_file = os.path.join(playlist_dir, f"{playlist_title}.m3u")

                # Load existing playlist entries if resuming
                if resume and os.path.exists(playlist_file):
                    try:
                        with open(playlist_file, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith("#"):
                                    playlist_files.append(line)
                        log_queue.put(
                            f"[PROGRESS] Loaded {len(playlist_files)} existing tracks from playlist"
                        )
                    except Exception as e:
                        log_queue.put(
                            f"[WARNING] Failed to load existing playlist: {str(e)}"
                        )

                start_index = 0
                if resume:
                    progress = self.progress_tracker.get_progress(url)
                    if progress:
                        start_index = progress["last_index"] + 1
                        log_queue.put(
                            f"[PROGRESS] Resuming from track {start_index + 1}/{len(playlist_entries)}"
                        )
                    else:
                        log_queue.put(
                            "[PROGRESS] No progress found, starting from beginning"
                        )

                # Download each video in the playlist
                for i, entry in enumerate(playlist_entries):
                    if i < start_index:
                        continue

                    video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                    log_queue.put(
                        f"[PLAYLIST] Downloading video {i + 1}/{len(playlist_entries)}: {entry.get('title', 'Untitled')}"
                    )

                    # Download the video
                    video_file = self._download_video(
                        video_url,
                        log_queue,
                        quality,
                        codec,
                        audio_dir,
                        lyrics_dir,
                        is_playlist,
                        overwrite,
                        playlist_title,
                    )

                    if video_file:
                        playlist_files.append(video_file)
                        self.progress_tracker.save_progress(
                            url, playlist_title, i, len(playlist_entries)
                        )

                        log_queue.put(
                            f"[PLAYLIST] Completed video {i + 1}/{len(playlist_entries)}"
                        )
                    else:
                        self._log_fail(
                            is_playlist,
                            playlist_title,
                            i + 1,
                            video_url,
                            quality,
                            codec,
                            "Failed (didn't download for some reason)",
                        )
                        log_queue.put(f"[WARNING] Failed to download video {i + 1}")

                # Create M3U playlist file
                if playlist_files:
                    self.playlist_manager.create_m3u_playlist(
                        playlist_title,
                        playlist_files,
                        playlist_dir,
                        playlist_options,
                        log_queue,
                    )
                    log_queue.put(f"[PLAYLIST] Created M3U playlist in {playlist_dir}")
                else:
                    log_queue.put("[WARNING] No files downloaded for playlist")

                # End playlist processing
                self.active_downloads.pop(download_id, None)
                log_queue.put("[END]")
                return

            # If not a playlist, process as single video
            output_file = self._download_video(
                url,
                log_queue,
                quality,
                codec,
                audio_dir,
                lyrics_dir,
                is_playlist,
                overwrite,
            )
        except Exception as e:
            log_queue.put(f"[ERROR] Download failed: {str(e)}")
            output_file = None

        finally:
            # Clean up thumbnail file
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
                log_queue.put("[THUMBNAIL] Temporary thumbnail deleted")

            # Update MPD if requested
            if mpd_options and mpd_options.get("update_mpd"):
                self.mpd_manager.update_mpd(mpd_options, log_queue)

            if save_logs:
                self.log_manager.stop_logging(download_id)

            self.active_downloads.pop(download_id, None)
            log_queue.put("[END]")  # Signal end of stream

    def _download_video(
        self,
        url,
        log_queue,
        quality,
        codec,
        audio_dir,
        lyrics_dir,
        is_playlist,
        overwrite=False,
        playlist_title=None,
        format_id=None,
    ):
        """Download and process a single video using helper classes"""
        thumbnail_path = None
        output_file = None
        lrc_file = None

        try:
            # Get video metadata
            metadata = self.metadata_manager.get_video_metadata(url, log_queue)
            title = metadata["title"]
            sanitized_title = metadata["sanitized_title"] + "_" + metadata["video_id"]
            uploader = metadata["uploader"]
            year = metadata["year"]
            video_id = metadata["video_id"]
            thumbnail_url = metadata["thumbnail_url"]

            # Determine output filename
            extension = get_extension(codec)
            output_filename = f"{sanitized_title}.{extension}"
            output_path = os.path.join(audio_dir, output_filename)

            # Check if file exists and overwrite is disabled
            if os.path.exists(output_path) and not overwrite:
                log_queue.put(f"[SKIPPED] File exists: {output_filename}")
                self._log_history(
                    is_playlist,
                    playlist_title,
                    url,
                    output_path,
                    uploader,
                    lrc_file,
                    quality,
                    codec,
                    "skipped",
                )
                return output_path

            # Download thumbnail
            thumbnail_path = (
                self.thumbnail_manager.download_thumbnail(thumbnail_url, log_queue)
                if thumbnail_url
                else None
            )

            # Get lyrics
            lyrics = self.lyrics_manager.get_lyrics(
                title, uploader, video_id, log_queue
            )

            # Prepare download command
            quality_setting = get_quality_setting(quality)
            log_queue.put(f"[QUALITY] Selected: {quality} ({quality_setting})")
            log_queue.put(f"[SETTINGS] Selected codec: {codec.upper()}")

            cmd = self._build_download_command(
                url,
                quality_setting,
                codec,
                audio_dir,
                year,
                uploader,
                title,
                sanitized_title,
                format_id=format_id,
            )
            log_queue.put(f"[COMMAND] {' '.join(cmd)}")

            # Execute download command
            output_file = self._execute_download_command(
                cmd, audio_dir, sanitized_title, extension, log_queue
            )

            if output_file:
                # Embed thumbnail if available
                if thumbnail_path:
                    self.thumbnail_manager.embed_thumbnail(
                        output_file, thumbnail_path, codec, log_queue
                    )

                # Save lyrics
                if lyrics:
                    base_name = os.path.splitext(os.path.basename(output_file))[0]
                    lrc_file = os.path.join(lyrics_dir, f"{base_name}.lrc")

                    with open(lrc_file, "w", encoding="utf-8") as f:
                        f.write(lyrics)

                    log_queue.put(
                        f"[LYRICS] Saved lyrics to {os.path.basename(lrc_file)}"
                    )
                    log_queue.put(f"[DIRECTORY] Lyrics saved to: {lyrics_dir}")

                # Log history
                self._log_history(
                    is_playlist,
                    playlist_title,
                    url,
                    output_file,
                    uploader,
                    lrc_file,
                    quality,
                    codec,
                    "downloaded",
                )

            else:
                self._log_fail(
                    is_playlist,
                    playlist_title,
                    None,
                    url,
                    quality,
                    codec,
                    "Failed (didn't download for some reason)",
                )

            return output_file

        except Exception as e:
            self._log_fail(
                is_playlist,
                playlist_title,
                None,
                url,
                quality,
                codec,
                "[ERROR] Download failed: " + str(e),
            )
            log_queue.put(f"[ERROR] Download failed: {str(e)}")
            return None
        finally:
            # Clean up thumbnail file
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
                log_queue.put("[THUMBNAIL] Temporary thumbnail deleted")

    def _build_download_command(
        self,
        url,
        quality_setting,
        codec,
        audio_dir,
        year,
        artist,
        title,
        sanitized_title,
        format_id=None,
    ):
        """Construct the yt-dlp command with appropriate parameters"""
        cmd = ["yt-dlp", url]

        if format_id:
            # Explicit format retry (from --list-formats)
            cmd.extend(["-f", format_id])
        else:
            # Normal path: let yt-dlp choose best audio
            cmd.extend(["-f", "bestaudio"])

        cmd.extend(
            [
                "--extract-audio",
                "--audio-format",
                codec,
                "--audio-quality",
                quality_setting,
            ]
        )
        cmd.extend(
            [
                "--embed-metadata",
                "--add-metadata",
                "--parse-metadata",
                f"title:{title}",
                "--parse-metadata",
                f"uploader:{artist}",
                # '--output', f'{audio_dir}/%(title)s.%(ext)s',
                "-o",
                f"{audio_dir}/{sanitized_title}.%(ext)s",
                "--verbose",
                "--no-simulate",
                "--newline",
            ]
        )

        # Add year if available
        if year:
            cmd.extend(["--parse-metadata", f"{year}:%(meta_year)s"])

        # Special handling for certain codecs
        if codec == "flac":
            cmd.extend(["--audio-quality", "0"])  # FLAC is lossless
            cmd.extend(["--postprocessor-args", "-c:a flac -compression_level 12"])
        elif codec == "wav":
            cmd.extend(["--postprocessor-args", "-c:a pcm_s16le"])
        elif codec == "opus":
            cmd.extend(["--postprocessor-args", "-b:a " + quality_setting])

        return cmd

    def _execute_download_command(self, cmd, audio_dir, title, extension, log_queue):
        """Run the download command and process output"""
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        # Stream output in real-time
        for line in process.stdout:
            cleaned_line = line.strip()
            if cleaned_line:
                # Simplify verbose messages
                if "Deleting original file" in cleaned_line:
                    cleaned_line = "[CLEANUP] Deleting temporary files"
                elif "Embedding metadata" in cleaned_line:
                    cleaned_line = "[METADATA] Embedding metadata"
                elif "Embedding thumbnail" in cleaned_line:
                    cleaned_line = "[METADATA] Embedding thumbnail"

                log_queue.put(cleaned_line)

        process.wait()

        if process.returncode != 0:
            log_queue.put(f"[ERROR] Download failed with code {process.returncode}")
            return None

        # Find the downloaded file
        output_files = [
            f
            for f in os.listdir(audio_dir)
            if f.endswith(f".{extension}") and title in f
        ]

        if not output_files:
            log_queue.put("[ERROR] Downloaded file not found")
            return None

        output_file = os.path.join(audio_dir, output_files[0])
        log_queue.put(f"[SUCCESS] Audio downloaded: {output_files[0]}")
        return output_file

    def start_migration(
        self,
        migration_id,
        audio_dir,
        lyrics_dir,
        playlist_dir,
        match_perc,
        fallback,
        migrate_dir,
        save_logs=False,
        log_queue=None,
    ):
        self.migration_logger = MigrationLogger(migrate_dir)

        sse_log_queue = Queue()
        self.log_queues[migration_id] = sse_log_queue
        self.active_downloads[migration_id] = True

        if save_logs and log_queue:
            combined_queue = Queue()
            threading.Thread(
                target=self._forward_logs,
                args=(combined_queue, sse_log_queue, log_queue),
                daemon=True,
            ).start()
            thread_log_queue = combined_queue
        else:
            thread_log_queue = sse_log_queue

        thread = threading.Thread(
            target=self._migration_thread,
            args=(
                migration_id,
                audio_dir,
                lyrics_dir,
                playlist_dir,
                match_perc,
                fallback,
                thread_log_queue,
                save_logs,
            ),
            daemon=True,
        )
        thread.start()

    def _migration_thread(
        self,
        migration_id,
        audio_dir,
        lyrics_dir,
        playlist_dir,
        match_perc,
        fallback,
        log_queue,
        save_logs,
    ):
        log_queue.put(
            f"[MIGRATION] Starting library migration With {match_perc}% accuracy..."
        )

        try:
            match_threshold = float(match_perc) / 100.0
        except (TypeError, ValueError):
            match_threshold = 0.85

        # Collect all audio files first (for progress logging)
        entries = []
        for root, _, files in os.walk(audio_dir):
            for filename in files:
                if filename.lower().endswith((".mp3", ".flac", ".m4a")):
                    entries.append(os.path.join(root, filename))

        entries.sort(key=lambda p: os.path.basename(p).lower())

        for i, path in enumerate(entries):
            filename = os.path.basename(path)
            log_queue.put(
                f"[MIGRATE] Migrating File {i + 1}/{len(entries)}: {filename}"
            )

            try:
                meta = self.get_audio_metadata(path)
                if not meta:
                    raise Exception("MetaData was not fetched")
                title = meta["title"]
                artist = meta["artist"]

                log_queue.put(f"[SCAN] {title} — {artist}")

                query = f"{title} {artist}"
                search_filter = "songs"

                # --- First pass: VIDEOS ---
                cleaned = self._search_and_clean(
                    query, title, artist, match_threshold, search_filter=search_filter
                )

                # --- Second pass: SONGS (only if low confidence) ---
                if not cleaned:
                    log_queue.put(
                        "[RETRY] Low confidence — retrying with Videos filter"
                    )
                    search_filter = "videos"

                    cleaned = self._search_and_clean(
                        query,
                        title,
                        artist,
                        match_threshold,
                        search_filter=search_filter,
                        log_queue=log_queue,
                    )
                    log_queue.put(f"[RETRY] Low confidence — retrying result {cleaned}")

                if len(cleaned) == 1:
                    log_queue.put(f"result {cleaned}")
                    self._apply_migration(
                        lyrics_dir,
                        playlist_dir,
                        path,
                        cleaned[0]["videoId"],
                        log_queue,
                    )
                elif len(cleaned) > 1:
                    if fallback == "manual":
                        log_queue.put("[CHOICE_REQUIRED]")

                        choice_event = threading.Event()
                        self.migration_choices[migration_id] = {
                            "event": choice_event,
                            "action": None,
                            "video_id": None,
                        }

                        log_queue.put(
                            json.dumps(
                                {
                                    "type": "choice",
                                    "file": path,
                                    "title": title,
                                    "artist": artist,
                                    "candidates": cleaned[:10],
                                    "allow_research": True,
                                    "allow_manual": True,
                                    "search_filter": search_filter,
                                }
                            )
                        )

                        choice_event.wait()

                        choice = self.migration_choices[migration_id]
                        del self.migration_choices[migration_id]

                        if choice["action"] == "select":
                            self._apply_migration(
                                lyrics_dir,
                                playlist_dir,
                                path,
                                choice["video_id"],
                                log_queue,
                            )
                            continue

                        if choice["action"] == "manual":
                            log_queue.put("[MANUAL] User provided video ID")

                            self._apply_migration(
                                lyrics_dir,
                                playlist_dir,
                                path,
                                choice["video_id"],
                                log_queue,
                            )
                            continue

                        action = choice["action"]
                        if action and action.startswith("research_"):
                            search_filter = action.split("_", 1)[1]
                            log_queue.put(
                                f"[RESEARCH] User requested {search_filter.upper()} search"
                            )

                            cleaned = self._search_and_clean(
                                query,
                                title,
                                artist,
                                match_threshold,
                                search_filter=search_filter,
                            )

                            if cleaned:
                                choice_event = threading.Event()
                                self.migration_choices[migration_id] = {
                                    "event": choice_event,
                                    "action": None,
                                    "video_id": None,
                                }

                                log_queue.put(
                                    json.dumps(
                                        {
                                            "type": "choice",
                                            "file": path,
                                            "title": title,
                                            "artist": artist,
                                            "candidates": cleaned[:10],
                                            "allow_research": False,  # prevent infinite loop
                                            "allow_manual": True,
                                            "search_filter": search_filter,
                                        }
                                    )
                                )

                                choice_event.wait()
                                choice = self.migration_choices[migration_id]
                                del self.migration_choices[migration_id]

                                if choice["action"] == "select":
                                    self._apply_migration(
                                        lyrics_dir,
                                        playlist_dir,
                                        path,
                                        choice["video_id"],
                                        log_queue,
                                    )
                                if choice["action"] == "manual":
                                    log_queue.put("[MANUAL] User provided video ID")

                                    self._apply_migration(
                                        lyrics_dir,
                                        playlist_dir,
                                        path,
                                        choice["video_id"],
                                        log_queue,
                                    )
                                    continue
                                else:
                                    self._log_migration(
                                        path,
                                        title,
                                        artist,
                                        "skipped",
                                        "user skipped",
                                    )
                                    log_queue.put(
                                        "[SKIP] User skipped after SONGS search"
                                    )

                            else:
                                self._log_migration(
                                    path,
                                    title,
                                    artist,
                                    "skipped",
                                    "no matches were found",
                                )
                                log_queue.put("[SKIP] No SONGS matches found")

                            continue

                        self._log_migration(
                            path,
                            title,
                            artist,
                            "skipped",
                            "user skipped",
                        )
                        log_queue.put("[SKIP] User skipped")
                        continue
                    elif fallback == "best":
                        self._apply_migration(
                            lyrics_dir,
                            playlist_dir,
                            path,
                            cleaned[0]["videoId"],
                            log_queue,
                        )
                        continue
                    else:
                        self._log_migration(
                            path,
                            title,
                            artist,
                            "ambiguous",
                            "multiple_matches",
                            candidates=cleaned[:10],
                        )
                        log_queue.put("[AMBIGUOUS] Multiple candidates found")
                else:
                    self._log_migration(
                        path, title, artist, "skipped", "low_confidence"
                    )
                    log_queue.put("[SKIPPED] Low Confidance")

            except Exception as e:
                log_queue.put(f"[ERROR] {filename}: {str(e)}")

            finally:
                log_queue.put("[MIGRATION] Completed")
                if save_logs:
                    self.log_manager.stop_logging(migration_id)

                self.active_downloads.pop(migration_id, None)
                log_queue.put("[END]")

    def _search_and_clean(
        self, query, title, artist, match_threshold, search_filter, log_queue=None
    ):
        results = self.ytmusic.search(query, filter=search_filter)
        if log_queue:
            log_queue.put(f"[RETRY] retrying result {results}")
        if not results:
            return []

        matches = self.filter_song_matches(results, title, artist)

        return [
            self.serialize_song(score, r)
            for score, r in matches
            if score >= match_threshold
        ]

    def serialize_song(self, score, r):
        thumbs = r.get("thumbnails") or []

        thumb_url = None

        if thumbs:
            # pick medium size if available, else first
            thumb_url = thumbs[-1].get("url")
        return {
            "score": round(score, 3),
            "title": r.get("title"),
            "artists": [a["name"] for a in r.get("artists", [])],
            "videoId": r.get("videoId"),
            "thumbnail": thumb_url,
        }

    def get_audio_metadata(self, path):
        try:
            audio = MutagenFile(path, easy=True)
            if not audio:
                raise Exception("Unsupported format")

            def tag(name):
                return audio.get(name, [None])[0]

            # MP3 (ID3)
            if path.lower().endswith(".mp3"):
                try:
                    id3 = ID3(path)
                except Exception:
                    pass

            return {
                "title": tag("title") or os.path.splitext(os.path.basename(path))[0],
                "artist": tag("artist") or "Unknown Artist",
            }

        except Exception:
            return None

    def title_similarity(self, a, b):
        return SequenceMatcher(None, a, b).ratio()

    def filter_song_matches(self, results, target_title, target_artist):
        target_title_n = target_title

        # Split artists by commas and normalize
        target_artist_parts = [p.strip().lower() for p in target_artist.split(",")]

        scored = []

        for r in results:
            # Get all artist names from result
            result_artists = [a["name"].lower() for a in r.get("artists", [])]

            # Calculate how many target artist parts match
            matching_parts = sum(
                1
                for part in target_artist_parts
                if any(part in artist or artist in part for artist in result_artists)
            )

            # Require at least one artist to match (or adjust threshold)
            if matching_parts == 0:
                continue

            result_title_n = r.get("title", "")
            score = self.title_similarity(target_title_n, result_title_n)

            # Bonus for more artist matches
            artist_match_ratio = matching_parts / len(target_artist_parts)
            adjusted_score = score * (0.7 + 0.3 * artist_match_ratio)  # Weighted

            scored.append((adjusted_score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    def _extract_video_id(self, base_name):
        """
        Returns existing videoId if filename already contains one.
        """
        YOUTUBE_ID_RE = re.compile(r"_(?P<id>[A-Za-z0-9_-]{11})$")
        match = YOUTUBE_ID_RE.search(base_name)
        return match.group("id") if match else None

    def _apply_migration(self, lyrics_dir, playlist_dir, path, video_id, log_queue):
        base, ext = os.path.splitext(path)
        dirname = os.path.dirname(path)
        filename = os.path.basename(base)

        existing_id = self._extract_video_id(filename)

        if existing_id == video_id:
            log_queue.put("[SKIP] Already migrated (same videoId)")
            self._log_migration(
                path,
                None,
                None,
                "skipped",
                "already_migrated",
                new_path=path,
                video_id=video_id,
            )
            return

        if existing_id and existing_id != video_id:
            log_queue.put(f"[UPDATE] Replacing videoId {existing_id} → {video_id}")
            clean_base = filename[: -(len(existing_id) + 1)]
        else:
            clean_base = filename

        new_filename = f"{clean_base}_{video_id}{ext}"
        new_path = os.path.join(dirname, new_filename)

        if os.path.exists(new_path):
            log_queue.put("[SKIP] Target file already exists")
            self._log_migration(
                path,
                None,
                None,
                "failed",
                "target_exists",
                new_path=new_path,
                video_id=video_id,
            )
            return

        os.rename(path, new_path)
        log_queue.put(f"[RENAMED] Audio → {new_filename}")

        self._migrate_lyrics(lyrics_dir, path, new_path, video_id, log_queue)
        self._migrate_playlists(playlist_dir, path, new_path, log_queue)

        self._log_migration(
            path,
            None,
            None,
            "migrated",
            "success",
            new_path=new_path,
            video_id=video_id,
        )

    def _migrate_lyrics(self, lyrics_dir, old_audio, new_audio, video_id, log_queue):
        if not lyrics_dir:
            return

        old_base = os.path.splitext(os.path.basename(old_audio))[0]
        new_base = os.path.splitext(os.path.basename(new_audio))[0]

        for ext in (".lrc", ".txt"):
            old_lyrics = os.path.join(lyrics_dir, old_base + ext)
            if not os.path.exists(old_lyrics):
                continue

            new_lyrics = os.path.join(lyrics_dir, new_base + ext)

            if os.path.exists(new_lyrics):
                log_queue.put("[SKIP] Lyrics already migrated")
                return

            try:
                os.rename(old_lyrics, new_lyrics)
                log_queue.put(f"[RENAMED] Lyrics → {os.path.basename(new_lyrics)}")
            except Exception as e:
                log_queue.put(f"[FAIL] Lyrics rename: {e}")

    def _migrate_playlists(self, playlist_dir, old_audio, new_audio, log_queue):
        if not playlist_dir:
            return

        updated = 0
        old_name = os.path.basename(old_audio)
        new_name = os.path.basename(new_audio)

        for root, _, files in os.walk(playlist_dir):
            for f in files:
                if not f.lower().endswith((".m3u", ".m3u8")):
                    continue

                playlist_path = os.path.join(root, f)

                try:
                    with open(playlist_path, "r", encoding="utf-8") as file:
                        lines = file.readlines()

                    changed = False
                    new_lines = []

                    for line in lines:
                        stripped = line.strip()

                        if stripped.endswith(old_name):
                            line = line.replace(old_name, new_name)
                            changed = True

                        new_lines.append(line)

                    if changed:
                        with open(playlist_path, "w", encoding="utf-8") as file:
                            file.writelines(new_lines)

                        updated += 1
                        log_queue.put(f"[PLAYLIST] Updated {f}")

                except Exception as e:
                    log_queue.put(f"[FAIL] Playlist {f}: {e}")

        if updated == 0:
            log_queue.put("[INFO] No playlist references found")

    def _log_migration(
        self,
        file_path,
        title,
        artist,
        status,
        reason,
        new_path=None,
        video_id=None,
        candidates=None,
    ):
        if not self.migration_logger:
            return
        entry = {
            "file": file_path,
            "new_file": new_path,
            "title": title,
            "artist": artist,
            "video_id": video_id,
            "status": status,
            "reason": reason,
            "candidates": candidates,
            "timestamp": datetime.now().isoformat(),
        }

        self.migration_logger.log_migration(entry)

    def _log_history(
        self,
        is_playlist,
        playlist_title,
        url,
        output_file,
        artist,
        lrc_file,
        quality,
        codec,
        status,
    ):
        """Create history log entry"""
        if not self.history_logger:
            return

        history_entry = {
            "type": "playlist" if is_playlist else "single",
            "playlist_title": playlist_title if is_playlist else "No Playlist",
            "url": url,
            "title": os.path.basename(output_file),
            "artist": artist,
            "file_path": output_file,
            "lyrics_path": lrc_file
            if lrc_file and os.path.exists(lrc_file)
            else "No Lyrics",
            "timestamp": datetime.now().isoformat(),
            "quality": quality,
            "format": codec,
            "status": status,
        }

        self.history_logger.log_download(history_entry)

    def _log_fail(
        self, is_playlist, playlist_title, index, url, quality, codec, status
    ):
        """Create Fail log entry"""
        if not self.fail_logger:
            return

        fail_entry = {
            "type": "playlist" if is_playlist else "single",
            "playlist_title": playlist_title if is_playlist else "No Playlist",
            "index": index,
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "quality": quality,
            "format": codec,
            "status": status,
        }

        self.fail_logger.log_fail(fail_entry)

    def get_logs(self, download_id):
        """Get logs for a specific download"""
        queue = self.log_queues.get(download_id)
        if not queue:
            return

        while True:
            try:
                # Block for a short time to wait for new messages
                message = queue.get(timeout=0.5)
                yield message
            except Empty:
                # Check if the download is still active
                if download_id not in self.active_downloads:
                    break
                # Continue waiting if download is still active
                continue
