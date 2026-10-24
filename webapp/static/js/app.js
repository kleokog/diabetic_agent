import { initImports, loadImportHistory, showImportView } from "./imports.js";
import { initSettings, loadSettings } from "./settings.js";
import { loadToday, redrawChart } from "./today.js";

const VIEWS = ["today", "trends", "coach", "journal", "settings", "import"];
const NAV_FOR_VIEW = { import: "settings" };

function currentView() {
  const name = window.location.hash.replace("#", "");
  return VIEWS.includes(name) ? name : "today";
}

function showView() {
  const name = currentView();
  const navName = NAV_FOR_VIEW[name] || name;
  document.querySelectorAll("[data-view]").forEach((view) => {
    view.hidden = view.dataset.view !== name;
  });
  document.querySelectorAll("[data-nav]").forEach((link) => {
    link.classList.toggle("active", link.dataset.nav === navName);
  });
  if (name === "today") redrawChart();
  if (name === "settings") {
    loadSettings().catch(showError);
    loadImportHistory().catch(showError);
  }
  if (name === "import") showImportView();
  window.scrollTo({ top: 0 });
}

function showError(error) {
  console.error(error);
}

function initSheet() {
  const sheet = document.getElementById("log-sheet");
  const backdrop = document.getElementById("sheet-backdrop");
  const open = () => { sheet.hidden = false; backdrop.hidden = false; };
  const close = () => { sheet.hidden = true; backdrop.hidden = true; };
  document.querySelectorAll("[data-open-sheet]").forEach((button) => button.addEventListener("click", open));
  document.querySelectorAll("[data-close-sheet]").forEach((button) => button.addEventListener("click", close));
  backdrop.addEventListener("click", close);
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") close(); });
}

let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(redrawChart, 150);
});
window.addEventListener("hashchange", showView);

initSheet();
initSettings(() => loadToday().catch(showError));
initImports(() => {
  loadToday().catch(showError);
  loadImportHistory().catch(showError);
});
showView();
loadToday().catch(showError);
