document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("library-container");
  const searchInput = document.getElementById("library-search");
  const filterSelect = document.getElementById("library-filter");

  let library = [];
  let offset = 0;
  const limit = 25;
  let loading = false;
  let hasMore = true;
  let audioDir = null;

  async function loadLibrary(reset = false) {
    if (searchInput.value.trim() !== "") return;

    if (loading || (!hasMore && !reset)) return;

    loading = true;
  
    try {
      if (!audioDir) {
      const prefs = await (await fetch("/preferences")).json();
      audioDir = prefs.audioDir;
    }

      if (reset) {
      offset = 0;
      hasMore = true;
      library = [];
      container.innerHTML = "";
    }

    const res = await fetch(
      `/library?dir=${encodeURIComponent(audioDir)}&offset=${offset}&limit=${limit}`
    );

      const data = await res.json();

      hasMore = data.hasMore;
      offset += limit;
      library.push(...data.items);

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

  function renderLibrary(items, clear = false) {
    if (clear) container.innerHTML = "";

    if (!items.length) {
      container.innerHTML = `
        <div class="history-placeholder">
          <i class="fas fa-music fa-3x"></i>
          <p>No matching files found</p>
        </div>
      `;
      return;
    }

    items.forEach((entry) => {
      const item = document.createElement("div");
      item.className = "history-item library-item";

      item.innerHTML = `
        <div class="history-header">
          <div class="history-title">${entry.title}</div>
          <div class="library-actions">
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
  </div>
        </div>
        <div class="history-artist">${entry.artist}</div>
        <div class="history-meta">
          <span>${entry.album}</span>
          <span>${entry.year || ""}</span>
        </div>
        <div class="history-path">
          <i class="fas fa-folder"></i> ${entry.path}
        </div>
      `;

      item.dataset.entry = JSON.stringify(entry);

      container.appendChild(item);
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
      loadLibrary();
    }
  });

  loadLibrary(true);


container.addEventListener("click", (e) => {
  const btn = e.target.closest(".actions-menu button");
  if (!btn) return;

  const item = btn.closest(".library-item");
  const entry = JSON.parse(item.dataset.entry);

  if (btn.dataset.action === "info") {
    openInfoModal(entry);
  }
});


const infoModal = document.getElementById("info-modal");
const overlay = document.getElementById("modal-overlay");

const infoFields = {
  title: document.getElementById("info-title"),
  artist: document.getElementById("info-artist"),
  album: document.getElementById("info-album"),
  year: document.getElementById("info-year"),
  format: document.getElementById("info-format"),
  path: document.getElementById("info-path"),
};

function openInfoModal(entry) {
  infoModal.classList.remove("hidden", "closing");
  overlay.classList.remove("hidden", "closing");

  infoFields.title.textContent = entry.title;
  infoFields.artist.textContent = entry.artist || "Unknown";
  infoFields.album.textContent = entry.album || "Unknown";
  infoFields.year.textContent = entry.year || "";
  infoFields.format.textContent = entry.format.toUpperCase();
  infoFields.path.textContent = entry.path;

  overlay.classList.remove("hidden");
  infoModal.classList.remove("hidden");
}


function closeModal() {
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
    { once: true }
  );
}


overlay.addEventListener("click", closeModal);
document
  .querySelector(".modal-close")
  .addEventListener("click", closeModal);



function openEditDialog(title, path) {
  alert(`Edit metadata for:\n${title}`);
}

function moveFile(path) {
  alert(`Move file:\n${path}`);
}
});
