import { apiGet } from "./api.js";
import { renderDayChart } from "./chart.js";
import { bandFor, formatDayTitle, formatShortDate, formatTime } from "./format.js";

const TREND_ROTATION = { rising_fast: 0, rising: 45, steady: 90, falling: 135, falling_fast: 180 };
const RING_CIRCUMFERENCE = 2 * Math.PI * 52;

const $ = (id) => document.getElementById(id);
let current = null;

export async function loadToday(date) {
  const data = await apiGet(date ? `/today?date=${date}` : "/today");
  current = data;
  render(data);
}

export function redrawChart() {
  if (current) drawChart(current);
}

export function initToday() {
  const tip = $("cv-tip");
  const btn = $("cv-tip-btn");
  if (!btn || !tip) return;
  btn.addEventListener("click", () => {
    const open = tip.hidden;
    tip.hidden = !open;
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  });
}

function render(data) {
  const isToday = data.date === data.today;
  $("today-eyebrow").textContent = isToday ? "Today" : "Day view";
  $("today-title").textContent = formatDayTitle(data.date);
  $("day-prev").disabled = !data.prev_date;
  $("day-next").disabled = !data.next_date;
  $("day-prev").onclick = () => data.prev_date && loadToday(data.prev_date);
  $("day-next").onclick = () => data.next_date && loadToday(data.next_date);

  const notice = $("stale-notice");
  if (!data.latest_data_date) {
    notice.hidden = false;
    $("stale-text").textContent = "No glucose data yet. Import a LibreLink export to get started.";
  } else if (data.latest_data_date < data.today && data.date === data.latest_data_date) {
    notice.hidden = false;
    $("stale-text").textContent = `Your latest glucose data is from ${formatShortDate(data.latest_data_date)}. Import a new LibreLink export to see recent days.`;
  } else {
    notice.hidden = true;
  }

  renderHero(data);
  renderLatest(data);
  renderTimeInRange(data);
  renderStats(data);
  drawChart(data);
}

function renderHero(data) {
  const has = data.readings.length > 0;
  const threshold = data.cv_unstable_pct ?? 36;
  $("cv-tip-threshold").textContent = String(threshold);

  const avgBadge = $("hero-avg-badge");
  if (has && data.average !== null) {
    $("hero-average").textContent = String(data.average);
    const band = bandFor(data.average, data.target_low, data.target_high);
    avgBadge.textContent = band.label;
    avgBadge.dataset.band = band.key;
  } else {
    $("hero-average").textContent = "–";
    avgBadge.textContent = "No data";
    avgBadge.removeAttribute("data-band");
  }
  if (has && data.min != null && data.max != null) {
    $("hero-range").textContent = `Range ${data.min}–${data.max}`;
  } else {
    $("hero-range").textContent = "";
  }

  const cv = data.variability;
  const badge = $("hero-cv-badge");
  if (cv) {
    $("hero-cv").textContent = String(cv.cv_pct);
    badge.textContent = cv.label;
    badge.dataset.spectrum = cv.spectrum || "";
    badge.removeAttribute("data-stability");
    $("hero-cv-meta").textContent = `typically ±${Math.round(cv.sd)} from average`;
    $("hero-cv-meta").dataset.spectrum = cv.spectrum || "";
  } else {
    $("hero-cv").textContent = "–";
    badge.textContent = has ? "Need more data" : "No data";
    badge.dataset.spectrum = "";
    badge.removeAttribute("data-stability");
    $("hero-cv-meta").textContent = has ? `~8h sensor needed · line at ${threshold}%` : "";
    $("hero-cv-meta").dataset.spectrum = "";
  }
}

