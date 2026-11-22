import { apiGet, apiPost } from "./api.js";
import { formatDayTitle, formatShortDate, formatTime } from "./format.js";

const $ = (id) => document.getElementById(id);
let loaded = false;
let refreshing = false;
let dayRefreshing = false;
let days = 7;
let currentDay = null;

const SECTION_LABELS = {
  safety: "Safety",
  glucose: "Glucose",
  food: "Food",
  sleep: "Sleep",
  activity: "Activity",
  insulin: "Insulin",
};

export async function loadCoach() {
  if (!currentDay) {
    const bootstrap = await apiGet(`/coach?days=${days}`);
    // Prefer latest glucose day from day endpoint via a recent date in coverage
    const end = bootstrap.coverage?.window_end || bootstrap.period_end;
    currentDay = end || new Date().toISOString().slice(0, 10);
  }
  const data = await apiGet(`/coach/day?date=${currentDay}`);
  currentDay = data.day;
  renderDay(data);
  // Also load period findings quietly
  const period = await apiGet(`/coach?days=${days}`);
  renderPeriod(period);
  renderPreview(data.findings?.length ? data : period);
  loaded = true;
  return data;
}

export function ensureCoach() {
  if (!loaded) return loadCoach();
  return Promise.resolve();
}

export function initCoach() {
  document.querySelectorAll("#coach-periods .period-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = Number(btn.dataset.days);
      if (next === days) return;
      days = next;
      syncPeriodPills();
      apiGet(`/coach?days=${days}`)
        .then(renderPeriod)
        .catch((error) => console.error(error));
    });
  });

  $("coach-refresh")?.addEventListener("click", () => {
    refreshPeriod().catch((error) => {
      console.error(error);
      showNotice(error.message || "Could not refresh period coach.");
    });
  });

  $("coach-day-refresh")?.addEventListener("click", () => {
    refreshDay().catch((error) => {
      console.error(error);
      showNotice(error.message || "Could not analyse this day.");
      const btn = $("coach-day-refresh");
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Analyse day";
      }
      dayRefreshing = false;
    });
  });

  $("coach-day-input")?.addEventListener("change", (event) => {
    const value = event.target.value;
    if (!value) return;
    currentDay = value;
    apiGet(`/coach/day?date=${currentDay}`)
      .then((data) => {
        renderDay(data);
        renderPreview(data);
      })
      .catch((error) => console.error(error));
  });

  $("coach-day-prev")?.addEventListener("click", () => navigateDay(-1));
  $("coach-day-next")?.addEventListener("click", () => navigateDay(1));
}

function navigateDay(step) {
  const btn = step < 0 ? $("coach-day-prev") : $("coach-day-next");
  const target = btn?.dataset.date;
  if (!target) return;
  currentDay = target;
  apiGet(`/coach/day?date=${currentDay}`)
    .then((data) => {
      renderDay(data);
      renderPreview(data);
    })
    .catch((error) => console.error(error));
}

async function refreshDay() {
  if (dayRefreshing || !currentDay) return;
  dayRefreshing = true;
  const btn = $("coach-day-refresh");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Thinking…";
  }
  try {
    const data = await apiPost("/coach/day/refresh", { date: currentDay });
    renderDay(data);
    renderPreview(data);
    hideNotice();
  } finally {
    dayRefreshing = false;
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Analyse day";
    }
  }
}

async function refreshPeriod() {
  if (refreshing) return;
  refreshing = true;
  const btn = $("coach-refresh");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Thinking…";
  }
  try {
    const data = await apiPost("/coach/refresh", { days });
    renderPeriod(data);
  } finally {
    refreshing = false;
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Refresh period";
    }
  }
}

function syncPeriodPills() {
  document.querySelectorAll("#coach-periods .period-pill").forEach((btn) => {
    btn.classList.toggle("active", Number(btn.dataset.days) === days);
  });
}

