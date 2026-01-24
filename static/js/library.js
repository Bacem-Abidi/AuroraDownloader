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
  const container = document.getElementById("library-body");
  const searchInput = document.getElementById("library-search");
  const filterSelect = document.getElementById("library-filter");

  const playlistList = document.getElementById("playlist-list");
  const libraryTitle = document.getElementById("library-title");
  const librarySize = document.getElementById("library-size");
  const libraryMeta = document.getElementById("library-meta");

  const header = document.getElementById("library-row-header");

  const HEADERS = {
    all: `
      <div class="col-icon">♪</div>
      <div class="col-title">Title</div>
      <div class="col-artist">Artist</div>
      <div class="col-album">Album</div>
      <div class="col-duration">⏱</div>
      <div class="col-actions"></div>
    `,

    failed: `
      <div class="col-check">
        <input type="checkbox" id="select-all-failed">
      </div>
      <div class="col-icon">⚠</div>
      <div class="col-url">URL</div>
      <div class="col-vidId">video ID</div>
      <div class="col-format">Format</div>
      <div class="col-quality">Quality</div>
      <div class="col-type">Type</div>
      <div class="col-playlist">Playlist</div>
      <div class="col-index">Index</div>
      <div class="col-actions"></div>
    `,
  };

  // Separate cache for each source/playlist
  const libraryCache = {
    all: {
      items: [],
      offset: 0,
      hasMore: true,
      totalCount: 0,
      totalSize: 0,
      totalDuration: 0,
      cacheAge: null,
    },
    failed: {
      items: [],
      offset: 0,
      hasMore: true,
      totalCount: 0,
      totalSize: 0,
      totalDuration: 0,
      cacheAge: null,
    },
  };
  // Playlists will be cached by their name
  const playlistCache = {};

  let currentSource = "all";
  let playlistDir = null;
  let audioDir = null;
  let lyricsDir = null;
  let mode = "library"; // "library" | "playlist"
  let currentPlaylist = null;
  let activeFailedEntry = null;
  let loading = false;
  const limit = 25;

  function updateGridMode(source) {
    const header = document.getElementById("library-row-header");

    header.classList.toggle("is-library", source !== "failed");
    header.classList.toggle("is-failed", source === "failed");
  }

  function formatCacheAge(seconds) {
    if (seconds == null) return "";

    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
    return `${Math.floor(seconds / 86400)}d`;
  }

  async function loadPlaylists() {
    try {
      if (!playlistDir) {
        const prefs = await (await fetch("/preferences")).json();
        playlistDir = prefs.playlistDir;
      }

      const res = await fetch(
        `/playlists?dir=${encodeURIComponent(playlistDir)}`,
      );
      const playlists = await res.json();

      playlistList.innerHTML = "";

      if (!playlists.length) {
        playlistList.innerHTML = `<li class="sidebar-placeholder">No playlists</li>`;
        return;
      }

      playlists.forEach((pl) => {
        const li = document.createElement("li");
        li.textContent = pl.name.replace(/\.m3u$/i, "");
        li.dataset.playlist = pl.name;
        playlistList.appendChild(li);
      });
    } catch (e) {
      playlistList.innerHTML = `<li class="sidebar-placeholder">Failed to load playlists</li>`;
    }
  }

  function updateBulkActions() {
    const bulk = document.getElementById("retry-bulk-btn");
    bulk.classList.toggle("hidden", currentSource !== "failed");
  }

  function updateReloadActions() {
    const reload = document.getElementById("reload-btn");
    reload.classList.toggle("hidden", currentSource === "failed");
  }

  function selectSource(source) {
    mode = "library";
    currentPlaylist = null;
    currentSource = source;

    updateGridMode(currentSource);

    if (source == "all") {
      libraryTitle.textContent = "All Music";
      libraryMeta.textContent = "";
      header.innerHTML = HEADERS.all;
    } else {
      mode = "failed";
      libraryTitle.textContent = "Failed Downloads";
      libraryMeta.textContent = "";
      header.innerHTML = HEADERS.failed;
    }
    updateBulkActions();
    updateReloadActions();

    const cache = libraryCache[source];

    // Clear current view and load from cache or server
    container.innerHTML = "";

    if (cache.items.length > 0 && source != "failed") {
      renderLibrary(cache.items, true);

      libraryMeta.textContent =
        `${cache.items.length} / ${cache.totalCount} tracks` +
        (source === "failed" ? "" : ` [${cache.totalDuration} listening time]`);

      librarySize.textContent = source === "failed" ? "" : `${cache.totalSize}`;
    } else {
      loadLibrary(true, source);
    }
    // loadLibrary(true, source);
  }

  async function selectPlaylist(name) {
    mode = "playlist";
    currentPlaylist = name;
    currentSource = "playlist";

    updateGridMode(currentSource);

    libraryTitle.textContent = name.replace(/\.m3u$/i, "");
    libraryMeta.textContent = "Playlist";

    updateBulkActions();
    updateReloadActions();

    const cacheKey = `playlist:${currentPlaylist}`;
    const cache = playlistCache[cacheKey];

    // Clear current view and load from cache or server
    container.innerHTML = "";
    header.innerHTML = HEADERS.all;

    if (cache && cache.items.length > 0) {
      renderLibrary(cache.items, true);

      libraryMeta.textContent =
        `${cache.items.length} / ${cache.totalCount} tracks` +
        ` [${cache.totalDuration} listening time]`;

      librarySize.textContent = cache.totalSize;
    } else {
      loadPlaylistPage(true);
    }
    // loadPlaylistPage(true);
  }

  async function loadPlaylistPage(reset = false) {
    if (loading) return;

    // Get or create cache entry for this playlist
    const cacheKey = `playlist:${currentPlaylist}`;
    if (!playlistCache[cacheKey]) {
      playlistCache[cacheKey] = {
        items: [],
        offset: 0,
        hasMore: true,
        totalCount: 0,
        totalSize: 0,
        totalDuration: 0,
        cacheAge: null,
      };
    }

    const cache = playlistCache[cacheKey];

    // Reset cache if requested
    if (reset) {
      cache.items = [];
      cache.offset = 0;
      cache.hasMore = true;
      container.innerHTML = "";
    }

    if (!cache.hasMore && !reset) return;

    loading = true;

    try {
      const res = await fetch(
        `/playlist/${encodeURIComponent(currentPlaylist)}?` +
          `audioDir=${encodeURIComponent(audioDir)}` +
          `&playlistDir=${encodeURIComponent(playlistDir)}` +
          `&offset=${cache.offset}&limit=${limit}` +
          (reset ? "&reset=true" : ""),
      );

      const data = await res.json();

      cache.hasMore = data.hasMore;
      cache.offset += limit;
      cache.items.push(...data.items);
      cache.totalCount = data.total;
      cache.totalSize = data.total_size;
      cache.totalDuration = data.total_duration;

      if (data.cached && data.cache_age != null) {
        cache.cacheAge = data.cache_age;
      }

      const cacheInfo =
        cache.cacheAge != null
          ? ` • cache ${formatCacheAge(cache.cacheAge)} ago`
          : "";

      libraryMeta.textContent =
        `${cache.items.length} / ${cache.totalCount} tracks ` +
        `[${cache.totalDuration} listening time]` +
        cacheInfo;

      renderLibrary(cache.items.slice(-data.items.length)); // Only render new items
    } catch (e) {
      console.error("Error loading playlist:", e);
    } finally {
      loading = false;
    }
  }

  async function loadLibrary(reset = false, source = "all") {
    if (searchInput.value.trim() !== "") return;
    if (loading) return;

    // Get or create cache entry for this source
    const cache = libraryCache[source];

    // Reset cache if requested
    if (reset) {
      cache.items = [];
      cache.offset = 0;
      cache.hasMore = true;
      container.innerHTML = "";
    }

    if (!cache.hasMore && !reset) return;

    loading = true;

    try {
      let endpoint;

      if (source === "failed") {
        endpoint = `/failed?offset=${cache.offset}&limit=${limit}`;
      } else {
        if (!audioDir) {
          const prefs = await (await fetch("/preferences")).json();
          audioDir = prefs.audioDir;
          playlistDir = prefs.playlistDir;
          lyricsDir = prefs.lyricsDir;
        }
        endpoint = `/library?dir=${encodeURIComponent(audioDir)}&offset=${cache.offset}&limit=${limit}&reset=${reset}`;
      }

      const res = await fetch(endpoint);
      const data = await res.json();

      cache.hasMore = data.hasMore;
      cache.offset += limit;
      cache.items.push(...data.items);
      cache.totalCount = data.total;
      cache.totalSize = data.total_size;
      cache.totalDuration = data.total_duration;

      if (data.cached && data.cache_age != null) {
        cache.cacheAge = data.cache_age;
      }

      const cacheInfo =
        cache.cacheAge != null
          ? ` • cache ${formatCacheAge(cache.cacheAge)} ago`
          : "";

      libraryMeta.textContent =
        `${cache.items.length} / ${cache.totalCount} tracks` +
        (source === "failed"
          ? ""
          : ` [${cache.totalDuration} listening time]`) +
        cacheInfo;

      librarySize.textContent = source === "failed" ? "" : `${cache.totalSize}`;

      // Only render the newly loaded items
      renderLibrary(cache.items.slice(-data.items.length));

      if (reset && data.cached) {
        showToast(
          `${source === "failed" ? "Failed downloads" : "Library"} loaded from cache`,
        );
      }
    } catch (error) {
      console.error("Error loading library:", error);
      container.innerHTML = `
        <div class="history-placeholder">
          <i class="fas fa-exclamation-circle fa-3x"></i>
          <p>Failed to load ${source === "failed" ? "failed downloads" : "library"}</p>
        </div>
      `;
    } finally {
      loading = false;
    }
  }

  function renderLibrary(items, clear = false) {
    if (clear) {
      container.innerHTML = "";
    }

    if (!items.length && clear) {
      container.innerHTML = `
      <div class="history-placeholder">
        <i class="fas fa-music fa-3x"></i>
        <p>No matching files found</p>
      </div>
    `;
      return;
    }

    items.forEach((entry) => {
      const row = document.createElement("div");
      const isFailed = currentSource === "failed";

      row.className = isFailed
        ? "library-row library-item-row is-failed"
        : "library-row library-item-row is-library";

      const safePath = isFailed ? entry.path : entry.path.replace(/\\/g, "/");
      const artwork = entry.hasArtwork
        ? `<img class="track-artwork"
          src="/artwork?path=${encodeURIComponent(safePath)}"
          loading="lazy"
          onerror="this.replaceWith(document.createTextNode('▶'))">`
        : "▶";

      if (isFailed) {
        row.innerHTML = `
        <div class="col-check">
          <input type="checkbox" class="retry-check">
        </div>
        <div class="col-icon">⚠</div>
        <div class="col-url">${entry.url}</div>
        <div class="col-vidId">${entry.id}</div>
        <div class="col-format">${entry.format}</div>
        <div class="col-quality">${entry.quality}</div>
        <div class="col-type">${entry.type}</div>
        <div class="col-playlist">${entry.playlist}</div>
        <div class="col-index">${entry.index}</div>
        <div class="col-actions">
          <button class="actions-btn" aria-label="Actions">
            <i class="fas fa-ellipsis-v"></i>
          </button>

          <div class="actions-menu">
            <button data-action="info">
              <i class="fas fa-info-circle"></i> Info
            </button>
            <button data-action="edit">
              <i class="fas fa-pen"></i> Edit
            </button>
            <button data-action="move">
              <i class="fas fa-folder-open"></i> Move location
            </button>
          </div>
        </div>
      `;
      } else {
        row.innerHTML = `
        <div class="col-icon">${artwork}</div>
        <div class="col-title">${entry.title || entry.filename}</div>
        <div class="col-artist">${entry.artist || "—"}</div>
        <div class="col-album">${entry.album || "—"}</div>
        <div class="col-duration">${entry.duration || "—"}</div>
        <div class="col-actions">
          <button class="actions-btn" aria-label="Actions">
            <i class="fas fa-ellipsis-v"></i>
          </button>

          <div class="actions-menu">
            <button data-action="info">
              <i class="fas fa-info-circle"></i> Info
            </button>
            <button data-action="edit">
              <i class="fas fa-pen"></i> Edit
            </button>
            <button data-action="move">
              <i class="fas fa-folder-open"></i> Move location
            </button>
          </div>
        </div>
      `;
      }

      row.dataset.entry = JSON.stringify(entry);
      container.appendChild(row);
    });
  }

  function getFilteredLibrary() {
    const query = searchInput.value.toLowerCase().trim();
    const filter = filterSelect.value;

    // Get the current cache based on mode
    let currentItems = [];
    if (mode === "playlist" && currentPlaylist) {
      const cacheKey = `playlist:${currentPlaylist}`;
      currentItems = playlistCache[cacheKey]?.items || [];
    } else {
      currentItems = libraryCache[currentSource]?.items || [];
    }

    return currentItems.filter((item) => {
      let value = "";

      switch (filter) {
        case "title":
          value = item.title;
          break;
        case "artist":
          value = item.artist;
          break;
        case "album":
          value = item.album;
          break;
        case "filename":
          value = item.filename;
          break;
        default:
          // "all"
          value = `${item.title} ${item.artist} ${item.album} ${item.filename}`;
      }

      return value?.toLowerCase().includes(query);
    });
  }

  function applyFilters() {
    const filtered = getFilteredLibrary();
    renderLibrary(filtered, true);

    // Update count for filtered results
    const filteredCount = filtered.length;
    let totalCount = 0;

    if (mode === "playlist" && currentPlaylist) {
      const cacheKey = `playlist:${currentPlaylist}`;
      totalCount = playlistCache[cacheKey]?.totalCount || 0;
    } else {
      totalCount = libraryCache[currentSource]?.totalCount || 0;
    }

    const totalText = searchInput.value.trim()
      ? `Showing ${filteredCount} of ${totalCount} tracks`
      : `Loaded ${filteredCount} of ${totalCount} tracks`;

    libraryMeta.textContent = totalText;
  }

  searchInput.addEventListener("input", applyFilters);
  filterSelect.addEventListener("change", applyFilters);

  container.addEventListener("scroll", () => {
    if (
      container.scrollTop + container.clientHeight >=
      container.scrollHeight - 50
    ) {
      if (loading) return;

      if (mode === "library") {
        loadLibrary(false, currentSource);
      } else if (mode === "failed") {
        loadLibrary(false, "failed");
      } else if (mode === "playlist") {
        loadPlaylistPage(false);
      }
    }
  });

  // Initialize by loading the library
  loadLibrary(true, "all");
  updateGridMode(currentSource);
  loadPlaylists();

  document.getElementById("reload-btn").addEventListener("click", async () => {
    if (loading) return;

    if (mode === "playlist" && currentPlaylist) {
      // Clear playlist cache and reload
      const cacheKey = `playlist:${currentPlaylist}`;
      delete playlistCache[cacheKey];
      await loadPlaylistPage(true);
      showToast("Playlist cache cleared and reloaded");
    } else {
      // Clear library cache and reload
      libraryCache[currentSource] = {
        items: [],
        offset: 0,
        hasMore: true,
        totalCount: 0,
        totalSize: 0,
        totalDuration: 0,
      };
      await loadLibrary(true, currentSource);
      showToast(
        `${currentSource === "failed" ? "Failed downloads" : "Library"} cache cleared and reloaded`,
      );
    }
  });

  document.querySelectorAll(".sidebar-list").forEach((list) => {
    list.addEventListener("click", (e) => {
      const li = e.target.closest("li");
      if (!li || li.classList.contains("sidebar-placeholder")) return;

      document
        .querySelectorAll(".sidebar-list li")
        .forEach((el) => el.classList.remove("active"));

      li.classList.add("active");

      if (li.dataset.source) {
        selectSource(li.dataset.source);
      }

      if (li.dataset.playlist) {
        selectPlaylist(li.dataset.playlist);
      }
    });
  });

  container.addEventListener("click", (e) => {
    const btn = e.target.closest(".actions-menu button");
    if (!btn) return;

    const item = btn.closest(".library-row");
    const entry = JSON.parse(item.dataset.entry);

    if (btn.dataset.action === "info") {
      openInfoModal(entry);
    } else if (btn.dataset.action === "edit") {
      openEditModal(entry);
    }
  });

  const overlay = document.getElementById("modal-overlay");

  const infoFields = {
    title: document.getElementById("info-title"),
    duration: document.getElementById("info-duration"),
    artist: document.getElementById("info-artist"),
    album: document.getElementById("info-album"),
    year: document.getElementById("info-year"),
    fileFormat: document.getElementById("info-format"),
    path: document.getElementById("info-path"),
  };

  const failedFields = {
    url: document.getElementById("failed-url"),
    playlist: document.getElementById("failed-playlist"),
    index: document.getElementById("failed-index"),
    format: document.getElementById("failed-format"),
    quality: document.getElementById("failed-quality"),
    type: document.getElementById("failed-type"),
    statuses: document.getElementById("failed-statuses"),
  };

  function openInfoModal(entry) {
    const isFailed = currentSource === "failed";

    const infoModal = isFailed
      ? document.getElementById("failed-modal")
      : document.getElementById("info-modal");

    infoModal.classList.remove("hidden", "closing");

    overlay.classList.remove("hidden", "closing");

    // Artwork
    const artworkEl = document.getElementById("info-artwork");
    if (!isFailed && entry.hasArtwork) {
      artworkEl.src = `/artwork?path=${encodeURIComponent(entry.path)}`;
      artworkEl.style.display = "block";
    } else {
      artworkEl.style.display = "none";
    }

    if (isFailed) {
      activeFailedEntry = entry;

      failedFields.url.textContent = entry.url;
      failedFields.playlist.textContent = entry.playlist || "—";
      failedFields.index.textContent = entry.index ?? "—";
      failedFields.format.textContent = entry.format?.toUpperCase() || "—";
      failedFields.quality.textContent = entry.quality || "—";
      failedFields.type.textContent = entry.type || "—";

      failedFields.statuses.innerHTML = (entry.statuses || [])
        .map((s) => `<div>• ${s}</div>`)
        .join("");
    } else {
      // Header info
      infoFields.title.textContent = entry.title || entry.filename;
      infoFields.artist.textContent = entry.artist || "Unknown";

      infoFields.duration.textContent = entry.duration || "—";

      // Details
      infoFields.album.textContent = entry.album || "Unknown";
      infoFields.year.textContent = entry.year || "";
      infoFields.fileFormat.textContent = entry.format?.toUpperCase() || "—";
      infoFields.path.textContent = entry.path;
    }
  }

  function closeModal() {
    const isFailed = currentSource === "failed";

    const infoModal = isFailed
      ? document.getElementById("failed-modal")
      : document.getElementById("info-modal");

    infoModal.classList.add("closing");
    overlay.classList.add("closing");

    infoModal.addEventListener(
      "animationend",
      () => {
        infoModal.classList.remove("closing");
        overlay.classList.remove("closing");

        infoModal.classList.add("hidden");
        overlay.classList.add("hidden");
      },
      { once: true },
    );
  }

  overlay.addEventListener("click", () => {
    const retryModal = document.getElementById("retry-modal");
    const editModal = document.getElementById("edit-modal");

    if (!retryModal.classList.contains("hidden")) {
      closeRetryModal();
      return;
    }

    if (!editModal.classList.contains("hidden")) {
      closeEditModal();
    }

    closeModal(); // existing info/failed modal closer
  });

  document.addEventListener("click", (e) => {
    if (e.target.closest(".modal-close")) {
      closeModal();
    }
  });

  function moveFile(path) {
    alert(`Move file:\n${path}`);
  }

  document.getElementById("copy-btn").addEventListener("click", () => {
    const text = document.getElementById("info-url").textContent;

    navigator.clipboard
      .writeText(text)
      .then(() => {
        showToast("Copied!");
      })
      .catch((err) => {
        showToast("Failed to copy:", err);
      });
  });

  document.addEventListener("change", (e) => {
    if (e.target.id === "select-all-failed") {
      document
        .querySelectorAll(".retry-check")
        .forEach((cb) => (cb.checked = e.target.checked));
    }
  });

  // RETRY BULK BTN
  function getSelectedFailedEntries() {
    return [...document.querySelectorAll(".library-row.is-failed")]
      .filter((row) => row.querySelector(".retry-check")?.checked)
      .map((row) => JSON.parse(row.dataset.entry));
  }

  document.getElementById("retry-bulk-btn").addEventListener("click", () => {
    const selected = getSelectedFailedEntries();

    if (selected.length > 0) {
      retryEntries(selected);
    } else {
      openRetryModal();
    }
  });

  document
    .getElementById("retry-modal-close")
    .addEventListener("click", closeRetryModal);

  document
    .getElementById("retry-modal-cancel")
    .addEventListener("click", closeRetryModal);

  function populateRetryPlaylists() {
    const select = document.getElementById("retry-playlist-select");
    const playlists = [
      ...new Set(
        libraryCache["failed"]?.items.map((e) => e.playlist).filter(Boolean) ||
          [],
      ),
    ];

    select.innerHTML = playlists
      .map((p) => `<option value="${p}">${p}</option>`)
      .join("");
  }

  function openRetryModal() {
    populateRetryPlaylists();
    document.getElementById("retry-modal").classList.remove("hidden");
    overlay.classList.remove("hidden");
  }

  function closeRetryModal() {
    const modal = document.getElementById("retry-modal");

    modal.classList.add("closing");
    overlay.classList.add("closing");

    modal.addEventListener(
      "animationend",
      () => {
        modal.classList.remove("closing");
        overlay.classList.remove("closing");

        modal.classList.add("hidden");
        overlay.classList.add("hidden");
      },
      { once: true },
    );
  }

  document.getElementById("retry-all-btn").onclick = () => {
    retryBulk({
      mode: "all",
    });
  };

  document.getElementById("retry-count-btn").onclick = () => {
    const count = Number(document.getElementById("retry-count-input").value);

    if (!count || count <= 0) {
      showToast("Please enter a valid retry count");
      return;
    }

    retryBulk({
      mode: "count",
      count: count,
    });
  };

  document.getElementById("retry-playlist-btn").onclick = () => {
    const selectedPlaylist = document.getElementById(
      "retry-playlist-select",
    ).value;
    retryBulk({
      mode: "playlist",
      playlist: selectedPlaylist,
    });
  };

  async function retryBulk(payload) {
    showToast("Retrying failed downloads…");

    const res = await fetch("/failed/retry/bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...payload,
        audio_dir: audioDir,
        lyrics_dir: lyricsDir,
        playlist_dir: playlistDir,
      }),
    });

    const data = await res.json();

    if (data.download_id) {
      setCurrentDownloadId(data.download_id);
      startLogStream(getCurrentDownloadId());
    } else {
      throw new Error("Retry failed");
    }

    showToast(`Retrying ${data.count} entries`);
    closeRetryModal();
  }

  async function retryEntries(entries) {
    if (!entries.length) return;

    try {
      const res = await fetch("/failed/retry/bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entries: entries,
          audio_dir: audioDir,
          lyrics_dir: lyricsDir,
          playlist_dir: playlistDir,
        }),
      });

      const data = await res.json();

      if (data.download_id) {
        setCurrentDownloadId(data.download_id);
        startLogStream(getCurrentDownloadId());
      } else {
        throw new Error("Retry failed");
      }

      showToast(`Retrying ${entries.length} entries…`);

      closeRetryModal();
    } catch (e) {
      showToast(e.message);
    }
  }

  document.querySelector(".retry-btn").addEventListener("click", async () => {
    if (!activeFailedEntry) return;

    try {
      showToast("Retrying download…");

      const res = await fetch("/failed/retry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entry: activeFailedEntry,
          audio_dir: audioDir,
          lyrics_dir: lyricsDir,
          playlist_dir: playlistDir,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Retry failed");
      }
      if (data.download_id) {
        setCurrentDownloadId(data.download_id);
        startLogStream(getCurrentDownloadId());
      } else {
        throw new Error("Retry failed");
      }

      showToast("Retry started");

      closeModal();
    } catch (e) {
      showToast(e.message);
    }
  });

  let currentArtworkData = null;
  let originalArtwork = null;

  // Add this function to open the edit modal
  function openEditModal(entry) {
    const isFailed = currentSource === "failed";

    if (isFailed) {
      // Failed entries don't have audio files to edit metadata for
      showToast("Cannot edit metadata for failed downloads");
      return;
    }

    const editModal = document.getElementById("edit-modal");
    editModal.classList.remove("hidden", "closing");
    overlay.classList.remove("hidden", "closing");

    currentArtworkData = null;
    originalArtwork = null;

    // Populate form with current metadata
    document.getElementById("edit-title").value = entry.title || "";
    document.getElementById("edit-artist").value = entry.artist || "";
    document.getElementById("edit-album").value = entry.album || "";
    document.getElementById("edit-year").value = entry.year || "";

    document.getElementById("edit-filename").textContent = entry.path;

    // Store the entry path for the update
    document.getElementById("edit-modal").dataset.entryPath = entry.path;

    // Store the entry path for the update
    document.getElementById("edit-modal").dataset.entryPath = entry.path;

    // Show artwork if available
    const previewImg = document.getElementById("edit-artwork-preview");
    const placeholder = document.getElementById("edit-artwork-placeholder");

    if (entry.hasArtwork) {
      previewImg.src = `/artwork?path=${encodeURIComponent(entry.path)}`;
      previewImg.style.display = "block";

      previewImg.style.display = "block";
      placeholder.style.display = "none";
      originalArtwork = true;
    } else {
      previewImg.style.display = "none";
      placeholder.style.display = "flex";
      originalArtwork = false;
    }
    document.getElementById("edit-artwork-url-input").value = "";
    document.getElementById("edit-artwork-url-container").style.display =
      "none";
  }

  const uploadBtn = document.getElementById("edit-artwork-upload");
  const urlBtn = document.getElementById("edit-artwork-url");
  const removeBtn = document.getElementById("edit-artwork-remove");
  const fileInput = document.getElementById("edit-artwork-file");
  const urlContainer = document.getElementById("edit-artwork-url-container");
  const urlInput = document.getElementById("edit-artwork-url-input");
  const urlCancel = document.getElementById("edit-artwork-url-cancel");
  const urlLoad = document.getElementById("edit-artwork-url-load");
  const previewImg = document.getElementById("edit-artwork-preview");
  const placeholder = document.getElementById("edit-artwork-placeholder");

  // Upload button handler
  uploadBtn.addEventListener("click", () => {
    fileInput.click();
  });

  // File input handler
  fileInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
      // Validate file type
      if (!file.type.startsWith("image/")) {
        showToast("Please select an image file");
        return;
      }

      // Validate file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        showToast("Image must be less than 5MB");
        return;
      }

      currentArtworkData = {
        type: "upload",
        data: file,
      };

      // Create preview
      const reader = new FileReader();
      reader.onload = (e) => {
        previewImg.src = e.target.result;
        previewImg.style.display = "block";
        placeholder.style.display = "none";
      };
      reader.readAsDataURL(file);

      // Hide URL container if visible
      urlContainer.style.display = "none";
    }
  });

  // URL button handler
  urlBtn.addEventListener("click", () => {
    urlContainer.style.display = "flex";
    urlInput.focus();
  });

  // URL cancel button
  urlCancel.addEventListener("click", () => {
    urlContainer.style.display = "none";
    urlInput.value = "";
  });

  // URL load button
  urlLoad.addEventListener("click", async () => {
    const url = urlInput.value.trim();

    if (!url) {
      showToast("Please enter a URL");
      return;
    }

    try {
      // Validate URL
      new URL(url);

      showToast("Loading image from URL...");

      // Use a proxy to avoid CORS issues
      const proxyUrl = `/proxy-image?url=${encodeURIComponent(url)}`;

      // Create a temporary image to check if it loads
      const tempImg = new Image();
      tempImg.crossOrigin = "anonymous";

      tempImg.onload = () => {
        currentArtworkData = {
          type: "url",
          data: url,
        };

        // Show in preview
        previewImg.src = proxyUrl;
        previewImg.style.display = "block";
        placeholder.style.display = "none";
        urlContainer.style.display = "none";
        showToast("Image loaded successfully");
      };

      tempImg.onerror = () => {
        showToast("Failed to load image from URL");
      };

      tempImg.src = proxyUrl;
    } catch (error) {
      showToast("Invalid URL format");
    }
  });

  // Remove artwork button
  removeBtn.addEventListener("click", () => {
    currentArtworkData = {
      type: "remove",
      data: null,
    };

    previewImg.style.display = "none";
    placeholder.style.display = "flex";
  });

  // Add close handler for edit modal
  document
    .getElementById("edit-modal-close")
    .addEventListener("click", closeEditModal);
  document
    .getElementById("edit-modal-cancel")
    .addEventListener("click", closeEditModal);

  function closeEditModal() {
    const editModal = document.getElementById("edit-modal");

    editModal.classList.add("closing");
    overlay.classList.add("closing");

    editModal.addEventListener(
      "animationend",
      () => {
        editModal.classList.remove("closing");
        overlay.classList.remove("closing");

        editModal.classList.add("hidden");
        overlay.classList.add("hidden");

        // Clear stored data
        delete editModal.dataset.entryPath;
      },
      { once: true },
    );
  }

  // Add save handler for edit modal
  // Update the save handler to include artwork
  document
    .getElementById("edit-modal-save")
    .addEventListener("click", async () => {
      const editModal = document.getElementById("edit-modal");
      const path = editModal.dataset.entryPath;

      if (!path) {
        showToast("Error: No file selected");
        return;
      }

      const metadata = {
        title: document.getElementById("edit-title").value.trim(),
        artist: document.getElementById("edit-artist").value.trim(),
        album: document.getElementById("edit-album").value.trim(),
        year: document.getElementById("edit-year").value.trim(),
      };

      // Basic validation
      if (!metadata.title) {
        showToast("Title is required");
        return;
      }

      try {
        // Create FormData to handle file upload
        const formData = new FormData();
        formData.append("path", path);
        formData.append("metadata", JSON.stringify(metadata));

        // Handle artwork data
        if (currentArtworkData) {
          if (
            currentArtworkData.type === "upload" &&
            currentArtworkData.data instanceof File
          ) {
            formData.append("artwork_file", currentArtworkData.data);
            formData.append("artwork_type", "upload");
          } else if (currentArtworkData.type === "url") {
            formData.append("artwork_url", currentArtworkData.data);
            formData.append("artwork_type", "url");
          } else if (currentArtworkData.type === "remove") {
            formData.append("artwork_type", "remove");
          }
        } else if (originalArtwork === false) {
          // No original artwork, no new artwork - don't send anything
        } else {
          // Keep original artwork
          formData.append("artwork_type", "keep");
        }

        const response = await fetch("/metadata/update", {
          method: "POST",
          body: formData, // Note: Don't set Content-Type header for FormData
        });

        const result = await response.json();

        if (response.ok) {
          showToast("Metadata updated successfully!");
          closeEditModal();

          // Refresh the current view
          if (mode === "playlist" && currentPlaylist) {
            const cacheKey = `playlist:${currentPlaylist}`;
            delete playlistCache[cacheKey];
            await loadPlaylistPage(true);
          } else {
            libraryCache[currentSource] = {
              items: [],
              offset: 0,
              hasMore: true,
              totalCount: 0,
              totalSize: 0,
              totalDuration: 0,
            };
            await loadLibrary(true, currentSource);
          }
        } else {
          showToast(`Error: ${result.error || "Failed to update metadata"}`);
        }
      } catch (error) {
        console.error("Error updating metadata:", error);
        showToast("Failed to update metadata");
      }
    });

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
});
