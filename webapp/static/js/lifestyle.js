import { apiGet } from "./api.js";
import { formatShortDate, parseLocal } from "./format.js";

const $ = (id) => document.getElementById(id);
const DONUT_R = 46;
const DONUT_C = 2 * Math.PI * DONUT_R;

const MACRO_COLORS = {
  carbs: "#c47a2c",
  protein: "#2f8a6b",
  fat: "#5a5fc7",
};

let days = 14;
let loaded = false;

export async function loadLifestyle(periodDays = days) {
  days = periodDays;
  document.querySelectorAll("#lifestyle-periods .period-pill").forEach((btn) => {
    btn.classList.toggle("active", Number(btn.dataset.days) === days);
  });
  const data = await apiGet(`/lifestyle?days=${days}`);
  render(data);
  loaded = true;
}

export function initLifestyle() {
  document.querySelectorAll("#lifestyle-periods .period-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      loadLifestyle(Number(btn.dataset.days)).catch((error) => console.error(error));
    });
  });
}

export function ensureLifestyle() {
  if (!loaded) return loadLifestyle();
  return Promise.resolve();
}

function rangeLabel(prefix, data) {
  if (!data.start || !data.end) return prefix;
  return `${prefix} · ${formatShortDate(data.start)} – ${formatShortDate(data.end)}`;
}

function render(data) {
  const notice = $("lifestyle-notice");
  if (!data.has_food && !data.has_sleep && !data.has_activity) {
    notice.hidden = false;
    $("lifestyle-notice-text").textContent =
      "No food or Whoop data yet. Import Cronometer servings + daily summary, and Whoop sleeps / workouts / cycles.";
  } else {
    notice.hidden = true;
  }

  renderFood(data);
  renderSleep(data);
  renderActivity(data);
}

function renderFood(data) {
  const food = data.food || {};
  const has = data.has_food;

  $("food-range").textContent = has
    ? rangeLabel("Cronometer", data)
    : "Import Cronometer servings + daily summary";

  $("food-avg-carbs").textContent =
    has && food.avg_carbs != null ? String(Math.round(food.avg_carbs)) : "–";
  $("food-meals").textContent = has && food.avg_meals_per_day != null ? String(food.avg_meals_per_day) : "–";
  $("food-snacks").textContent = has && food.avg_snacks_per_day != null ? String(food.avg_snacks_per_day) : "–";

  drawMacroDonut(food.macro_pct || {}, has);
  renderMacroLegend(food.macro_pct || {}, has);
  renderStackedMacros(food.daily_macros || food.daily_carbs || []);
  renderInsights("food-insights", has ? food.insights : ["Import Cronometer to see carbs and macros."]);
}

function drawMacroDonut(pct, has) {
  const svg = $("macro-donut");
  svg.replaceChildren();
  const track = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  track.setAttribute("class", "donut-track");
  track.setAttribute("cx", "60");
  track.setAttribute("cy", "60");
  track.setAttribute("r", String(DONUT_R));
  svg.append(track);

  if (!has) return;
  const parts = [
    { key: "carbs", value: pct.carbs },
    { key: "protein", value: pct.protein },
    { key: "fat", value: pct.fat },
  ].filter((p) => p.value != null && p.value > 0);
  const total = parts.reduce((sum, p) => sum + p.value, 0);
  if (!total) return;

  let offset = 0;
  for (const part of parts) {
    const len = (part.value / total) * DONUT_C;
    const seg = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    seg.setAttribute("class", `donut-seg macro-${part.key}`);
    seg.setAttribute("cx", "60");
    seg.setAttribute("cy", "60");
    seg.setAttribute("r", String(DONUT_R));
    seg.setAttribute("stroke", MACRO_COLORS[part.key]);
    seg.setAttribute("stroke-dasharray", `${len} ${DONUT_C - len}`);
    seg.setAttribute("stroke-dashoffset", String(-offset));
    svg.append(seg);
    offset += len;
  }
}

