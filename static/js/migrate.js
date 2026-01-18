document.addEventListener("DOMContentLoaded", () => {
  const {
    addLog,
    startLogStream,
    closeEventSource,
    disableManagementTab,
    enableManagementTab,
    logOutput,
    getCurrentDownloadId,
    setCurrentDownloadId,
  } = window.App;

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

  const migrateBtn = document.getElementById("start-migration-btn");

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

  migrateBtn.addEventListener("click", async () => {
    const match_perc = matchThresholdInput.value;
    const audioDir = audioDirInput.value || "Downloads";
    const lyricsDir = lyricsDirInput.value || "Lyrics";
    const playlistDir = playlistDirInput.value || "Playlists";

    // Disable button during download
    migrateBtn.disabled = true;
    migrateBtn.innerHTML =
      '<i class="fas fa-spinner fa-spin"></i> Migrating...';

    // Disable management tab during download
    disableManagementTab();

    // Clear any previous logs
    if (getCurrentDownloadId()) {
      closeEventSource();
    }

    // Clear log output
    logOutput.innerHTML = "";
    addLog(`[INFO] Starting Migrating for directory: ${audioDir}`);

    try {
      // Start the download
      const response = await fetch("/migrate/start", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          audio_dir: audioDir,
          lyrics_dir: lyricsDir,
          playlist_dir: playlistDir,
          match_perc: match_perc,
        }),
      });

      const data = await response.json();

      if (data.migration_id) {
        setCurrentDownloadId(data.migration_id);
        startLogStream(getCurrentDownloadId());
      } else {
        throw new Error("Failed to start migrating");
      }
    } catch (error) {
      addLog(`[ERROR] ${error.message}`, "error");
      migrateBtn.disabled = false;
      migrateBtn.innerHTML = '<i class="fas fa-random"></i> Start Migration';
      enableManagementTab();
    }
  });
});
