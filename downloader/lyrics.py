from ytmusicapi import YTMusic

class LyricsManager:
    def __init__(self):
        self.ytmusic = YTMusic()

    def get_lyrics(self, title, artist, video_id, log_queue):
        try:
            log_queue.put("[LYRICS] Searching for lyrics...")
            lyrics_id = self.ytmusic.get_watch_playlist(video_id, limit=1)
            lyrics_data = self.ytmusic.get_lyrics(lyrics_id["lyrics"], timestamps=True)
            
            if not lyrics_data or not lyrics_data.get('lyrics'):
                log_queue.put("[LYRICS] Lyrics not available for this track")
                return None
                
            return self._format_lrc_lyrics(
                lyrics_data['lyrics'],
                title,
                artist,
                lyrics_data.get('source', 'YouTube Music')
            )
        except Exception as e:
            log_queue.put(f"[WARNING] Lyrics search failed: {str(e)}")
            return None

    def _format_lrc_lyrics(self, lines, title, artist, source):
        """Convert lyrics data to LRC format"""
        lrc_content = [
            f"[ar:{artist}]",
            f"[ti:{title}]",
            f"[al:YouTube Download]",
            f"[by:{source}]",
            f"[re:https://music.youtube.com]",
            f"[ve:1.0]"
        ]
        
        # Add lyrics lines with timestamps
        for line in lines:
            text = line.text
            start_time = line.start_time if hasattr(line, 'start_time') else line.startTimeMs
            
            # Convert milliseconds to [mm:ss.xx] format
            minutes = start_time // 60000
            seconds = (start_time % 60000) // 1000
            centiseconds = (start_time % 1000) // 10
            timestamp = f"[{minutes:02d}:{seconds:02d}.{centiseconds:02d}]"
            lrc_content.append(f"{timestamp}{text}")
        
        return "\n".join(lrc_content)
