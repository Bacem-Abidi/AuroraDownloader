# metadata_helpers.py
import os
import re
import json
import tempfile
import requests
from io import BytesIO
from PIL import Image
from mutagen import File as MutagenFile
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from mutagen.flac import Picture
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TYER, TDRC, APIC


def update_audio_metadata(file_path, metadata):
    """Update metadata for various audio formats"""
    try:
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext in [".mp3"]:
            return update_mp3_metadata(file_path, metadata)
        elif file_ext in [".m4a", ".mp4"]:
            return update_m4a_metadata(file_path, metadata)
        elif file_ext in [".flac"]:
            return update_flac_metadata(file_path, metadata)
        else:
            return update_generic_metadata(file_path, metadata)

    except Exception as e:
        print(f"Error updating metadata for {file_path}: {e}")
        import traceback

        traceback.print_exc()
        return False


def update_mp3_metadata(file_path, metadata):
    """Update ID3 tags for MP3 files"""
    try:
        # Create ID3 object with UTF-8 encoding
        try:
            audio = ID3(file_path)
        except Exception:
            audio = ID3()

        encoding = 3  # UTF-8

        print(f"Updating MP3 metadata for {os.path.basename(file_path)}:")

        # Update title
        if "title" in metadata and metadata["title"]:
            title = str(metadata["title"]).strip()
            if title:
                audio["TIT2"] = TIT2(encoding=encoding, text=title)
                print(f"  Title: {title}")

        # Update artist
        if "artist" in metadata and metadata["artist"]:
            artist = str(metadata["artist"]).strip()
            if artist:
                audio["TPE1"] = TPE1(encoding=encoding, text=artist)
                print(f"  Artist: {artist}")

        # Update album
        if "album" in metadata and metadata["album"]:
            album = str(metadata["album"]).strip()
            if album:
                audio["TALB"] = TALB(encoding=encoding, text=album)
                print(f"  Album: {album}")

        # Update year - handle various formats
        if "year" in metadata and metadata["year"]:
            year_str = str(metadata["year"]).strip()

            if year_str:
                print(f"  Year input: {year_str}")

                # Try to extract year from various formats
                year_value = None

                # Try YYYY format
                if re.match(r"^\d{4}$", year_str):
                    year_value = year_str
                # Try YYYYMMDD format
                elif re.match(r"^\d{8}$", year_str):
                    year_value = year_str[:4]
                # Try to find any 4-digit year in the string
                else:
                    year_match = re.search(r"\b(19|20)\d{2}\b", year_str)
                    if year_match:
                        year_value = year_match.group()

                if year_value:
                    # Update TYER (Year)
                    audio["TYER"] = TYER(encoding=encoding, text=year_value)

                    # Update TDRC (Recording time) - modern standard
                    audio["TDRC"] = TDRC(encoding=encoding, text=year_value)

                    print(f"  Year set to: {year_value}")
                else:
                    print(f"  Warning: Could not parse year from '{year_str}'")

        # Save to file
        audio.save(file_path, v2_version=3)  # Use ID3v2.3 for better compatibility
        print(f"  Successfully saved metadata")
        return True

    except Exception as e:
        print(f"Error updating MP3 metadata for {file_path}: {e}")
        import traceback

        traceback.print_exc()
        return False


def update_m4a_metadata(file_path, metadata):
    """Update metadata for M4A files"""
    try:
        audio = MP4(file_path)

        # Map metadata keys to MP4 tags
        tag_map = {
            "title": "\xa9nam",
            "artist": "\xa9ART",
            "album": "\xa9alb",
            "year": "\xa9day",
        }

        for key, value in metadata.items():
            if key in tag_map and value:
                audio[tag_map[key]] = [str(value)]

        audio.save()
        return True
    except Exception as e:
        print(f"Error updating M4A metadata: {e}")
        import traceback

        traceback.print_exc()
        return False


def update_flac_metadata(file_path, metadata):
    """Update metadata for FLAC files"""
    try:
        audio = FLAC(file_path)

        if "title" in metadata and metadata["title"]:
            audio["title"] = str(metadata["title"])
        if "artist" in metadata and metadata["artist"]:
            audio["artist"] = str(metadata["artist"])
        if "album" in metadata and metadata["album"]:
            audio["album"] = str(metadata["album"])
        if "year" in metadata and metadata["year"]:
            audio["date"] = str(metadata["year"])

        audio.save()
        return True
    except Exception as e:
        print(f"Error updating FLAC metadata: {e}")
        import traceback

        traceback.print_exc()
        return False


