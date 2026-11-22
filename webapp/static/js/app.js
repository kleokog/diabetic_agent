import { ensureCoach, initCoach, loadCoach } from "./coach.js";
import { initImports, loadImportHistory, showImportView } from "./imports.js";
import { ensureLifestyle, initLifestyle, loadLifestyle } from "./lifestyle.js";
import { initSettings, loadSettings } from "./settings.js";
import { ensureTrends, initTrends, loadTrends } from "./trends.js";
import { initToday, loadToday, redrawChart } from "./today.js";

const VIEWS = ["today", "trends", "lifestyle", "coach", "journal", "settings", "import"];
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
  if (name === "trends") ensureTrends().catch(showError);
  if (name === "lifestyle") ensureLifestyle().catch(showError);
  if (name === "coach") ensureCoach().catch(showError);
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
initToday();
initTrends();
initLifestyle();
initCoach();
initSettings(() => {
  loadToday().catch(showError);
  loadTrends().catch(showError);
  loadLifestyle().catch(showError);
  loadCoach().catch(showError);
});
initImports(() => {
  loadToday().catch(showError);
  loadTrends().catch(showError);
  loadLifestyle().catch(showError);
  loadCoach().catch(showError);
  loadImportHistory().catch(showError);
});
showView();
loadToday().catch(showError);
loadCoach().catch(showError);
