// static/js/script.js

document.addEventListener("DOMContentLoaded", () => {
  const historyContainer = document.getElementById("history-container");
  const historyWeekSelect = document.getElementById("history-week");
  const refreshHistoryBtn = document.getElementById("refresh-history");
  const historyButton = document.getElementById("history-button");

  historyButton.addEventListener("click", () => {
    const historyPanel = document.querySelector(".history-panel");
    historyPanel.scrollIntoView({ behavior: "smooth" });

    // Pulse animation for attention
    historyPanel.animate(
      [
        { backgroundColor: "transparent" },
        { backgroundColor: "rgba(31, 197, 197, 0.2)" },
        { backgroundColor: "transparent" },
      ],
      {
        duration: 1000,
        iterations: 1,
      },
    );
  });

  // Load history files
  async function loadHistoryFiles() {
    // Month names for readable formatting
    const monthNames = [
      "January",
      "February",
      "March",
      "April",
      "May",
      "June",
      "July",
      "August",
      "September",
      "October",
      "November",
      "December",
    ];

    try {
      const response = await fetch("/history_files");
      const files = await response.json();
      historyWeekSelect.innerHTML = "";

      // Add current week option
      const currentOption = document.createElement("option");
      currentOption.value = "current";
      currentOption.textContent = "Current Week";
      historyWeekSelect.appendChild(currentOption);

      // Process and add history files
      files.forEach((file) => {
        const option = document.createElement("option");
        option.value = file;

        // Extract date parts from filename
        const dateString = file.match(
          /history_(\d{4})-(\d{2})-(\d{2})_to_(\d{4})-(\d{2})-(\d{2})\.json/,
        );

        if (dateString) {
          // Parse dates
          const [, startY, startM, startD, endY, endM, endD] = dateString;
          const startDate = new Date(startY, startM - 1, startD);
          const endDate = new Date(endY, endM - 1, endD);

          // Format readable date range
          let displayText;
          if (startDate.getFullYear() === endDate.getFullYear()) {
            if (startDate.getMonth() === endDate.getMonth()) {
              // Same month: "July 21-27, 2025"
              displayText = `${monthNames[startDate.getMonth()]} ${startDate.getDate()}-${endDate.getDate()}, ${startY}`;
            } else {
              // Different months, same year: "July 21 - August 3, 2025"
              displayText = `${monthNames[startDate.getMonth()]} ${startDate.getDate()} - ${monthNames[endDate.getMonth()]} ${endDate.getDate()}, ${startY}`;
            }
          } else {
            // Different years: "December 28, 2025 - January 3, 2026"
            displayText = `${monthNames[startDate.getMonth()]} ${startDate.getDate()}, ${startY} - ${monthNames[endDate.getMonth()]} ${endDate.getDate()}, ${endY}`;
          }
          option.textContent = displayText;
        } else {
          // Fallback to original format if parsing fails
          option.textContent = file
            .replace("history_", "")
            .replace(".json", "")
            .replace(/_/g, " ");
        }

        historyWeekSelect.appendChild(option);
      });

      // Load current week's history
      loadHistoryData("current");
    } catch (error) {
      console.error("Error loading history files:", error);
    }
  }

  // Load history data
  async function loadHistoryData(week) {
    try {
      let url = "/history";
      if (week !== "current") {
        url += `?week=${encodeURIComponent(week)}`;
      }

      const response = await fetch(url);
      const history = await response.json();

      // Clear container
      historyContainer.innerHTML = "";

      if (history.length === 0) {
        historyContainer.innerHTML = `
                    <div class="history-placeholder">
                        <i class="fas fa-history fa-3x"></i>
                        <p>No downloads found for this period</p>
                    </div>
                `;
        return;
      }

      // Add history items
      history.forEach((entry) => {
        const item = document.createElement("div");
        item.className = "history-item";

        // Format timestamp
        const date = new Date(entry.timestamp);
        const formattedDate = date.toLocaleString();

        // Determine icon based on type
        const icon =
          entry.type === "playlist"
            ? '<i class="fas fa-list"></i>'
            : '<i class="fas fa-music"></i>';

        item.innerHTML = `
                    <div class="history-header">
                        <div class="history-title"><sapn style="word-break: break-word;">${entry.title}</sapn></div>
                        <div class="history-type">${icon} ${entry.type}</div>
                    </div>
                    <div class="history-artist">${entry.artist || "Unknown Artist"}</div>
                    <div class="history-meta">
                        <span>${entry.quality} kbps • ${entry.format.toUpperCase()}</span>
                        <span>${formattedDate}
                            <span class="history-status status-${entry.status || "downloaded"}">
                                ${entry.status === "skipped" ? "Skipped" : "Downloaded"}
                            </span>
                        </span>
                    </div>
                    <div class="history-path" title="${entry.file_path}">
                        <i class="fas fa-folder"></i> ${entry.file_path}
                    </div>
                `;
        if (entry.status === "skipped") {
          item.classList.add("history-skipped");
        }
        historyContainer.appendChild(item);
      });
    } catch (error) {
      console.error("Error loading history data:", error);
      historyContainer.innerHTML = `
                <div class="alert alert-danger">
                    Failed to load history data: ${error.message}
                </div>
            `;
    }
  }

  // Helper to truncate long paths
  function truncatePath(path, maxLength) {
    if (path.length <= maxLength) return path;

    const parts = path.split("/");
    let result = "";

    while (parts.length > 0) {
      const part = parts.shift();
      if (result.length + part.length + 1 <= maxLength - 3) {
        result += (result ? "/" : "") + part;
      } else {
        result += "/.../" + parts.pop();
        break;
      }
    }

    return result;
  }

  // Event listeners
  historyWeekSelect.addEventListener("change", () => {
    loadHistoryData(historyWeekSelect.value);
  });

  refreshHistoryBtn.addEventListener("click", () => {
    loadHistoryFiles();
  });

  // Load history on page load
  loadHistoryFiles();
});