function renderDay(data) {
  currentDay = data.day;
  const input = $("coach-day-input");
  if (input) input.value = data.day;
  const subtitle = $("coach-day-subtitle");
  if (subtitle) {
    const when = data.generated_at ? ` · Analysed ${formatShortDate(data.generated_at.slice(0, 10))}` : "";
    subtitle.textContent = `${formatDayTitle(data.day)}${when}`;
  }

  $("coach-day-prev").disabled = !data.prev_date;
  $("coach-day-next").disabled = !data.next_date;
  $("coach-day-prev").dataset.date = data.prev_date || "";
  $("coach-day-next").dataset.date = data.next_date || "";

  const meals = data.meals || {};
  const source = $("coach-meal-source");
  const note = $("coach-meal-note");
  if (source) {
    source.textContent =
      meals.source === "logged"
        ? "Logged meals"
        : meals.source === "estimated"
          ? `Schedule + insulin (${meals.schedule_kind || "day"})`
          : `Typical ${meals.schedule_kind || "day"} schedule`;
  }
  if (note) note.textContent = meals.note || "";

  const mealList = $("coach-meal-list");
  if (mealList) {
    const windows = data.meal_windows || [];
    const byTime = Object.fromEntries(windows.map((w) => [w.meal_t, w]));
    const items = meals.meals || [];
    if (!items.length) {
      mealList.replaceChildren(
        Object.assign(document.createElement("li"), {
          className: "muted",
          textContent: "No meals for this day. Set typical times in Settings.",
        }),
      );
    } else {
      mealList.replaceChildren(
        ...items.map((m) => {
          const li = document.createElement("li");
          const win = byTime[m.t];
          const carbs = m.carbs != null ? `${Math.round(m.carbs)} g carbs` : "carbs unknown";
          const insulin =
            m.insulin_units != null ? `${m.insulin_units} u rapid` : null;
          const tag =
            m.source === "estimated"
              ? `estimated${insulin ? ` · ${insulin}` : ""}`
              : m.source === "logged"
                ? "logged"
                : "schedule";
          const assessLabel = {
            well_managed: "well managed",
            started_low: "started low",
            started_high: "started already high",
            post_meal_high: "post-meal high",
            mild_overshoot: "mild overshoot",
            moderate_rise: "moderate rise",
          };
          const assessKey = win?.assessment || "";
          const assess = assessKey ? assessLabel[assessKey] || assessKey : null;
          const twoH = win?.at_2h_mg_dl != null ? String(win.at_2h_mg_dl) : "–";
          li.innerHTML = `<div><strong></strong><span class="muted"></span></div><span class="life-metric meal-metric"></span>`;
          li.querySelector("strong").textContent = `${m.label} · ${formatTime(m.t)}`;
          li.querySelector(".muted").textContent = ` · ${carbs} · ${tag}`;
          const metric = li.querySelector(".meal-metric");
          if (!win) {
            metric.textContent = "no glucose window";
          } else {
            metric.append(
              document.createTextNode(`pre ${win.pre_mg_dl} → peak ${win.peak_mg_dl} → 2h ${twoH}`),
            );
            if (assess) {
              const chip = document.createElement("span");
              chip.className = "meal-assess";
              chip.dataset.assess = assessKey;
              chip.textContent = assess;
              metric.append(document.createTextNode(" "), chip);
            }
          }
          return li;
        }),
      );
    }
  }

  if (!data.api_key_configured) {
    showNotice("Add OPENAI_API_KEY to your .env file, then analyse a day.");
  } else if (!(data.findings || []).length) {
    showNotice("No day findings yet. Tap Analyse day for feedback on this date.");
  } else if (data.coverage && data.coverage.meals_source === "estimated") {
    showNotice(
      "No food log — meal times estimated from your schedule plus this day's rapid insulin. Timing can shift day to day; carb advice stays lower confidence.",
    );
  } else if (data.coverage && !data.coverage.has_logged_meals) {
    showNotice(
      "No food log this day — coach used your weekday/weekend meal schedule from Settings. Confidence is lower for carb-specific advice.",
    );
  } else {
    hideNotice();
  }

  const list = $("coach-day-list");
  if (!list) return;
  const findings = data.findings || [];
  if (!findings.length) {
    list.innerHTML = `
      <article class="card empty-card">
        <svg class="icon empty-icon"><use href="#i-coach"/></svg>
        <h2>No feedback for this day</h2>
        <p class="empty-text">Analyse the day to get dated meal and glucose recommendations you can act on next time.</p>
      </article>`;
    return;
  }
  list.replaceChildren(...findings.map(renderCard));
}

