document.addEventListener("DOMContentLoaded", () => {
  const MAX_LOG_ENTRIES = 250;
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

  const migrateBtn = document.getElementById("start-migration-btn");

  threshold.addEventListener("input", () => {
    valueLabel.textContent = threshold.value + "%";
  });

  const saveLogsToggle = document.getElementById("save-logs-toggle");

  const savedLogsList = document.getElementById("saved-logs-list");
  const logViewerContent = document.getElementById("log-viewer-content");
  const logViewTitle = document.getElementById("log-view-title");
  const logViewMeta = document.getElementById("log-view-meta");
  const refreshLogsSidebar = document.getElementById("refresh-logs-sidebar");
  const clearAllLogsBtn = document.getElementById("clear-all-logs");
  const deleteCurrentLogBtn = document.getElementById("delete-current-log");

  // Move tab fields
  const moveAudioSource = document.getElementById("move-audio-source");
  const moveLyricsSource = document.getElementById("move-lyrics-source");
  const movePlaylistsSource = document.getElementById("move-playlists-source");

  // Keep track of the currently selected log filename
  let currentSelectedLog = null;

  // Search functionality
  const logSearchInput = document.getElementById("log-search");
  const clearSearchBtn = document.getElementById("clear-search");
  const searchCountSpan = document.getElementById("search-count");
  let currentLogContent = "";
  let searchDebounceTimer = null;
  let currentSearchTask = null;
  let matchIndices = [];
  let currentMatchIndex = -1;
  function getLogType(line) {
    // Use the same tagMap as in addLog
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
      { tag: "[FIX PLAYLIST COMPLETE]", type: "success" },
      { tag: "[FIX PLAYLIST SUMMARY]", type: "lyrics" },
      { tag: "[WARNING]", type: "warning" },
      { tag: "[ERROR]", type: "error" },
      { tag: "[MPD]", type: "mpd" },
      { tag: "[CLEANUP]", type: "system" },
      { tag: "[PROGRESS]", type: "system" },
    ];

    for (const { tag, type } of tagMap) {
      if (line.includes(tag)) return type;
    }
    if (line.includes("yt-dlp")) return "command";
    if (line.includes("ffmpeg")) return "convert";
    return "info";
  }

  // Log navigation Elements
  const prevMatchBtn = document.getElementById("prev-match");
  const nextMatchBtn = document.getElementById("next-match");

  if (prevMatchBtn) {
    prevMatchBtn.addEventListener("click", goToPrevMatch);
  }
  if (nextMatchBtn) {
    nextMatchBtn.addEventListener("click", goToNextMatch);
  }

  // Log navigation keyboard Shortcuts
  document.addEventListener("keydown", (e) => {
    // Check if logs tab is active
    const logsTab = document.getElementById("logs-tab");
    if (!logsTab || !logsTab.classList.contains("active")) return;

    // Avoid interfering with typing in the search input
    if (document.activeElement === logSearchInput) return;

    if (e.key === "n" && !e.shiftKey) {
      e.preventDefault();
      goToNextMatch();
    } else if (e.key === "N" || (e.key === "n" && e.shiftKey)) {
      e.preventDefault();
      goToPrevMatch();
    }
  });

  const moveModeSelect = document.getElementById("move-mode");
  const moveWarning = document.getElementById("move-warning");
  if (moveModeSelect && moveWarning) {
    moveWarning.style.display =
      moveModeSelect.value === "move" ? "inline-block" : "none";
    moveModeSelect.addEventListener("change", () => {
      moveWarning.style.display =
        moveModeSelect.value === "move" ? "inline-block" : "none";
    });
  }


  const startMoveBtn = document.getElementById("start-move-btn");
  const moveStatusDiv = document.getElementById("move-status");
  const moveProgressText = document.getElementById("move-progress-text");
  const moveProgressBar = document.getElementById("move-progress-bar");
  const moveTitle = document.getElementById("move-title");

  startMoveBtn.addEventListener("click", async () => {
      const sourceAudio = document.getElementById("move-audio-source").value;
      const sourceLyrics = document.getElementById("move-lyrics-source").value;
      const sourcePlaylists = document.getElementById("move-playlists-source").value;
      const destAudio = document.getElementById("move-audio-dest").value;
      const destLyrics = document.getElementById("move-lyrics-dest").value;
      const destPlaylists = document.getElementById("move-playlists-dest").value;
      const processAudio = document.getElementById("move-audio-enabled").checked;
      const processLyrics = document.getElementById("move-lyrics-enabled").checked;
      const processPlaylists = document.getElementById("move-playlists-enabled").checked;
      const updatePlaylists = document.getElementById("move-update-playlists").checked;
      const mode = document.getElementById("move-mode").value;
      const saveLogs = document.getElementById("save-logs-toggle").checked;

      startMoveBtn.disabled = true;
      startMoveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

      moveStatusDiv.style.display = "block";
      moveProgressText.textContent = "0/0";
      moveProgressBar.style.width = "0%";
      moveTitle.textContent = "Preparing...";

      try {
          const response = await fetch("/move_copy/start", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                  source_audio: sourceAudio,
                  source_lyrics: sourceLyrics,
                  source_playlists: sourcePlaylists,
                  dest_audio: destAudio,
                  dest_lyrics: destLyrics,
                  dest_playlists: destPlaylists,
                  process_audio: processAudio,
                  process_lyrics: processLyrics,
                  process_playlists: processPlaylists,
                  update_playlists: updatePlaylists,
                  mode: mode,
                  save_logs: saveLogs,
              }),
          });

          const data = await response.json();
          if (data.operation_id) {
              const eventSource = new EventSource(`/logs/${data.operation_id}`);

              eventSource.onmessage = (event) => {
                  const msg = event.data;
                  // Update progress from [PROGRESS] messages
                  const progressMatch = msg.match(/\[PROGRESS\] (\d+)\/(\d+)/);
                  if (progressMatch) {
                      const current = parseInt(progressMatch[1]);
                      const total = parseInt(progressMatch[2]);
                      moveProgressText.textContent = `${current}/${total}`;
                      const percent = (current / total) * 100;
                      moveProgressBar.style.width = `${percent}%`;
                  }

                  // Update title from first meaningful message
                  if (msg.includes("[MOVE/COPY] Starting") && moveTitle.textContent === "Preparing...") {
                      moveTitle.textContent = "Moving/Copying files...";
                  }

                  // Add logs to the main log output (reuse existing addLog)
                  if (window.App && window.App.addLog) {
                      window.App.addLog(msg);
                  }

                  if (msg === "[END]") {
                      eventSource.close();
                      startMoveBtn.disabled = false;
                      startMoveBtn.innerHTML = '<i class="fas fa-random"></i> Start Moving/Copying';
                      moveTitle.textContent = "Completed";
                  }
              };

              eventSource.onerror = (err) => {
                  console.error("Move/copy SSE error:", err);
                  eventSource.close();
                  startMoveBtn.disabled = false;
                  startMoveBtn.innerHTML = '<i class="fas fa-random"></i> Start Moving/Copying';
                  moveTitle.textContent = "Error occurred";
                  if (window.App && window.App.addLog) {
                      window.App.addLog("[ERROR] Move/copy log stream failed", "error");
                  }
              };
          } else {
              throw new Error("No operation_id returned");
          }
      } catch (error) {
          console.error("Move/copy start error:", error);
          startMoveBtn.disabled = false;
          startMoveBtn.innerHTML = '<i class="fas fa-random"></i> Start Moving/Copying';
          moveTitle.textContent = "Failed to start";
          if (window.App && window.App.addLog) {
              window.App.addLog(`[ERROR] ${error.message}`, "error");
          }
      }
  });

  function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function scrollElementIntoView(element, container) {
    if (!element || !container) return;
    const containerRect = container.getBoundingClientRect();
    const elementRect = element.getBoundingClientRect();
    const offsetTop = elementRect.top - containerRect.top + container.scrollTop;
    // Center the element vertically
    const targetScrollTop =
      offsetTop - containerRect.height / 2 + elementRect.height / 2;
    container.scrollTo({
      top: targetScrollTop,
      behavior: "smooth",
    });
  }

  // Search navigations:
  function goToNextMatch() {
    if (!matchIndices.length) return;
    const currentLine = document.querySelector(".log-line.current-match");
    if (currentLine) currentLine.classList.remove("current-match");

    currentMatchIndex = (currentMatchIndex + 1) % matchIndices.length;
    const nextLine = document.querySelector(
      `.log-line[data-line="${matchIndices[currentMatchIndex]}"]`,
    );
    if (nextLine) {
      nextLine.classList.add("current-match");
      scrollElementIntoView(nextLine, logViewerContent);
    }
  }

  function goToPrevMatch() {
    if (!matchIndices.length) return;
    const currentLine = document.querySelector(".log-line.current-match");
    if (currentLine) currentLine.classList.remove("current-match");

    currentMatchIndex =
      (currentMatchIndex - 1 + matchIndices.length) % matchIndices.length;
    const prevLine = document.querySelector(
      `.log-line[data-line="${matchIndices[currentMatchIndex]}"]`,
    );
    if (prevLine) {
      prevLine.classList.add("current-match");
      scrollElementIntoView(prevLine, logViewerContent);
    }
  }

  // Filter logs content
  function filterLogContent() {
    const searchTerm = logSearchInput.value.trim();
    const container = logViewerContent;
    if (!container) return;

    // Cancel any ongoing search
    if (currentSearchTask) {
      currentSearchTask.cancel = true;
      currentSearchTask = null;
    }

    const lines = currentLogContent.split("\n");
    if (lines.length === 0) return;

    // Show searching indicator
    container.innerHTML =
      '<div class="searching-indicator">Searching... <i class="fas fa-spinner fa-spin"></i></div>';
    if (searchCountSpan) searchCountSpan.textContent = "";

    const totalLines = lines.length;
    const lowerTerm = searchTerm.toLowerCase();
    const CHUNK_SIZE = 5000;
    let processedLines = 0;
    let matchedLines = 0;
    const resultChunks = [];
    const newMatchIndices = [];

    const task = { cancel: false };
    currentSearchTask = task;

    function processChunk(startIdx) {
      if (task.cancel) return;

      const endIdx = Math.min(startIdx + CHUNK_SIZE, totalLines);
      const chunk = lines.slice(startIdx, endIdx);
      let chunkHtml = "";

      for (let i = 0; i < chunk.length; i++) {
        const line = chunk[i];
        const lineNumber = startIdx + i;
        const logType = getLogType(line);
        let escaped = escapeHtml(line);

        const matches = searchTerm && line.toLowerCase().includes(lowerTerm);
        if (matches) {
          matchedLines++;
          newMatchIndices.push(lineNumber);
          const regex = new RegExp(`(${escapeRegExp(searchTerm)})`, "gi");
          escaped = escaped.replace(regex, "<mark>$1</mark>");
        }

        chunkHtml += `<div class="log-line log-${logType}" data-line="${lineNumber}">${escaped}</div>`;
      }

      resultChunks.push(chunkHtml);
      processedLines += chunk.length;

      if (endIdx < totalLines) {
        setTimeout(() => processChunk(endIdx), 0);
      } else {
        if (!task.cancel) {
          const finalHtml = resultChunks.join("");
          if (searchTerm && matchedLines === 0) {
            container.innerHTML = `<div class="no-matches">No matches found for "${escapeHtml(searchTerm)}"</div>`;
            matchIndices = [];
            currentMatchIndex = -1;
          } else {
            container.innerHTML = finalHtml;
            matchIndices = newMatchIndices;
            if (searchTerm && matchIndices.length > 0) {
              currentMatchIndex = 0;
              const firstMatchLine = document.querySelector(
                `.log-line[data-line="${matchIndices[0]}"]`,
              );
              if (firstMatchLine) {
                scrollElementIntoView(firstMatchLine, logViewerContent);
                firstMatchLine.classList.add("current-match");
              }
            } else {
              currentMatchIndex = -1;
            }
          }
          if (searchCountSpan)
            searchCountSpan.textContent = searchTerm
              ? `(${matchedLines} matches)`
              : "";
          currentSearchTask = null;
        }
      }
    }

    processChunk(0);
  }

  // Load log saving setting
  async function loadLogSettings() {
    try {
      const response = await fetch("/logs/settings");
      const data = await response.json();
      if (data.save_logs !== undefined) {
        saveLogsToggle.checked = data.save_logs;
      }
    } catch (error) {
      console.error("Failed to load log settings:", error);
    }
  }

  // Save log setting
  async function saveLogSettings(enabled) {
    try {
      const response = await fetch("/logs/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ save_logs: enabled }),
      });
      const data = await response.json();
      if (data.success) {
        showToast(`Log saving ${enabled ? "enabled" : "disabled"}`);
      }
    } catch (error) {
      console.error("Failed to save log settings:", error);
      showToast("Failed to update log settings", true);
    }
  }

  // Load saved logs into the sidebar list
  async function loadSavedLogsSidebar() {
    try {
      const response = await fetch("/logs/files");
      const logs = await response.json();

      if (!savedLogsList) return;

      if (logs.length === 0) {
        savedLogsList.innerHTML =
          '<li class="sidebar-placeholder">No saved logs</li>';
        // Clear viewer and title
        logViewerContent.textContent = "";
        logViewTitle.textContent = "No logs available";
        logViewMeta.textContent = "";
        currentSelectedLog = null;
        return;
      }

      // Sort by modified date (newest first)
      logs.sort((a, b) => b.modified - a.modified);

      // Build the list
      savedLogsList.innerHTML = logs
        .map(
          (log) => `
      <li data-filename="${escapeHtml(log.name)}" data-modified="${log.modified}">
        <span class="log-filename">${escapeHtml(log.name)}</span>
        <span class="log-meta">${new Date(log.modified * 1000).toLocaleString()}</span>
      </li>
    `,
        )
        .join("");

      // Attach click handlers
      document.querySelectorAll("#saved-logs-list li").forEach((li) => {
        li.addEventListener("click", async (e) => {
          e.stopPropagation();
          const filename = li.dataset.filename;
          if (!filename) return;

          // Highlight selected item
          document
            .querySelectorAll("#saved-logs-list li")
            .forEach((item) => item.classList.remove("active"));
          li.classList.add("active");

          // Load and display the log content
          await viewLogContent(filename);
        });
      });

      // If there's a currently selected log, try to keep it selected
      if (currentSelectedLog) {
        const existingLi = document.querySelector(
          `#saved-logs-list li[data-filename="${currentSelectedLog}"]`,
        );
        if (existingLi) {
          existingLi.classList.add("active");
          await viewLogContent(currentSelectedLog);
        } else {
          // The previously selected log no longer exists, select the latest
          const firstLi = savedLogsList.querySelector("li");
          if (firstLi && firstLi.dataset.filename) {
            firstLi.classList.add("active");
            await viewLogContent(firstLi.dataset.filename);
          } else {
            // No logs left
            logViewerContent.textContent = "";
            logViewTitle.textContent = "No logs available";
            logViewMeta.textContent = "";
            currentSelectedLog = null;
          }
        }
      } else if (logs.length > 0) {
        // No current selection, select the latest (first in list)
        const firstLi = savedLogsList.querySelector("li");
        if (firstLi && firstLi.dataset.filename) {
          firstLi.classList.add("active");
          await viewLogContent(firstLi.dataset.filename);
        }
      }
      showToast("Loaded all saved logs successfully");
    } catch (error) {
      console.error("Failed to load saved logs:", error);
      showToast("Failed to load saved logs", true);
    }
  }

  function escapeHtml(str) {
    return str.replace(/[&<>]/g, function (m) {
      if (m === "&") return "&amp;";
      if (m === "<") return "&lt;";
      if (m === ">") return "&gt;";
      return m;
    });
  }

  // View log file content
  async function viewLogFile(filename) {
    try {
      const response = await fetch(`/logs/file/${filename}`);
      const data = await response.json();

      if (data.content) {
        logViewerTitle.textContent = filename;
        logViewerContent.textContent = data.content;
        logViewer.style.display = "block";
        logViewerContent.scrollTop = 0;
      } else {
        showToast("Failed to load log file", true);
      }
    } catch (error) {
      console.error("Failed to view log file:", error);
      showToast("Failed to load log file", true);
    }
  }

  async function viewLogContent(filename) {
    try {
      const response = await fetch(`/logs/file/${filename}`);
      const data = await response.json();

      if (data.content) {
        currentLogContent = data.content; // store for search
        logViewerContent.textContent = data.content; // initial plain display
        logViewTitle.textContent = filename;
        logViewMeta.textContent = `${formatFileSize(data.size)} · ${new Date(data.modified * 1000).toLocaleString()}`;
        currentSelectedLog = filename;
        logViewerContent.scrollTop = 0;

        // Reset search field and filter (will show full content)
        if (logSearchInput) logSearchInput.value = "";
        filterLogContent(); // re‑apply filter (clears any previous highlight)
      } else {
        showToast("Failed to load log file", true);
      }
    } catch (error) {
      console.error("Failed to view log file:", error);
      showToast("Failed to load log file", true);
    }
  }

  async function deleteLogFile(filename) {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) {
      return;
    }

    try {
      const response = await fetch(`/logs/file/${filename}`, {
        method: "DELETE",
      });
      const data = await response.json();

      if (data.success) {
        showToast("Log file deleted");
        // Refresh the sidebar list
        await loadSavedLogsSidebar();
        // If the deleted file was the one displayed, clear viewer (loadSavedLogsSidebar will select a new one)
        if (currentSelectedLog === filename) {
          // loadSavedLogsSidebar will auto‑select the latest, so no extra action needed
        }
      } else {
        showToast("Failed to delete log file", true);
      }
    } catch (error) {
      console.error("Failed to delete log file:", error);
      showToast("Failed to delete log file", true);
    }
  }

  // Clear all logs
  async function clearAllLogs() {
    if (!confirm("Are you sure you want to delete ALL saved logs?")) {
      return;
    }

    try {
      const response = await fetch("/logs/clear", {
        method: "POST",
      });
      const data = await response.json();

      if (data.success) {
        showToast("All logs cleared");
        await loadSavedLogsSidebar(); // will show empty state
        logViewerContent.textContent = "";
        logViewTitle.textContent = "No logs available";
        logViewMeta.textContent = "";
        currentSelectedLog = null;
      } else {
        showToast("Failed to clear logs", true);
      }
    } catch (error) {
      console.error("Failed to clear logs:", error);
      showToast("Failed to clear logs", true);
    }
  }
  // Format file size
  function formatFileSize(bytes) {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

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
      if (moveAudioSource) moveAudioSource.value = prefs.audioDir || "~/Music";
      if (moveLyricsSource)
        moveLyricsSource.value = prefs.lyricsDir || "~/Music/lyrics";
      if (movePlaylistsSource)
        movePlaylistsSource.value =
          prefs.playlistDir || "~/.config/mpd/playlists";
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
    if (logOutput.children.length > MAX_LOG_ENTRIES) {
      logOutput.innerHTML = "";
      logOutput.appendChild(logEntry);
    }
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

    const saveLogs = saveLogsToggle.checked;

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
          save_logs: saveLogs,
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

  function updateMigrateProgress(current, total, title) {
    const migrateStatus = document.getElementById("migration-status");
    const migrateProgressText = document.getElementById(
      "migration-progress-text",
    );
    const migrateProgressBar = document.getElementById(
      "migration-progress-bar",
    );
    const migrateTitleElement = document.getElementById("migrate-title");

    migrateStatus.style.display = "block";
    migrateProgressText.textContent = `${current}/${total}`;
    migrateTitleElement.textContent = title || "Untitled Playlist";

    const percentage = total > 0 ? (current / total) * 100 : 0;
    migrateProgressBar.style.width = `${percentage}%`;
  }

  function updateMpdStatus(message, output = "") {
    const mpdStatus = document.getElementById("mpd-status");
    const mpdStatusText = document.getElementById("mpd-status-text");
    const mpdOutput = document.getElementById("mpd-output");

    mpdStatus.style.display = "block";
    mpdStatusText.textContent = message;
    mpdOutput.textContent = output;
  }

  const modal = document.getElementById("match-modal");
  const list = document.getElementById("match-list");
  const desc = document.getElementById("match-modal-desc");
  const skipBtn = document.getElementById("skip-match");
  const overlay = document.getElementById("modal-overlay");

  function getConfidence(scorePerc) {
    if (scorePerc >= 85) {
      return { label: "STRONG", class: "conf-strong" };
    }
    if (scorePerc >= 65) {
      return { label: "GOOD", class: "conf-good" };
    }
    return { label: "WEAK", class: "conf-weak" };
  }

  function extractVideoId(input) {
    // raw ID
    if (/^[a-zA-Z0-9_-]{11}$/.test(input)) {
      return input;
    }

    try {
      const url = new URL(input);
      if (
        url.hostname.includes("youtube.com") ||
        url.hostname.includes("music.youtube.com")
      ) {
        return url.searchParams.get("v");
      }
      if (url.hostname === "youtu.be") {
        return url.pathname.slice(1);
      }
    } catch (_) {}

    return null;
  }

  function showMatchModal(payload, migrationId) {
    modal.classList.remove("hidden");
    overlay.classList.remove("hidden", "closing");
    list.innerHTML = "";

    desc.textContent = `${payload.title} — ${payload.artist}`;

    payload.candidates.forEach((c) => {
      const btn = document.createElement("button");
      btn.className = "match-item";
      btn.onclick = () => submitChoice(migrationId, "select", c.videoId);

      btn.innerHTML = `
      <img class="match-thumb" src="${c.thumbnail}">
      <div class="match-meta">
        <div class="match-title">${c.title}</div>
        <div class="match-artists">${c.artists.join(", ")}</div>
      </div>
      <div class="match-right">
        <span class="confidence-badge conf-${c.score >= 0.85 ? "strong" : "good"}">
          ${c.score >= 0.85 ? "STRONG" : "GOOD"}
        </span>
        <span class="match-score conf-${c.score >= 0.85 ? "strong" : "good"}">
          ${Math.round(c.score * 100)}%
        </span>
      </div>
    `;
      list.appendChild(btn);
    });

    skipBtn.onclick = () => submitChoice(migrationId, "skip");

    console.log(payload);

    const manualWrapper = document.getElementById("manual-video-wrapper");
    const manualInput = document.getElementById("manual-video-id");
    const manualSubmit = document.getElementById("manual-submit");

    /* reset */
    manualWrapper.classList.add("hidden");
    manualInput.value = "";
    manualSubmit.onclick = null;

    const researchSongsBtn = document.getElementById("research-songs");
    const researchVideosBtn = document.getElementById("research-videos");

    researchSongsBtn.style.display = "none";
    researchVideosBtn.style.display = "none";
    researchSongsBtn.onclick = null;
    researchVideosBtn.onclick = null;

    if (payload.allow_research) {
      if (payload.search_filter === "songs") {
        researchVideosBtn.style.display = "inline-flex";
        researchVideosBtn.onclick = () =>
          submitChoice(migrationId, "research_videos");
      } else {
        researchSongsBtn.style.display = "inline-flex";
        researchSongsBtn.onclick = () =>
          submitChoice(migrationId, "research_songs");
      }
    }
    /* show manual option when allowed */
    if (payload.allow_manual) {
      manualWrapper.classList.remove("hidden");

      manualSubmit.onclick = () => {
        const value = manualInput.value.trim();
        if (!value) return;

        const videoId = extractVideoId(value);
        if (!videoId) {
          alert("Invalid YouTube URL or video ID");
          return;
        }

        submitChoice(migrationId, "manual", videoId);
      };
    }
  }

  async function submitChoice(migrationId, action, videoId = null) {
    await fetch("/migrate/choice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        migration_id: migrationId,
        action,
        video_id: videoId,
      }),
    });

    modal.classList.add("hidden");
    overlay.classList.add("hidden");
  }

  // Start listening to the log stream
  function startLogStream(downloadId) {
    closeEventSource();

    eventSource = new EventSource(`/logs/${downloadId}`);

    eventSource.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        if (parsed.type === "choice") {
          showMatchModal(parsed, downloadId);
          return;
        }
      } catch (_) {}

      const message = event.data;

      const playlistMatch = message.match(
        /\[PLAYLIST\] Downloading video (\d+)\/(\d+): (.+)/,
      );
      const migrateMatch = message.match(
        /\[MIGRATE\] Migrating File (\d+)\/(\d+): (.+)/,
      );
      if (playlistMatch) {
        const current = parseInt(playlistMatch[1]);
        const total = parseInt(playlistMatch[2]);
        const title = playlistMatch[3];
        updatePlaylistProgress(current, total, title);
      }
      if (migrateMatch) {
        const migrateCurrent = parseInt(migrateMatch[1]);
        const migrateTotal = parseInt(migrateMatch[2]);
        const migrateTitle = migrateMatch[3];
        updateMigrateProgress(migrateCurrent, migrateTotal, migrateTitle);
      }
      if (message === "[END]") {
        // Download completed
        closeEventSource();
        downloadBtn.disabled = false;
        downloadBtn.innerHTML = '<i class="fas fa-download"></i> Download';
        migrateBtn.disabled = false;
        migrateBtn.innerHTML = '<i class="fas fa-random"></i> Start Migration';
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
      migrateBtn.disabled = false;
      migrateBtn.innerHTML = '<i class="fas fa-random"></i> Start Migration';
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

  // Attach search event with debouncing
  if (clearSearchBtn) {
    clearSearchBtn.addEventListener("click", () => {
      logSearchInput.value = "";
      filterLogContent();
    });
  }

  if (logSearchInput) {
    logSearchInput.addEventListener("input", () => {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => {
        filterLogContent();
      }, 300);
    });
  }
  // Refresh sidebar
  if (refreshLogsSidebar) {
    refreshLogsSidebar.addEventListener("click", loadSavedLogsSidebar);
  }

  // Clear all logs
  if (clearAllLogsBtn) {
    clearAllLogsBtn.addEventListener("click", clearAllLogs);
  }

  // Delete current log
  if (deleteCurrentLogBtn) {
    deleteCurrentLogBtn.addEventListener("click", async () => {
      if (currentSelectedLog) {
        await deleteLogFile(currentSelectedLog);
      } else {
        showToast("No log selected", true);
      }
    });
  }

  // Event listeners
  saveLogsToggle.addEventListener("change", (e) => {
    saveLogSettings(e.target.checked);
  });

  const logsTabBtn = document.getElementById("logs-tab-btn");
  if (logsTabBtn) {
    logsTabBtn.addEventListener("click", () => {
      // When logs tab is clicked, load the saved logs
      loadSavedLogsSidebar();
    });
  }

  // "View Saved" button: switch to logs tab and load saved logs
  const viewSavedLogsBtn = document.getElementById("view-saved-logs");
  if (viewSavedLogsBtn) {
    viewSavedLogsBtn.addEventListener("click", () => {
      if (logsTabBtn) {
        logsTabBtn.click();
        // Allow time for the tab to become visible, then scroll
        setTimeout(() => {
          const logsTabPane = document.getElementById("logs-tab");
          if (logsTabPane) {
            window.scrollTo({
              top: 0,
              behavior: "smooth",
            });
          }
        }, 100);
      } else {
        // Fallback: find the logs tab button manually
        const logsTab = document.querySelector('.tab-btn[data-tab="logs-tab"]');
        if (logsTab) logsTab.click();
        setTimeout(() => {
          const logsTabPane = document.getElementById("logs-tab");
          if (logsTabPane)
            window.scrollTo({
              top: 0,
              behavior: "smooth",
            });
        }, 100);
      }
    });
  }

  clearAllLogsBtn.addEventListener("click", clearAllLogs);

  // Load settings on page load
  loadLogSettings();

  window.App = {
    addLog,
    startLogStream,
    closeEventSource,
    disableManagementTab,
    enableManagementTab,
    getCurrentDownloadId: () => currentDownloadId,
    setCurrentDownloadId: (id) => (currentDownloadId = id),
    logOutput,
  };
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
