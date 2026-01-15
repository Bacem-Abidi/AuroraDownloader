document.addEventListener("DOMContentLoaded", () => {
  const threshold = document.getElementById("strong-match-threshold");
  const valueLabel = document.getElementById("threshold-value");

  threshold.addEventListener("input", () => {
    valueLabel.textContent = threshold.value + "%";
  });
});