function renderMacroLegend(pct, has) {
  const root = $("macro-legend");
  if (!has || pct.carbs == null) {
    root.replaceChildren();
    return;
  }
  const items = [
    ["carbs", "Carbs", pct.carbs],
    ["protein", "Protein", pct.protein],
    ["fat", "Fat", pct.fat],
  ];
  root.replaceChildren(
    ...items.map(([key, label, value]) => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="macro-swatch macro-${key}"></span><span></span><strong></strong>`;
      li.querySelector("span:nth-child(2)").textContent = label;
      li.querySelector("strong").textContent = value != null ? `${Math.round(value)}%` : "–";
      return li;
    }),
  );
}

function renderStackedMacros(series) {
  const root = $("macro-bars");
  if (!series.length) {
    root.replaceChildren();
    return;
  }
  const totals = series.map((d) => {
    if (d.carbs == null && d.protein == null && d.fat == null) return null;
    return (d.carbs || 0) + (d.protein || 0) + (d.fat || 0);
  });
  const max = Math.max(40, ...totals.filter((v) => v != null), 0);

  root.replaceChildren(
    ...series.map((d, i) => {
      const col = document.createElement("div");
      col.className = "life-bar-col";
      const stack = document.createElement("div");
      stack.className = "life-stack";
      const total = totals[i];
      if (total == null || total <= 0) {
        const empty = document.createElement("div");
        empty.className = "life-bar empty";
        stack.append(empty);
      } else {
        for (const key of ["fat", "protein", "carbs"]) {
          const grams = d[key] || 0;
          if (grams <= 0) continue;
          const seg = document.createElement("div");
          seg.className = `life-stack-seg macro-${key}`;
          seg.style.flexGrow = String(grams);
          seg.title = `${formatShortDate(d.date)} · ${Math.round(d.carbs || 0)}g C / ${Math.round(d.protein || 0)}g P / ${Math.round(d.fat || 0)}g F`;
          stack.append(seg);
        }
        stack.style.height = `${Math.max(8, (total / max) * 100)}%`;
      }
      const label = document.createElement("span");
      label.textContent = dayLabel(d.date);
      col.append(stack, label);
      return col;
    }),
  );
}

function renderSleep(data) {
  const sleep = data.sleep || {};
  const overall = sleep.overall || {};
  const weekday = sleep.weekday || {};
  const weekend = sleep.weekend || {};
  const has = data.has_sleep;

  $("sleep-range").textContent = has ? rangeLabel("Whoop", data) : "Import Whoop sleeps.csv";

  $("sleep-avg-hours").textContent =
    has && overall.avg_hours != null ? `${overall.avg_hours} h` : "–";
  $("sleep-window").textContent =
    has && overall.typical_bedtime && overall.typical_wake
      ? `${overall.typical_bedtime}–${overall.typical_wake}`
      : "–";
  $("sleep-quality").textContent =
    has && overall.avg_quality_pct != null ? `${Math.round(overall.avg_quality_pct)}%` : "–";

  fillSleepCol("wd", weekday, has);
  fillSleepCol("we", weekend, has);

  const maxH = Math.max(8, weekday.avg_hours || 0, weekend.avg_hours || 0);
  setDurationFill("sleep-wd-fill", weekday.avg_hours, maxH, has);
  setDurationFill("sleep-we-fill", weekend.avg_hours, maxH, has);

  renderInsights("sleep-insights", has ? sleep.insights : ["Import Whoop sleep to see duration and quality."]);
}

function fillSleepCol(prefix, bucket, has) {
  const hours = has && bucket.avg_hours != null ? `${bucket.avg_hours} h` : "–";
  const window =
    has && bucket.typical_bedtime && bucket.typical_wake
      ? `${bucket.typical_bedtime}–${bucket.typical_wake}`
      : "–";
  const quality =
    has && bucket.avg_quality_pct != null ? `${Math.round(bucket.avg_quality_pct)}%` : "–";
  $(`sleep-${prefix}-hours`).textContent = hours;
  $(`sleep-${prefix}-window`).textContent = window;
  $(`sleep-${prefix}-quality`).textContent = quality;
}

function setDurationFill(id, hours, maxH, has) {
  const el = $(id);
  if (!has || hours == null) {
    el.style.width = "0%";
    return;
  }
  el.style.width = `${Math.max(8, (hours / maxH) * 100)}%`;
}

function renderActivity(data) {
  const act = data.activity || {};
  const has = data.has_activity;

  $("activity-range").textContent = has
    ? rangeLabel("Whoop", data)
    : "Import Whoop workouts + physiological cycles";

  if (has) {
    $("act-training-days").textContent = String(act.training_days ?? "–");
    $("act-training-pct").textContent =
      act.training_day_pct != null ? `${Math.round(act.training_day_pct)}% of days` : "";
    if (act.avg_workout_hr != null) {
      $("act-workout-hr").innerHTML = `${Math.round(act.avg_workout_hr)}<small>bpm</small>`;
    } else {
      $("act-workout-hr").textContent = "–";
    }
    if (act.avg_walk_min != null) {
      $("act-walk-min").innerHTML = `${Math.round(act.avg_walk_min)}<small>min</small>`;
    } else {
      $("act-walk-min").textContent = "–";
    }
    $("act-walk-steps").textContent =
      act.avg_est_steps != null ? `~${Math.round(act.avg_est_steps).toLocaleString()} est. steps` : "";
    if (act.avg_resting_hr != null) {
      $("act-rhr").innerHTML = `${Math.round(act.avg_resting_hr)}<small>bpm</small>`;
    } else {
      $("act-rhr").textContent = "–";
    }
  } else {
    $("act-training-days").textContent = "–";
    $("act-training-pct").textContent = "";
    $("act-workout-hr").textContent = "–";
    $("act-walk-min").textContent = "–";
    $("act-walk-steps").textContent = "";
    $("act-rhr").textContent = "–";
  }

  renderActivityBars(act.daily || []);
  renderWorkoutTypes(act.by_type || [], has);
  renderInsights(
    "activity-insights",
    has ? act.insights : ["Import Whoop workouts and cycles for training and walking."],
  );
}

function niceMax(value, fallback) {
  const v = Math.max(value || 0, fallback);
  if (v <= 0) return fallback;
  const exp = 10 ** Math.floor(Math.log10(v));
  const f = v / exp;
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
  return nice * exp;
}

function formatAxisSteps(n) {
  if (n >= 1000) return `${Math.round(n / 1000)}k`;
  return String(Math.round(n));
}

function renderActivityBars(series) {
  const root = $("activity-bars");
  if (!series.length) {
    root.replaceChildren();
    return;
  }

  const n = series.length;
  const width = Math.max(root.clientWidth || 320, n * 22);
  const height = 168;
  const pad = { top: 18, right: 36, bottom: 28, left: 34 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const slot = innerW / n;
  const barW = Math.max(6, Math.min(14, slot * 0.42));

  const strains = series.map((d) => d.training_strain).filter((v) => v != null);
  const steps = series.map((d) => d.est_steps).filter((v) => v != null);
  const maxStrain = niceMax(Math.max(0, ...strains), 5);
  const maxSteps = niceMax(Math.max(0, ...steps), 2000);

  const xAt = (i) => pad.left + (i + 0.5) * slot;
  const yStrain = (v) => pad.top + innerH - (v / maxStrain) * innerH;
  const ySteps = (v) => pad.top + innerH - (v / maxSteps) * innerH;

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "activity-svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", String(height));
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Training intensity bars with walking steps line");

  const ticks = [0, 0.5, 1];
  for (const t of ticks) {
    const y = pad.top + innerH * (1 - t);
    const grid = document.createElementNS("http://www.w3.org/2000/svg", "line");
    grid.setAttribute("class", "activity-grid");
    grid.setAttribute("x1", String(pad.left));
    grid.setAttribute("x2", String(width - pad.right));
    grid.setAttribute("y1", String(y));
    grid.setAttribute("y2", String(y));
    svg.append(grid);

    const left = document.createElementNS("http://www.w3.org/2000/svg", "text");
    left.setAttribute("class", "activity-axis-left");
    left.setAttribute("x", String(pad.left - 6));
    left.setAttribute("y", String(y + 3));
    left.setAttribute("text-anchor", "end");
    left.textContent = t === 0 ? "0" : String(Math.round(maxStrain * t * 10) / 10);
    svg.append(left);

    const right = document.createElementNS("http://www.w3.org/2000/svg", "text");
    right.setAttribute("class", "activity-axis-right");
    right.setAttribute("x", String(width - pad.right + 6));
    right.setAttribute("y", String(y + 3));
    right.setAttribute("text-anchor", "start");
    right.textContent = formatAxisSteps(maxSteps * t);
    svg.append(right);
  }

  const leftTitle = document.createElementNS("http://www.w3.org/2000/svg", "text");
  leftTitle.setAttribute("class", "activity-axis-left activity-axis-title");
  leftTitle.setAttribute("x", String(pad.left - 6));
  leftTitle.setAttribute("y", String(pad.top - 6));
  leftTitle.setAttribute("text-anchor", "end");
  leftTitle.textContent = "strain";
  svg.append(leftTitle);

  const rightTitle = document.createElementNS("http://www.w3.org/2000/svg", "text");
  rightTitle.setAttribute("class", "activity-axis-right activity-axis-title");
  rightTitle.setAttribute("x", String(width - pad.right + 6));
  rightTitle.setAttribute("y", String(pad.top - 6));
  rightTitle.setAttribute("text-anchor", "start");
  rightTitle.textContent = "steps";
  svg.append(rightTitle);

  // Training bars first (under the line)
  series.forEach((d, i) => {
    const cx = xAt(i);
    if (d.training_strain != null) {
      const y = yStrain(d.training_strain);
      const h = Math.max(3, pad.top + innerH - y);
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("class", "activity-train-bar");
      rect.setAttribute("x", String(cx - barW / 2));
      rect.setAttribute("y", String(y));
      rect.setAttribute("width", String(barW));
      rect.setAttribute("height", String(h));
      rect.setAttribute("rx", "3");
      const tip = [`${formatShortDate(d.date)} · strain ${d.training_strain}`];
      if (d.est_steps != null) tip.push(`~${Math.round(d.est_steps).toLocaleString()} est. steps`);
      const tipNode = document.createElementNS("http://www.w3.org/2000/svg", "title");
      tipNode.textContent = tip.join(" · ");
      rect.append(tipNode);
      svg.append(rect);
    }
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("class", "activity-day-label");
    label.setAttribute("x", String(cx));
    label.setAttribute("y", String(height - 8));
    label.setAttribute("text-anchor", "middle");
    label.textContent = dayLabel(d.date);
    svg.append(label);
  });

  // Walking line on top — break across days with no walk
  const walkPts = series.map((d, i) =>
    d.est_steps == null ? null : { x: xAt(i), y: ySteps(d.est_steps), d, i },
  );
  let segment = [];
  const flush = () => {
    if (segment.length >= 2) {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("class", "activity-walk-line");
      path.setAttribute(
        "d",
        segment.map((p, idx) => `${idx === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" "),
      );
      svg.append(path);
    }
    segment = [];
  };
  for (const p of walkPts) {
    if (!p) flush();
    else segment.push(p);
  }
  flush();

  for (const p of walkPts) {
    if (!p) continue;
    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("class", "activity-walk-dot");
    dot.setAttribute("cx", p.x.toFixed(1));
    dot.setAttribute("cy", p.y.toFixed(1));
    dot.setAttribute("r", "3.5");
    const mins = p.d.walk_min != null ? `${Math.round(p.d.walk_min)} min` : "";
    const tipNode = document.createElementNS("http://www.w3.org/2000/svg", "title");
    tipNode.textContent = `${formatShortDate(p.d.date)} · ~${Math.round(p.d.est_steps).toLocaleString()} est. steps${mins ? ` (${mins})` : ""}`;
    dot.append(tipNode);
    svg.append(dot);
  }

  root.replaceChildren(svg);
}

function renderWorkoutTypes(types, has) {
  const root = $("workout-types");
  if (!has || !types.length) {
    root.replaceChildren();
    return;
  }
  const max = Math.max(...types.map((t) => t.count));
  root.replaceChildren(
    ...types.map((t) => {
      const row = document.createElement("div");
      row.className = "workout-type-row";
      row.innerHTML =
        `<span class="workout-type-name"></span>` +
        `<div class="workout-type-track"><div class="workout-type-fill"></div></div>` +
        `<span class="workout-type-count"></span>`;
      row.querySelector(".workout-type-name").textContent = t.activity;
      row.querySelector(".workout-type-fill").style.width = `${(t.count / max) * 100}%`;
      row.querySelector(".workout-type-count").textContent = String(t.count);
      return row;
    }),
  );
}

function renderInsights(id, items) {
  const root = $(id);
  const list = (items || []).filter(Boolean);
  root.replaceChildren(
    ...list.map((text) => {
      const li = document.createElement("li");
      li.textContent = text;
      return li;
    }),
  );
}

function dayLabel(isoDate) {
  const d = parseLocal(isoDate);
  return `${d.getDate()}/${d.getMonth() + 1}`;
}
