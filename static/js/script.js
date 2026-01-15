document.addEventListener("DOMContentLoaded", () => {
  const downloadBtn = document.getElementById("download-btn");
  const youtubeUrl = document.getElementById("youtube-url");
  const logOutput = document.getElementById("log-output");
  const clearLogsBtn = document.getElementById("clear-logs");

  const audioDirInput = document.getElementById("audio-dir");
  const lyricsDirInput = document.getElementById("lyrics-dir");
  const playlistDirInput = document.getElementById("playlist-dir");

  const absolutePathsCheckbox = document.getElementById("absolute-paths");
  const relativePathsCheckbox = document.getElementById("relative-paths");
  const filenameOnlyCheckbox = document.getElementById("filename-only");

  const absolutePathsDefaultCheckbox = document.getElementById(
    "absolute-paths-default",
  );
  const relativePathsDefaultCheckbox = document.getElementById(
    "relative-paths-default",
  );
  const filenameOnlyDefaultCheckbox = document.getElementById(
    "filename-only-default",
  );
  const playlistOptions = document.getElementById("playlist-options");

  const updateMpdCheckbox = document.getElementById("update-mpd");
  const mpdAdvancedSection = document.getElementById("mpd-advanced");

  const updateMpdCheckboxDefault =
    document.getElementById("update-mpd-default");
  const mpdAdvancedSectionDefault = document.getElementById(
    "mpd-advanced-default",
  );

  // Advanced Panel Elements
  const defaultConfigToggle = document.getElementById("defaults-toggle");
  const defaultConfigPanel = document.getElementById("defaults-panel");
  const defaultConfigChevron = document.getElementById("defaults-chevron");
  const saveDefaultsBtn = document.getElementById("save-defaults");

  // Manger Tab
  const managementTabBtn = document.getElementById("management-tab-btn");

  const threshold = document.getElementById("strong-match-threshold-default");
  const valueLabel = document.getElementById("threshold-value-default");

  threshold.addEventListener("input", () => {
    valueLabel.textContent = threshold.value + "%";
  });

  function disableManagementTab() {
    if (!managementTabBtn) return;
    managementTabBtn.classList.add("disabled");
  }

  function enableManagementTab() {
    if (!managementTabBtn) return;
    managementTabBtn.classList.remove("disabled");
  }

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
      document.getElementById("mpc-path-default").value = prefs.mpcPath;

      document.getElementById("mpc-command").value = prefs.mpcCommand;
      document.getElementById("mpc-command-default").value = prefs.mpcCommand;

      absolutePathsCheckbox.checked = prefs.absolutePaths;
      relativePathsCheckbox.checked = prefs.relativePaths;
      filenameOnlyCheckbox.checked = prefs.fileNames;

      absolutePathsDefaultCheckbox.checked = prefs.absolutePaths;
      relativePathsDefaultCheckbox.checked = prefs.relativePaths;
      filenameOnlyDefaultCheckbox.checked = prefs.fileNames;

      document.getElementById("resume-download").checked = prefs.resume;
      document.getElementById("resume-download-default").checked = prefs.resume;

      document.getElementById("overwrite-files").checked = prefs.overwrite;
      document.getElementById("overwrite-files-default").checked =
        prefs.overwrite;

      threshold.value = prefs.matchThreshold;
      valueLabel.textContent = prefs.matchThreshold + "%";
      document.getElementById("fallback-policy-default").value = prefs.fallback;
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
      relativePaths: relativePathsDefaultCheckbox.checked,
      absolutePaths: absolutePathsDefaultCheckbox.checked,
      fileNames: filenameOnlyDefaultCheckbox.checked,
      resume: document.getElementById("resume-download-default").checked,
      overwrite: document.getElementById("overwrite-files-default").checked,
      matchThreshold: document.getElementById("strong-match-threshold-default")
        .value,
      fallback: document.getElementById("fallback-policy-default").value,
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
  // defaultConfigToggle.addEventListener("click", () => {
  //   if (defaultConfigPanel.style.display === "none") {
  //     defaultConfigPanel.style.display = "block";
  //     defaultConfigChevron.className = "fas fa-chevron-up";
  //   } else {
  //     defaultConfigPanel.style.display = "none";
  //     defaultConfigChevron.className = "fas fa-chevron-down";
  //   }
  // });
  defaultConfigToggle.addEventListener("click", function () {
    const isOpening = !defaultConfigPanel.classList.contains("open");

    // Toggle panel classes
    defaultConfigPanel.classList.toggle("open");
    defaultConfigToggle.classList.toggle("active");

    // Handle height transition completion
    if (isOpening) {
      defaultConfigPanel.style.padding = "25px";
    } else {
      // Wait for close animation to finish before hiding
      defaultConfigPanel.addEventListener(
        "transitionend",
        function handler() {
          if (!defaultConfigPanel.classList.contains("open")) {
            defaultConfigPanel.style.padding = "0px";
          }
          defaultConfigPanel.removeEventListener("transitionend", handler);
        },
        { once: true },
      );
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
  absolutePathsCheckbox.addEventListener("change", () => {
    if (absolutePathsCheckbox.checked) {
      filenameOnlyCheckbox.checked = false;
      relativePathsCheckbox.checked = false;
    }
  });
  relativePathsCheckbox.addEventListener("change", () => {
    if (relativePathsCheckbox.checked) {
      filenameOnlyCheckbox.checked = false;
      absolutePathsCheckbox.checked = false;
    }
  });

  filenameOnlyCheckbox.addEventListener("change", () => {
    if (filenameOnlyCheckbox.checked) {
      relativePathsCheckbox.checked = false;
      absolutePathsCheckbox.checked = false;
    }
  });

  absolutePathsDefaultCheckbox.addEventListener("change", () => {
    if (absolutePathsDefaultCheckbox.checked) {
      filenameOnlyDefaultCheckbox.checked = false;
      relativePathsDefaultCheckbox.checked = false;
    }
  });
  relativePathsDefaultCheckbox.addEventListener("change", () => {
    if (relativePathsDefaultCheckbox.checked) {
      filenameOnlyDefaultCheckbox.checked = false;
      absolutePathsDefaultCheckbox.checked = false;
    }
  });

  filenameOnlyDefaultCheckbox.addEventListener("change", () => {
    if (filenameOnlyDefaultCheckbox.checked) {
      relativePathsDefaultCheckbox.checked = false;
      absolutePathsDefaultCheckbox.checked = false;
    }
  });

  updateMpdCheckbox.addEventListener("change", () => {
    mpdAdvancedSection.style.display = updateMpdCheckbox.checked
      ? "block"
      : "none";
  });
  updateMpdCheckboxDefault.addEventListener("change", () => {
    mpdAdvancedSectionDefault.style.display = updateMpdCheckboxDefault.checked
      ? "block"
      : "none";
  });
  // Add log entry to the UI
  function addLog(message, type = "info") {
    const logEntry = document.createElement("div");
    logEntry.className = "log-entry";

    // Extract timestamp
    const now = new Date();
    const timestamp = now.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });

    // Create tag element
    const tag = document.createElement("span");
    tag.className = "log-tag";

    // Create content element
    const content = document.createElement("span");
    content.className = "log-content";

    // Auto-detect log types based on content
    let logType = "info";
    let logTag = "SYSTEM";

    // Map of tags to detect
    const tagMap = [
      { tag: "[DIRECTORY]", type: "system" },
      { tag: "[PLAYLIST]", type: "playlist" },
      { tag: "[METADATA]", type: "metadata" },
      { tag: "[THUMBNAIL]", type: "thumbnail" },
      { tag: "[LYRICS]", type: "lyrics" },
      { tag: "[QUALITY]", type: "quality" },
      { tag: "[SETTINGS]", type: "settings" },
      { tag: "[COMMAND]", type: "command" },
      { tag: "[debug]", type: "debug" },
      { tag: "[download]", type: "download" },
      { tag: "[ExtractAudio]", type: "convert" },
      { tag: "[Convert]", type: "convert" },
      { tag: "[SUCCESS]", type: "success" },
      { tag: "[WARNING]", type: "warning" },
      { tag: "[ERROR]", type: "error" },
      { tag: "[MPD]", type: "mpd" },
      { tag: "[CLEANUP]", type: "system" },
      { tag: "[PROGRESS]", type: "system" },
    ];

    // Find matching tag
    for (const { tag, type } of tagMap) {
      if (message.includes(tag)) {
        logType = type;
        logTag = tag.replace(/[\[\]]/g, ""); // Remove brackets
        break;
      }
    }

    // Special cases
    if (message.includes("yt-dlp")) logType = "command";
    if (message.includes("ffmpeg")) logType = "convert";

    // Set tag content with timestamp
    tag.textContent = `[${logTag.toUpperCase()}:${timestamp}]`;

    // Set message content without the first occurrence of the tag
    let cleanMessage = message;
    for (const { tag } of tagMap) {
      if (cleanMessage.includes(tag)) {
        cleanMessage = cleanMessage.replace(tag, "").trim();
        break;
      }
    }
    content.textContent = cleanMessage;

    // Add type-specific class
    tag.classList.add(`log-${logType}`);
    content.classList.add(`log-${logType}`);

    // Append elements
    logEntry.appendChild(tag);
    logEntry.appendChild(content);

    // Special handling for MPD messages
    if (logType === "mpd") {
      if (!message.includes("successfully")) {
        updateMpdStatus("In progress...", message.replace("[mpd]", ""));
      } else if (message.includes("[ERROR] MPD")) {
        updateMpdStatus("Failed", message);
      } else if (message.includes("[MPD] Library updated successfully")) {
        updateMpdStatus("Completed", message.replace("[mpd]", ""));
      }
    }

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

    // Disable management tab during download
    disableManagementTab();

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
      enableManagementTab();
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
        enableManagementTab();
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
      enableManagementTab();
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

function toggleCollapse(header) {
  const collapsible = header.parentElement;
  const content = collapsible.querySelector(".collapsible-content");
  const isOpen = collapsible.classList.contains("open");

  if (isOpen) {
    content.style.maxHeight = "0";
    collapsible.classList.remove("open");
  } else {
    content.style.maxHeight = content.scrollHeight + "px";
    collapsible.classList.add("open");
  }
}