function renderPeriod(data) {
  syncPeriodPills();
  const period = $("coach-period");
  if (period) {
    const start = data.period_start ? formatShortDate(data.period_start) : "–";
    const end = data.period_end ? formatShortDate(data.period_end) : "–";
    const when = data.generated_at ? ` · Updated ${formatShortDate(data.generated_at.slice(0, 10))}` : "";
    period.textContent = `${data.findings_days || data.days || days}d: ${start} – ${end}${when}`;
  }
  const list = $("coach-list");
  if (!list) return;
  const findings = data.findings || [];
  if (!findings.length) {
    list.innerHTML = `<p class="muted">No multi-day findings yet. Optional — use Refresh period after day reviews.</p>`;
    return;
  }
  list.replaceChildren(...findings.map(renderCard));
}

function renderCard(finding) {
  const article = document.createElement("article");
  article.className = "card finding-card";
  article.dataset.section = finding.section || "";

  const head = document.createElement("header");
  head.className = "finding-head";
  const chip = document.createElement("span");
  chip.className = "finding-chip";
  chip.dataset.section = finding.section || "";
  chip.textContent = SECTION_LABELS[finding.section] || finding.section || "Finding";
  const conf = document.createElement("span");
  conf.className = "finding-confidence";
  conf.dataset.confidence = finding.confidence || "";
  conf.textContent = finding.confidence ? `${finding.confidence} confidence` : "";
  head.append(chip, conf);

  const title = document.createElement("h2");
  title.className = "finding-title";
  title.textContent = finding.title;

  const insight = document.createElement("p");
  insight.className = "finding-insight";
  insight.textContent = finding.insight;

  article.append(head, title, insight);

  const evidenceDays = finding.evidence?.days || [];
  if (evidenceDays.length) {
    const evidence = document.createElement("p");
    evidence.className = "finding-evidence";
    evidence.textContent = `Examples: ${evidenceDays.map((d) => formatShortDate(d)).join(", ")}`;
    article.append(evidence);
  }

  if (finding.why_it_matters) {
    const why = document.createElement("p");
    why.className = "finding-why";
    const label = document.createElement("strong");
    label.textContent = "Why it matters";
    const whyBody = document.createElement("span");
    whyBody.textContent = ` ${finding.why_it_matters}`;
    why.append(label, whyBody);
    article.append(why);
  }

  if (finding.try_text) {
    const tryBox = document.createElement("div");
    tryBox.className = "finding-try";
    const label = document.createElement("span");
    label.className = "finding-try-label";
    label.textContent = "Try next";
    const body = document.createElement("p");
    body.textContent = finding.try_text;
    tryBox.append(label, body);
    article.append(tryBox);
  }

  return article;
}

function renderPreview(data) {
  const root = $("coach-preview-body");
  if (!root) return;
  const findings = data.findings || [];
  if (!findings.length) {
    root.innerHTML =
      '<p class="empty-text">Day feedback will appear here after you analyse a day in Coach.</p>';
    return;
  }
  root.replaceChildren(
    ...findings.slice(0, 2).map((f) => {
      const row = document.createElement("a");
      row.href = "#coach";
      row.className = "coach-preview-item";
      row.innerHTML = `<span class="finding-chip"></span><span class="coach-preview-title"></span>`;
      row.querySelector(".finding-chip").textContent = SECTION_LABELS[f.section] || f.section;
      row.querySelector(".finding-chip").dataset.section = f.section || "";
      row.querySelector(".coach-preview-title").textContent = f.title;
      return row;
    }),
  );
}

function showNotice(text) {
  const notice = $("coach-notice");
  const body = $("coach-notice-text");
  if (!notice || !body) return;
  body.textContent = text;
  notice.hidden = false;
}

function hideNotice() {
  const notice = $("coach-notice");
  if (notice) notice.hidden = true;
}
