document.addEventListener("DOMContentLoaded", () => {
  const downloadBtn = document.getElementById("download-btn");
  const youtubeUrl = document.getElementById("youtube-url");
  const logOutput = document.getElementById("log-output");
  const clearLogsBtn = document.getElementById("clear-logs");

  const audioDirInput = document.getElementById("audio-dir");
  const lyricsDirInput = document.getElementById("lyrics-dir");
  const playlistDirInput = document.getElementById("playlist-dir");

  const relativePathsCheckbox = document.getElementById("relative-paths");
  const filenameOnlyCheckbox = document.getElementById("filename-only");
  const playlistOptions = document.getElementById("playlist-options");

  const updateMpdCheckbox = document.getElementById("update-mpd");
  const mpdAdvancedSection = document.getElementById("mpd-advanced");

  // Advanced Panel Elements
  const defaultConfigToggle = document.getElementById("defaults-toggle");
  const defaultConfigPanel = document.getElementById("defaults-panel");
  const defaultConfigChevron = document.getElementById("defaults-chevron");
  const saveDefaultsBtn = document.getElementById("save-defaults");

  // Load saved preferences
  async function loadPreferences() {
    try {
      const response = await fetch("/preferences");
      const prefs = await response.json();

      // Apply preferences to form fields
      document.getElementById("audio-quality").value = prefs.audioQuality;
      document.getElementById("audio-quality-default").value =
        prefs.audioQuality;

      document.getElementById("audio-codec").value = prefs.audioCodec;
      document.getElementById("audio-codec-default").value = prefs.audioCodec;

      document.getElementById("audio-dir").value = prefs.audioDir;
      document.getElementById("audio-dir-default").value = prefs.audioDir;

      document.getElementById("lyrics-dir").value = prefs.lyricsDir;
      document.getElementById("lyrics-dir-default").value = prefs.lyricsDir;

      document.getElementById("playlist-dir").value = prefs.playlistDir;
      document.getElementById("playlist-dir-default").value = prefs.playlistDir;

      document.getElementById("update-mpd").checked = prefs.updateMpd;
      document.getElementById("update-mpd-default").checked = prefs.updateMpd;
      document.getElementById("mpd-advanced").style.display = prefs.updateMpd
        ? "block"
        : "none";
      document.getElementById("mpd-advanced-default").style.display =
        prefs.updateMpd ? "block" : "none";

      document.getElementById("mpc-path").value = prefs.mpcPath;
      document.getElementById("mpc-path").value = prefs.mpcPath;

      document.getElementById("mpc-command").value = prefs.mpcCommand;
      document.getElementById("mpc-command-default").value = prefs.mpcCommand;

      console.log("Preferences loaded successfully");
    } catch (e) {
      console.error("Error loading preferences:", e);
    }
  }

  // Save preferences to localStorage
  async function savePreferences() {
    const preferences = {
      audioQuality: document.getElementById("audio-quality-default").value,
      audioCodec: document.getElementById("audio-codec-default").value,
      audioDir: document.getElementById("audio-dir-default").value,
      lyricsDir: document.getElementById("lyrics-dir-default").value,
      playlistDir: document.getElementById("playlist-dir-default").value,
      updateMpd: document.getElementById("update-mpd-default").checked,
      mpcPath: document.getElementById("mpc-path-default").value,
      mpcCommand: document.getElementById("mpc-command-default").value,
    };
    try {
      const response = await fetch("/preferences", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(preferences),
      });

      const result = await response.json();
      if (response.ok) {
        showToast("Settings saved successfully!");
      } else {
        showToast(`Error: ${result.error}`, true);
      }
    } catch (e) {
      console.error("Error saving preferences:", e);
      showToast("Failed to save settings", true);
    }
  }

  // Show toast notification
  function showToast(message) {
    // Create toast element if it doesn't exist
    let toast = document.getElementById("toast-notification");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "toast-notification";
      toast.className = "toast";
      document.body.appendChild(toast);
    }

    toast.textContent = message;
    toast.style.display = "block";

    // Hide after 3 seconds
    setTimeout(() => {
      toast.style.display = "none";
    }, 3000);
  }

  // Toggle advanced panel
  defaultConfigToggle.addEventListener("click", () => {
    if (defaultConfigPanel.style.display === "none") {
      defaultConfigPanel.style.display = "block";
      defaultConfigChevron.className = "fas fa-chevron-up";
    } else {
      defaultConfigPanel.style.display = "none";
      defaultConfigChevron.className = "fas fa-chevron-down";
    }
  });

  // Save defaults button
  saveDefaultsBtn.addEventListener("click", savePreferences);

  // Load preferences when page loads
  loadPreferences();

  // Current download ID
  let currentDownloadId = null;
  let eventSource = null;

  youtubeUrl.addEventListener("input", () => {
    const url = youtubeUrl.value;
    if (url.includes("list=") && url.includes("playlist")) {
      playlistOptions.style.display = "block";
    } else {
      playlistOptions.style.display = "none";
    }
  });
  // Ensure only one option is selected
  relativePathsCheckbox.addEventListener("change", () => {
    if (relativePathsCheckbox.checked) {
      filenameOnlyCheckbox.checked = false;
    }
  });

  filenameOnlyCheckbox.addEventListener("change", () => {
    if (filenameOnlyCheckbox.checked) {
      relativePathsCheckbox.checked = false;
    }
  });

  updateMpdCheckbox.addEventListener("change", () => {
    mpdAdvancedSection.style.display = updateMpdCheckbox.checked
      ? "block"
      : "none";
  });

  // Add log entry to the UI
  function addLog(message, type = "info") {
    const logEntry = document.createElement("div");
    logEntry.className = `log-entry log-${type}`;

    // Auto-detect log types based on content
    if (message.includes("[ERROR]")) {
      logEntry.classList.add("log-error");
    } else if (message.includes("[WARNING]")) {
      logEntry.classList.add("log-warning");
    } else if (message.includes("[SUCCESS]")) {
      logEntry.classList.add("log-success");
    } else if (message.includes("[DOWNLOAD]")) {
      logEntry.classList.add("log-download");
    } else if (message.includes("[CONVERT]")) {
      logEntry.classList.add("log-convert");
    } else if (
      message.includes("[METADATA]") ||
      message.includes("[THUMBNAIL]") ||
      message.includes("[LYRICS]")
    ) {
      logEntry.classList.add("log-metadata");
    } else if (
      message.startsWith("[MPD]") &&
      !message.includes("successfully")
    ) {
      updateMpdStatus("In progress...", message.replace("[mpd]", ""));
    } else if (message.startsWith("[ERROR] MPD")) {
      updateMpdStatus("Failed", message);
    } else if (message.includes("[MPD] Library updated successfully")) {
      updateMpdStatus("Completed", message.replace("[mpd]", ""));
    }

    logEntry.textContent = message;
    logOutput.appendChild(logEntry);
    logOutput.scrollTop = logOutput.scrollHeight;
  }

  // Start download process
  downloadBtn.addEventListener("click", async () => {
    const url = youtubeUrl.value.trim();

    const quality = document.getElementById("audio-quality").value;
    const codec = document.getElementById("audio-codec").value;

    const audioDir = audioDirInput.value || "Downloads";
    const lyricsDir = lyricsDirInput.value || "Lyrics";
    const playlistDir = playlistDirInput.value || "Playlists";

    const useRelativePaths = relativePathsCheckbox.checked;
    const useFilenames = filenameOnlyCheckbox.checked;

    const updateMpd = updateMpdCheckbox.checked;
    const mpcPath = document.getElementById("mpc-path").value;
    const mpcCommand = document.getElementById("mpc-command").value;

    const overwriteFiles = document.getElementById("overwrite-files").checked;
    const resumeDownload = document.getElementById("resume-download").checked;

    if (!url) {
      addLog("[ERROR] Please enter a YouTube URL", "error");
      return;
    }

    // Disable button during download
    downloadBtn.disabled = true;
    downloadBtn.innerHTML =
      '<i class="fas fa-spinner fa-spin"></i> Downloading...';

    // Clear any previous logs
    if (currentDownloadId) {
      closeEventSource();
    }

    // Clear log output
    logOutput.innerHTML = "";
    addLog(`[INFO] Starting download for: ${url}`);

    try {
      // Start the download
      const response = await fetch("/start_download", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          url: url,
          quality: quality, // Send quality to backend
          codec: codec,
          audio_dir: audioDir,
          lyrics_dir: lyricsDir,
          playlist_dir: playlistDir,
          playlist_options: {
            relative_paths: useRelativePaths,
            filenames_only: useFilenames,
          },
          mpd_options: {
            update_mpd: updateMpd,
            mpc_path: mpcPath,
            mpc_command: mpcCommand,
          },
          overwrite: overwriteFiles,
          resume: resumeDownload,
        }),
      });

      const data = await response.json();

      if (data.download_id) {
        currentDownloadId = data.download_id;
        startLogStream(currentDownloadId);
      } else {
        throw new Error("Failed to start download");
      }
    } catch (error) {
      addLog(`[ERROR] ${error.message}`, "error");
      downloadBtn.disabled = false;
      downloadBtn.innerHTML = '<i class="fas fa-download"></i> Download';
    }
  });

  function updatePlaylistProgress(current, total, title) {
    const status = document.getElementById("playlist-status");
    const progressText = document.getElementById("playlist-progress-text");
    const progressBar = document.getElementById("playlist-progress-bar");
    const titleElement = document.getElementById("playlist-title");

    status.style.display = "block";
    progressText.textContent = `${current}/${total}`;
    titleElement.textContent = title || "Untitled Playlist";

    const percentage = total > 0 ? (current / total) * 100 : 0;
    progressBar.style.width = `${percentage}%`;
  }

  function updateMpdStatus(message, output = "") {
    const mpdStatus = document.getElementById("mpd-status");
    const mpdStatusText = document.getElementById("mpd-status-text");
    const mpdOutput = document.getElementById("mpd-output");

    mpdStatus.style.display = "block";
    mpdStatusText.textContent = message;
    mpdOutput.textContent = output;
  }

  // Start listening to the log stream
  function startLogStream(downloadId) {
    closeEventSource();

    eventSource = new EventSource(`/logs/${downloadId}`);

    eventSource.onmessage = (event) => {
      const message = event.data;

      const playlistMatch = message.match(
        /\[PLAYLIST\] Downloading video (\d+)\/(\d+): (.+)/,
      );
      if (playlistMatch) {
        const current = parseInt(playlistMatch[1]);
        const total = parseInt(playlistMatch[2]);
        const title = playlistMatch[3];
        updatePlaylistProgress(current, total, title);
      }
      if (message === "[END]") {
        // Download completed
        closeEventSource();
        downloadBtn.disabled = false;
        downloadBtn.innerHTML = '<i class="fas fa-download"></i> Download';
      } else {
        addLog(message);
      }
    };

    eventSource.onerror = (error) => {
      console.error("EventSource error:", error);
      addLog("[ERROR] Connection to log stream failed", "error");
      closeEventSource();
      downloadBtn.disabled = false;
      downloadBtn.innerHTML = '<i class="fas fa-download"></i> Download';
    };
  }

  // Close the event source connection
  function closeEventSource() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    currentDownloadId = null;
  }

  // Clear logs button
  clearLogsBtn.addEventListener("click", () => {
    logOutput.innerHTML = "";
    addLog("[INFO] Logs cleared", "info");
  });
});
