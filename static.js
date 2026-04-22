
const savedTheme = localStorage.getItem("theme") || "dark";
document.documentElement.setAttribute("data-theme", savedTheme);

function updateButtons(theme) {
  const buttons = document.querySelectorAll(".theme-toggle");

  buttons.forEach(btn => {
    btn.textContent = theme === "light" ? "☀️ Light" : "🌙 Dark";
  });
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme");
  const newTheme = current === "light" ? "dark" : "light";

  document.documentElement.setAttribute("data-theme", newTheme);
  localStorage.setItem("theme", newTheme);

  updateButtons(newTheme);
}

document.addEventListener("DOMContentLoaded", () => {
  const theme = localStorage.getItem("theme") || "dark";

  updateButtons(theme);

  // Supports multiple buttons across pages
  document.querySelectorAll(".theme-toggle").forEach(btn => {
    btn.addEventListener("click", toggleTheme);
  });
});

