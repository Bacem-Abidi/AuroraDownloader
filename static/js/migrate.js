document.addEventListener("DOMContentLoaded", () => {
  const threshold = document.getElementById("strong-match-threshold");
  const valueLabel = document.getElementById("threshold-value");

  threshold.addEventListener("input", () => {
    valueLabel.textContent = threshold.value + "%";
  });

  const audioDirInput = document.getElementById("audio-migrate-dir");
  const lyricsDirInput = document.getElementById("lyrics-migrate-dir");
  const playlistDirInput = document.getElementById("playlist-migrate-dir");
  const matchThresholdInput = document.getElementById("strong-match-threshold");
  const fallbackInput = document.getElementById("fallback-policy");

  async function loadPreferences() {
    try {
      const response = await fetch("/preferences");
      const prefs = await response.json();

      audioDirInput.value = prefs.audioDir;
      lyricsDirInput.value = prefs.lyricsDir;
      playlistDirInput.value = prefs.playlistDir;

      matchThresholdInput.value = prefs.matchThreshold;
      valueLabel.textContent = prefs.matchThreshold + "%";
      fallbackInput.value = prefs.fallback;
    } catch (e) {
      console.error("Error loading preferences:", e);
    }
  }

  loadPreferences();
});
