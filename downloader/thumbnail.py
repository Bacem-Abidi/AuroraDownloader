import os
import requests
import tempfile
import subprocess

class ThumbnailManager:
    def __init__(self, temp_dir="temp"):
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)

    def download_thumbnail(self, url, log_queue):
        if not url:
            log_queue.put("[WARNING] No thumbnail available for this video")
            return None

        try:
            log_queue.put("[THUMBNAIL] Downloading cover art...")
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False, dir=self.temp_dir) as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                thumbnail_path = temp_file.name
            
            log_queue.put(f"[THUMBNAIL] Saved to: {thumbnail_path}")
            return thumbnail_path
        except Exception as e:
            log_queue.put(f"[ERROR] Thumbnail download failed: {str(e)}")
            return None

    def embed_thumbnail(self, audio_file, thumbnail_path, codec, log_queue):
        """Embed thumbnail into audio file using FFmpeg with format-specific handling"""
        if not thumbnail_path or not os.path.exists(thumbnail_path):
            log_queue.put("[WARNING] Thumbnail file not found, skipping embedding")
            return False
        
        if not os.path.exists(audio_file):
            log_queue.put("[ERROR] Audio file not found for thumbnail embedding")
            return False

        try:
            log_queue.put(f"[THUMBNAIL] Embedding cover art for {codec.upper()} file...")
            
            # Create temporary output file
            base_name = os.path.splitext(audio_file)[0]
            temp_output = f"{base_name}_temp.{codec}"
            
            # Build FFmpeg command based on codec
            if codec in ['mp3', 'flac', 'wav']:
                ffmpeg_cmd = self._build_id3_command(audio_file, thumbnail_path, temp_output, codec)
            elif codec in ['aac', 'm4a']:
                ffmpeg_cmd = self._build_mp4_command(audio_file, thumbnail_path, temp_output)
            elif codec == 'opus':
                ffmpeg_cmd = self._build_opus_command(audio_file, thumbnail_path, temp_output)
            else:
                log_queue.put(f"[WARNING] Thumbnail embedding not supported for {codec} format")
                return False

            # Execute FFmpeg command
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Replace original file with tagged version
                os.replace(temp_output, audio_file)
                log_queue.put("[THUMBNAIL] Cover art embedded successfully")
                return True
            else:
                log_queue.put(f"[ERROR] FFmpeg failed: {result.stderr}")
                # Clean up temporary file
                if os.path.exists(temp_output):
                    os.remove(temp_output)
                return False

        except Exception as e:
            log_queue.put(f"[ERROR] Thumbnail embedding failed: {str(e)}")
            return False
        finally:
            # Clean up thumbnail file
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
                log_queue.put("[THUMBNAIL] Temporary thumbnail deleted")

    def _build_id3_command(self, audio_file, thumbnail_path, temp_output, codec):
        """Build command for ID3-tag based formats (MP3, FLAC, WAV)"""
        cmd = [
            'ffmpeg',
            '-y',
            '-i', audio_file,
            '-i', thumbnail_path,
            '-map', '0',
            '-map', '1',
            '-c:a', 'copy',
            '-c:v:1', 'mjpeg',
            '-id3v2_version', '3',
            '-metadata:s:v', 'title="Album cover"',
            '-metadata:s:v', 'comment="Cover (front)"',
            '-disposition:v:1', 'attached_pic',
            temp_output
        ]
        
        # FLAC needs special handling
        if codec == 'flac':
            cmd = [
                'ffmpeg',
                '-y',
                '-i', audio_file,
                '-i', thumbnail_path,
                '-map', '0:a',
                '-map', '1:v',
                '-c:a', 'copy',
                '-c:v', 'copy',
                '-metadata', 'comment="Cover (front)"',
                '-disposition:v', 'attached_pic',
                temp_output
            ]
            
        return cmd

    def _build_mp4_command(self, audio_file, thumbnail_path, temp_output):
        """Build command for MP4-based formats (AAC, M4A)"""
        return [
            'ffmpeg',
            '-y',
            '-i', audio_file,
            '-i', thumbnail_path,
            '-map', '0:a',
            '-map', '1:v',
            '-c:a', 'copy',
            '-c:v', 'copy',
            '-disposition:v', 'attached_pic',
            '-metadata', 'comment="Cover (front)"',
            temp_output
        ]

    def _build_opus_command(self, audio_file, thumbnail_path, temp_output):
        """Build command for Opus format"""
        return [
            'ffmpeg',
            '-y',
            '-i', audio_file,
            '-i', thumbnail_path,
            '-map', '0',
            '-map', '1',
            '-c:a', 'copy',
            '-c:v', 'copy',
            '-metadata', 'METADATA_BLOCK_PICTURE=' + self._create_opus_metadata(thumbnail_path),
            temp_output
        ]

    def _create_opus_metadata(self, image_path):
        """Generate Opus metadata block for cover art (simplified)"""
        # In a real implementation, this would encode the image and create the metadata block
        # For simplicity, we'll just return a placeholder
        return "cover_front"