function renderLatest(data) {
  const latest = data.latest;
  const inline = $("latest-inline");
  const state = $("latest-state");
  const arrow = $("latest-trend");
  if (!latest) {
    inline.hidden = true;
    $("latest-value").textContent = "–";
    state.textContent = "No data";
    state.removeAttribute("data-band");
    $("latest-time").textContent = "";
    arrow.toggleAttribute("hidden", true);
    return;
  }
  inline.hidden = false;
  const band = bandFor(latest.v, data.target_low, data.target_high);
  $("latest-value").textContent = `${latest.v}`;
  state.textContent = band.label;
  state.dataset.band = band.key;
  $("latest-time").textContent = `at ${formatTime(latest.t)}`;
  arrow.toggleAttribute("hidden", !latest.trend);
  if (latest.trend) {
    arrow.style.transform = `rotate(${TREND_ROTATION[latest.trend.direction]}deg)`;
    arrow.setAttribute("aria-label", latest.trend.direction.replace("_", " "));
  }
}

function renderTimeInRange(data) {
  const inRange = data.bands.find((b) => b.key === "in_range");
  const hasData = data.readings.length > 0;
  const pct = hasData ? inRange.pct : 0;
  $("tir-value").textContent = hasData ? `${Math.round(pct)}%` : "–";
  $("tir-caption").textContent = `in ${data.target_low}–${data.target_high}`;
  $("tir-ring").style.strokeDashoffset = String(RING_CIRCUMFERENCE * (1 - pct / 100));

  const bar = $("band-bar");
  bar.replaceChildren(
    ...[...data.bands].reverse().filter((b) => b.pct > 0).map((b) => {
      const span = document.createElement("span");
      span.className = `band-${b.key}`;
      span.style.width = `${b.pct}%`;
      return span;
    }),
  );

  const legend = $("band-legend");
  legend.replaceChildren(
    ...[...data.bands].reverse().map((b) => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="band-dot band-${b.key}"></span><span></span><strong></strong>`;
      li.children[1].textContent = b.label;
      li.children[2].textContent = hasData ? `${Math.round(b.pct)}%` : "–";
      return li;
    }),
  );
}

function renderStats(data) {
  const has = data.readings.length > 0;
  $("stat-lows").textContent = has ? String(data.lows) : "–";
  $("stat-above-label").textContent = `Hours above ${data.target_high}`;
  $("stat-above").innerHTML = has ? `${data.hours_above_target}<small>h</small>` : "–";
  const rapidDoses = data.insulin.filter((d) => d.kind === "rapid").length;
  $("stat-insulin").innerHTML = rapidDoses
    ? `${formatUnits(data.insulin_totals.rapid)}<small>u · ${rapidDoses}</small>`
    : "–";

  const long = data.last_long;
  if (long) {
    $("stat-long").innerHTML = `${formatUnits(long.units)}<small>u</small>`;
    $("stat-long-meta").textContent = long.t.slice(0, 10) < data.date
      ? `at ${formatTime(long.t)} yesterday`
      : `at ${formatTime(long.t)}`;
  } else {
    $("stat-long").textContent = "–";
    $("stat-long-meta").textContent = "";
  }
  $("chart-subtitle").textContent = `24 hours · ${data.target_low}–${data.target_high} shaded`;
}

function formatUnits(value) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function drawChart(data) {
  const meals = data.meals || [];
  const workouts = data.workouts || [];
  renderDayChart($("day-chart"), $("chart-tooltip"), {
    readings: data.readings,
    insulin: data.insulin,
    meals,
    workouts,
    targetLow: data.target_low,
    targetHigh: data.target_high,
  });
  const legend = $("event-legend");
  if (legend) {
    const walks = workouts.filter((w) => isWalkingActivity(w.activity));
    const training = workouts.filter((w) => !isWalkingActivity(w.activity));
    const show = meals.length > 0 || workouts.length > 0;
    legend.hidden = !show;
    legend.querySelector(".event-legend-meal").hidden = meals.length === 0;
    legend.querySelector(".event-legend-walk").hidden = walks.length === 0;
    legend.querySelector(".event-legend-training").hidden = training.length === 0;
  }
}

function isWalkingActivity(activity) {
  const name = String(activity || "").trim().toLowerCase();
  return name === "walking" || name === "walk" || name === "hike" || name === "hiking" || name.includes("walk");
}