def update_generic_metadata(file_path, metadata):
    """Fallback for other audio formats using mutagen"""
    try:
        audio = MutagenFile(file_path, easy=True)

        if audio is None:
            return False

        if "title" in metadata and metadata["title"]:
            audio["title"] = str(metadata["title"])
        if "artist" in metadata and metadata["artist"]:
            audio["artist"] = str(metadata["artist"])
        if "album" in metadata and metadata["album"]:
            audio["album"] = str(metadata["album"])
        if "year" in metadata and metadata["year"]:
            audio["date"] = str(metadata["year"])

        audio.save()
        return True
    except Exception as e:
        print(f"Error updating generic metadata: {e}")
        import traceback

        traceback.print_exc()
        return False


def embed_artwork_from_file(file_path, artwork_file):
    """Embed artwork from uploaded file"""
    try:
        print(f"Processing uploaded artwork file: {artwork_file.filename}")

        # Read the file data
        img_data = artwork_file.read()

        if not img_data:
            print("  Error: Empty file")
            return False

        print(f"  File size: {len(img_data)} bytes")

        # Process and embed the image
        success = _embed_artwork_from_bytes(file_path, img_data)

        if success:
            print(f"  Successfully embedded artwork from file")
        else:
            print(f"  Failed to process uploaded file")

        return success

    except Exception as e:
        print(f"Error embedding artwork from file: {e}")
        import traceback

        traceback.print_exc()
        return False


def embed_artwork_from_url(file_path, url):
    """Embed artwork from URL"""
    try:
        print(f"Downloading artwork from URL: {url}")

        # Download image
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get("content-type", "")
        print(f"  Content-Type: {content_type}")

        # Read image data
        img_data = response.content

        # Process and embed the image
        success = _embed_artwork_from_bytes(file_path, img_data)

        if success:
            print(f"  Successfully embedded artwork from URL")
        else:
            print(f"  Failed to process image from URL")

        return success

    except requests.exceptions.RequestException as e:
        print(f"Error downloading artwork from URL {url}: {e}")
        return False
    except Exception as e:
        print(f"Error embedding artwork from URL {url}: {e}")
        import traceback

        traceback.print_exc()
        return False


def remove_artwork(file_path):
    """Remove artwork from audio file"""
    try:
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext in [".mp3"]:
            audio = ID3(file_path)
            # Remove all APIC (picture) frames
            audio.delall("APIC")
            audio.save(file_path, v2_version=3)
            return True
        elif file_ext in [".m4a", ".mp4"]:
            audio = MP4(file_path)
            # Remove covr (cover art) atom
            if "covr" in audio:
                del audio["covr"]
                audio.save()
            return True
        elif file_ext in [".flac"]:
            audio = FLAC(file_path)
            # Remove all pictures
            audio.clear_pictures()
            audio.save()
            return True
        else:
            # Generic mutagen
            audio = MutagenFile(file_path)
            if audio:
                # Try to remove common picture tags
                for key in list(audio.keys()):
                    if "APIC" in key or "PIC" in key or "covr" in key:
                        del audio[key]
                audio.save()
            return True

    except Exception as e:
        print(f"Error removing artwork: {e}")
        import traceback

        traceback.print_exc()
        return False


def _embed_artwork_from_bytes(file_path, image_bytes):
    """Helper function to embed artwork from image bytes"""
    try:
        # Load image from bytes
        img = Image.open(BytesIO(image_bytes))

        print(f"  Image format: {img.format}, size: {img.size}, mode: {img.mode}")

        # Convert to RGB if necessary
        if img.mode == "RGBA":
            # Create a white background
            background = Image.new("RGB", img.size, (255, 255, 255))
            # Paste the image on the background
            background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Resize if too large (max 1000x1000)
        max_size = 1000
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            print(f"  Resized to: {img.size}")

        # Save processed image to bytes as JPEG
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG", quality=90)
        img_data = img_bytes.getvalue()

        print(f"  Processed image size: {len(img_data)} bytes")

        # Embed based on file type
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext in [".mp3"]:
            audio = ID3(file_path)
            # Remove existing artwork
            audio.delall("APIC")
            # Add new artwork
            audio.add(
                APIC(
                    encoding=3,  # UTF-8
                    mime="image/jpeg",
                    type=3,  # Cover (front)
                    desc="Cover",
                    data=img_data,
                )
            )
            audio.save(file_path, v2_version=3)
            return True

        elif file_ext in [".m4a", ".mp4"]:
            audio = MP4(file_path)
            audio["covr"] = [img_data]
            audio.save()
            return True

        elif file_ext in [".flac"]:
            audio = FLAC(file_path)
            audio.clear_pictures()

            picture = Picture()
            picture.type = 3  # Front cover
            picture.mime = "image/jpeg"
            picture.desc = "Cover"
            picture.data = img_data

            audio.add_picture(picture)
            audio.save()
            return True

        else:
            # Generic mutagen
            audio = MutagenFile(file_path)
            if audio:
                # Try to embed using easy method
                audio["APIC"] = img_data
                audio.save()
            return True

    except Exception as e:
        print(f"Error embedding artwork: {e}")
        import traceback

        traceback.print_exc()
        return False
