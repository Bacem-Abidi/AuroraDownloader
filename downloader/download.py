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
from fail import FailLogger
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
        self.custom_temp_dir = "temp"
        os.makedirs(self.custom_temp_dir, exist_ok=True)
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config')

        
        # Initialize helper classes
        self.metadata_manager = MetadataManager(self.custom_temp_dir)
        self.lyrics_manager = LyricsManager()
        self.playlist_manager = PlaylistManager()
        self.thumbnail_manager = ThumbnailManager()
        self.mpd_manager = MPDManager()

    def start_download(self, url, download_id, quality='best', codec='mp3', 
                      audio_dir="Downloads", lyrics_dir="Lyrics", playlist_dir="Playlists",
                      playlist_options=None, mpd_options=None, history_dir=None, fail_dir=None,overwrite=False, resume=False, config_dir=None):
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
        log_queue = Queue()
        self.log_queues[download_id] = log_queue
        self.active_downloads[download_id] = True
        
        # Start the download in a new thread
        thread = threading.Thread(
            target=self._download_thread, 
            args=(url, download_id, log_queue, quality, codec, audio_dir, lyrics_dir,
                  playlist_dir,playlist_options, mpd_options,overwrite, resume),
            daemon=True
        )
        thread.start()
    
    def _download_thread(self, url, download_id, log_queue, quality, codec, audio_dir, 
                         lyrics_dir, playlist_dir, playlist_options, mpd_options, overwrite, resume=False):
        """The actual download thread"""
        thumbnail_path = None
        output_file = None
        playlist_files = []

        try:
            is_playlist = False
            playlist_title = "Playlist"

            if playlist_options is None:
                playlist_options = {
                    'relative_paths': True,
                    'filenames_only': False
                }

            if "list=" in url and "playlist" in url:
                is_playlist = True
                parsed_url = urlparse(url)
                query_params = parse_qs(parsed_url.query)
                playlist_id = query_params.get('list', [''])[0]

                # Get playlist metadata
                playlist_metadata_cmd = [
                    'yt-dlp',
                    f'https://www.youtube.com/playlist?list={playlist_id}',
                    '--dump-json',
                    '--flat-playlist'
                ]

                log_queue.put("[PLAYLIST] Retrieving playlist metadata...")
                result = subprocess.run(
                    playlist_metadata_cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )

                playlist_entries = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
                
                if playlist_entries:
                    playlist_title = playlist_entries[0].get('playlist_title', 'Playlist')
                    playlist_title = re.sub(r'[^\w\-_\. ]', '', playlist_title)  # Sanitize filename
                    log_queue.put(f"[PLAYLIST] Found {len(playlist_entries)} videos in '{playlist_title}'")
                else:
                    log_queue.put("[WARNING] Failed to get playlist metadata, using default")

            if is_playlist:
                log_queue.put(f"[PLAYLIST] Starting download of playlist: {playlist_title}")


                # Generate playlist file path
                playlist_file = os.path.join(playlist_dir, f"{playlist_title}.m3u")
                
                # Load existing playlist entries if resuming
                if resume and os.path.exists(playlist_file):
                    try:
                        with open(playlist_file, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith('#'):
                                    playlist_files.append(line)
                        log_queue.put(f"[PROGRESS] Loaded {len(playlist_files)} existing tracks from playlist")
                    except Exception as e:
                        log_queue.put(f"[WARNING] Failed to load existing playlist: {str(e)}")

                start_index = 0
                if resume:
                    progress = self.progress_tracker.get_progress(url)
                    if progress:
                        start_index = progress["last_index"] + 1
                        log_queue.put(f"[PROGRESS] Resuming from track {start_index+1}/{len(playlist_entries)}")
                    else:
                        log_queue.put("[PROGRESS] No progress found, starting from beginning")
                
                # Download each video in the playlist
                for i, entry in enumerate(playlist_entries):
                    if i < start_index:
                        continue

                    video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                    log_queue.put(f"[PLAYLIST] Downloading video {i+1}/{len(playlist_entries)}: {entry.get('title', 'Untitled')}")

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
                            url, 
                            playlist_title, 
                            i, 
                            len(playlist_entries)
                        )
                        
                        log_queue.put(f"[PLAYLIST] Completed video {i+1}/{len(playlist_entries)}")
                    else:
                        self._log_fail(
                            is_playlist,
                            playlist_title,
                            i+1,
                            video_url,
                            quality,
                            codec,
                            "Failed (didn't download for some reason)"
                        )
                        log_queue.put(f"[WARNING] Failed to download video {i+1}")

                # Create M3U playlist file
                if playlist_files:
                    self.playlist_manager.create_m3u_playlist(
                        playlist_title,
                        playlist_files,
                        playlist_dir,
                        playlist_options,
                        log_queue
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
                overwrite
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
            if mpd_options and mpd_options.get('update_mpd'):
                self.mpd_manager.update_mpd(mpd_options, log_queue)

            self.active_downloads.pop(download_id, None)
            log_queue.put("[END]")  # Signal end of stream


    
    def _download_video(self, url, log_queue, quality, codec, audio_dir, lyrics_dir, 
                       is_playlist, overwrite=False, playlist_title=None):
        """Download and process a single video using helper classes"""
        thumbnail_path = None
        output_file = None
        lrc_file = None
        
        try:
            # Get video metadata
            metadata = self.metadata_manager.get_video_metadata(url, log_queue)
            title = metadata['title']
            sanitized_title = metadata['sanitized_title']
            uploader = metadata['uploader']
            year = metadata['year']
            video_id = metadata['video_id']
            thumbnail_url = metadata['thumbnail_url']
            
            # Determine output filename
            extension = get_extension(codec)
            output_filename = f"{sanitized_title}.{extension}"
            output_path = os.path.join(audio_dir, output_filename)
            
            # Check if file exists and overwrite is disabled
            if os.path.exists(output_path) and not overwrite:
                log_queue.put(f"[SKIPPED] File exists: {output_filename}")
                self._log_history(is_playlist, playlist_title, url, output_path, 
                                uploader, lrc_file, quality, codec, 'skipped')
                return output_path

            # Download thumbnail
            thumbnail_path = self.thumbnail_manager.download_thumbnail(
                thumbnail_url, 
                log_queue
            ) if thumbnail_url else None

            # Get lyrics
            lyrics = self.lyrics_manager.get_lyrics(
                title, 
                uploader, 
                video_id, 
                log_queue
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
                sanitized_title
            )
            log_queue.put(f"[COMMAND] {' '.join(cmd)}")
            
            # Execute download command
            output_file = self._execute_download_command(
                cmd, 
                audio_dir, 
                sanitized_title, 
                extension, 
                log_queue
            )
            
            if output_file:
                # Embed thumbnail if available
                if thumbnail_path:
                    self.thumbnail_manager.embed_thumbnail(
                        output_file, 
                        thumbnail_path, 
                        codec, 
                        log_queue
                    )
                
                # Save lyrics
                if lyrics:
                    base_name = os.path.splitext(os.path.basename(output_file))[0]
                    lrc_file = os.path.join(lyrics_dir, f"{base_name}.lrc")
                    
                    with open(lrc_file, "w", encoding="utf-8") as f:
                        f.write(lyrics)
                    
                    log_queue.put(f"[LYRICS] Saved lyrics to {os.path.basename(lrc_file)}")
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
                    'downloaded'
                )
                
            else:
                self._log_fail(
                    is_playlist,
                    playlist_title,
                    None,
                    url,
                    quality,
                    codec,
                    "Failed (didn't download for some reason)"
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



    def _build_download_command(self, url, quality_setting, codec, audio_dir, year,artist, title, sanitized_title):
        """Construct the yt-dlp command with appropriate parameters"""
        cmd = [
            'yt-dlp',
            url,
            '--extract-audio',
            '--audio-format', codec,
            '--audio-quality', quality_setting,
            '--embed-metadata',
            '--add-metadata',
            '--parse-metadata', f'title:{title}',
            '--parse-metadata', f'uploader:{artist}',
            # '--output', f'{audio_dir}/%(title)s.%(ext)s',
            '-o', f'{audio_dir}/{sanitized_title}.%(ext)s',
            '--verbose',
            '--no-simulate',
            '--newline',
        ]
        
        # Add year if available
        if year:
            cmd.extend(['--parse-metadata', f'{year}:%(meta_year)s'])
        
        # Special handling for certain codecs
        if codec == 'flac':
            cmd.extend(['--audio-quality', '0'])  # FLAC is lossless
            cmd.extend(['--postprocessor-args', '-c:a flac -compression_level 12'])
        elif codec == 'wav':
            cmd.extend(['--postprocessor-args', '-c:a pcm_s16le'])
        elif codec == 'opus':
            cmd.extend(['--postprocessor-args', '-b:a ' + quality_setting])
        
        return cmd

    def _execute_download_command(self, cmd, audio_dir, title, extension, log_queue):
        """Run the download command and process output"""
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Stream output in real-time
        for line in process.stdout:
            cleaned_line = line.strip()
            if cleaned_line:
                # Simplify verbose messages
                if 'Deleting original file' in cleaned_line:
                    cleaned_line = '[CLEANUP] Deleting temporary files'
                elif 'Embedding metadata' in cleaned_line:
                    cleaned_line = '[METADATA] Embedding metadata'
                elif 'Embedding thumbnail' in cleaned_line:
                    cleaned_line = '[METADATA] Embedding thumbnail'
                
                log_queue.put(cleaned_line)
        
        process.wait()
        
        if process.returncode != 0:
            log_queue.put(f"[ERROR] Download failed with code {process.returncode}")
            return None
        
        # Find the downloaded file
        output_files = [
            f for f in os.listdir(audio_dir)
            if f.endswith(f'.{extension}') and title in f
        ]
        
        if not output_files:
            log_queue.put("[ERROR] Downloaded file not found")
            return None
        
        output_file = os.path.join(audio_dir, output_files[0])
        log_queue.put(f"[SUCCESS] Audio downloaded: {output_files[0]}")
        return output_file

    def _log_history(self, is_playlist, playlist_title, url, output_file, 
                    artist, lrc_file, quality, codec, status):
        """Create history log entry"""
        if not self.history_logger:
            return
        
        history_entry = {
            'type': 'playlist' if is_playlist else 'single',
            'playlist_title': playlist_title if is_playlist else 'No Playlist',
            'url': url,
            'title': os.path.basename(output_file),
            'artist': artist,
            'file_path': output_file,
            'lyrics_path': lrc_file if lrc_file and os.path.exists(lrc_file) else 'No Lyrics',
            'timestamp': datetime.now().isoformat(),
            'quality': quality,
            'format': codec,
            'status': status
        }
        
        self.history_logger.log_download(history_entry)

    def _log_fail(self, is_playlist, playlist_title, index,  url, 
                     quality, codec, status):
        """Create Fail log entry"""
        if not self.fail_logger:
            return
        
        fail_entry = {
            'type': 'playlist' if is_playlist else 'single',
            'playlist_title': playlist_title if is_playlist else 'No Playlist',
            'index': index,
            'url': url,
            'timestamp': datetime.now().isoformat(),
            'quality': quality,
            'format': codec,
            'status': status
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
