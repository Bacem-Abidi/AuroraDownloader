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

  let library = [];
  let offset = 0;
  const limit = 25;
  let loading = false;
  let hasMore = true;
  let currentSource = "all";
  let playlistDir = null;
  let audioDir = null;
  let lyricsDir = null;
  let mode = "library"; // "library" | "playlist"
  let currentPlaylist = null;
  let totalCount = 0;
  let activeFailedEntry = null;

  function updateGridMode(source) {
    const header = document.getElementById("library-row-header");

    header.classList.toggle("is-library", source !== "failed");
    header.classList.toggle("is-failed", source === "failed");
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

    loadLibrary(true, source);
  }

  async function selectPlaylist(name) {
    mode = "playlist";
    currentPlaylist = name;

    currentSource = "playlist";

    updateGridMode(currentSource);

    libraryTitle.textContent = name.replace(/\.m3u$/i, "");
    libraryMeta.textContent = "Playlist";

    offset = 0;
    hasMore = true;
    loading = false;
    library = [];
    container.innerHTML = "";
    header.innerHTML = HEADERS.all;

    loadPlaylistPage(true);
  }

  async function loadPlaylistPage(reset = false) {
    if (loading || (!hasMore && !reset)) return;

    loading = true;

    try {
      const res = await fetch(
        `/playlist/${encodeURIComponent(currentPlaylist)}?` +
          `audioDir=${encodeURIComponent(audioDir)}` +
          `&playlistDir=${encodeURIComponent(playlistDir)}` +
          `&offset=${offset}&limit=${limit}`,
      );

      const data = await res.json();

      hasMore = data.hasMore;
      offset += limit;
      library.push(...data.items);

      totalCount = data.total;
      libraryMeta.textContent = `${library.length} / ${totalCount} tracks`;

      renderLibrary(data.items);
    } catch (e) {
      console.error("Error loading playlist:", e);
    } finally {
      loading = false;
    }
  }

  async function loadLibrary(reset = false, source = "all") {
    if (searchInput.value.trim() !== "") return;

    if (loading || (!hasMore && !reset)) return;

    loading = true;

    try {
      if (reset) {
        offset = 0;
        hasMore = true;
        library = [];
        container.innerHTML = "";
      }

      let endpoint;

      if (source === "failed") {
        endpoint = `/failed?offset=${offset}&limit=${limit}`;
      } else {
        if (!audioDir) {
          const prefs = await (await fetch("/preferences")).json();
          audioDir = prefs.audioDir;
          playlistDir = prefs.playlistDir;
          lyricsDir = prefs.lyricsDir;
        }
        endpoint = `/library?dir=${encodeURIComponent(audioDir)}&offset=${offset}&limit=${limit}&reset=${reset}`;
      }

      const res = await fetch(endpoint);

      const data = await res.json();

      hasMore = data.hasMore;
      offset += limit;
      library.push(...data.items);

      totalCount = data.total;
      libraryMeta.textContent = `${library.length} / ${totalCount} tracks`;

      renderLibrary(data.items);
    } catch (error) {
      console.error("Error loading library:", error);
      container.innerHTML = `
        <div class="history-placeholder">
          <i class="fas fa-exclamation-circle fa-3x"></i>
          <p>Failed to load library</p>
        </div>
      `;
    } finally {
      loading = false;
    }
  }

  // function renderLibrary(items, clear = false) {
  //   if (clear) container.innerHTML = "";
  //
  //   if (!items.length) {
  //     container.innerHTML = `
  //       <div class="history-placeholder">
  //         <i class="fas fa-music fa-3x"></i>
  //         <p>No matching files found</p>
  //       </div>
  //     `;
  //     return;
  //   }
  //
  //   items.forEach((entry) => {
  //     const item = document.createElement("div");
  //     item.className = "history-item library-item";
  //
  //     item.innerHTML = `
  //       <div class="history-header">
  //         <div class="history-title">${entry.title}</div>
  //         <div class="library-actions">
  //     <button class="actions-btn" aria-label="Actions">
  //       <i class="fas fa-ellipsis-v"></i>
  //     </button>
  //
  //     <div class="actions-menu">
  //       <button data-action="info">
  //         <i class="fas fa-info-circle"></i> Info
  //       </button>
  //       <button data-action="edit">
  //         <i class="fas fa-pen"></i> Edit
  //       </button>
  //       <button data-action="move">
  //         <i class="fas fa-folder-open"></i> Move location
  //       </button>
  //     </div>
  //   </div>
  // </div>
  //       </div>
  //       <div class="history-artist">${entry.artist}</div>
  //       <div class="history-meta">
  //         <span>${entry.album}</span>
  //         <span>${entry.year || ""}</span>
  //       </div>
  //       <div class="history-path">
  //         <i class="fas fa-folder"></i> ${entry.path}
  //       </div>
  //     `;
  //
  //     item.dataset.entry = JSON.stringify(entry);
  //
  //     container.appendChild(item);
  //   });
  // }

  function renderLibrary(items, clear = false) {
    if (clear) {
      container.innerHTML = "";
    }

    if (!items.length && clear) {
      container.innerHTML += `
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

  function truncatePath(path, maxLength) {
    if (!path || path.length <= maxLength) return path;

    const parts = path.split("/");
    return `${parts[0]}/.../${parts[parts.length - 1]}`;
  }

  function getFilteredLibrary() {
    const query = searchInput.value.toLowerCase().trim();
    const filter = filterSelect.value;

    return library.filter((item) => {
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
  }

  searchInput.addEventListener("input", applyFilters);
  filterSelect.addEventListener("change", applyFilters);

  container.addEventListener("scroll", () => {
    if (
      container.scrollTop + container.clientHeight >=
      container.scrollHeight - 50
    ) {
      if (mode === "library") {
        loadLibrary();
      } else if (mode === "failed") {
        loadLibrary(false, "failed");
      } else if (mode === "playlist") {
        loadPlaylistPage();
      }
    }
  });

  loadLibrary(true);
  updateGridMode(currentSource);
  loadPlaylists();

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
    url: document.getElementById("info-url"),
    playlist: document.getElementById("info-playlist"),
    index: document.getElementById("info-index"),
    format: document.getElementById("info-format"),
    quality: document.getElementById("info-quality"),
    type: document.getElementById("info-type"),
    statuses: document.getElementById("info-statuses"),
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

    if (!retryModal.classList.contains("hidden")) {
      closeRetryModal();
      return;
    }

    closeModal(); // existing info/failed modal closer
  });

  document.addEventListener("click", (e) => {
    if (e.target.closest(".modal-close")) {
      closeModal();
    }
  });

  function openEditDialog(title, path) {
    alert(`Edit metadata for:\n${title}`);
  }

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

  function populateRetryPlaylists() {
    const select = document.getElementById("retry-playlist-select");
    const playlists = [
      ...new Set(library.map((e) => e.playlist).filter(Boolean)),
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
    retryEntries(library);
  };

  document.getElementById("retry-playlist-btn").onclick = () => {
    const playlist = document.getElementById("retry-playlist-select").value;
    const entries = library.filter((e) => e.playlist === playlist);
    retryEntries(entries);
  };

  async function retryEntries(entries) {
    if (!entries.length) return;

    showToast(`Retrying ${entries.length} entries…`);

    // const res = await fetch("/failed/retry/bulk", {
    //   method: "POST",
    //   headers: { "Content-Type": "application/json" },
    //   body: JSON.stringify({
    //     entries,
    //     audio_dir: audioDir,
    //     lyrics_dir: lyricsDir,
    //     playlist_dir: playlistDir,
    //   }),
    // });
    //
    // const data = await res.json();
    //
    // if (data.download_id) {
    //   setCurrentDownloadId(data.download_id);
    //   startLogStream(getCurrentDownloadId());
    // }
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
