import { apiGet } from "./api.js";
import { bandFor, formatShortDate } from "./format.js";

const $ = (id) => document.getElementById(id);
const DONUT_R = 46;
const DONUT_C = 2 * Math.PI * DONUT_R;

const SPECTRUM_COPY = {
  perfect: "Perfect · under 25%",
  good: "Good · 25–30%",
  medium: "Medium · 30–36%",
  bad: "Bad · 36–45% (at/above consensus line)",
  very_bad: "Very bad · 45%+",
};

let days = 14;
let loaded = false;

export async function loadTrends(periodDays = days) {
  days = periodDays;
  document.querySelectorAll("#trends-periods .period-pill").forEach((btn) => {
    btn.classList.toggle("active", Number(btn.dataset.days) === days);
  });
  const data = await apiGet(`/trends?days=${days}`);
  render(data);
  loaded = true;
}

export function initTrends() {
  document.querySelectorAll("#trends-periods .period-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      loadTrends(Number(btn.dataset.days)).catch((error) => console.error(error));
    });
  });
}

export function ensureTrends() {
  if (!loaded) return loadTrends();
  return Promise.resolve();
}

function render(data) {
  const notice = $("trends-notice");
  if (!data.latest_data_date || data.readings_n === 0) {
    notice.hidden = false;
    $("trends-notice-text").textContent = "No glucose data yet. Import a LibreLink export to see trends.";
  } else {
    notice.hidden = true;
  }

  renderTir(data);
  renderTimeOfDay(data.hour_bands || []);
  renderVariability(data);
}

function renderTir(data) {
  const has = data.readings_n > 0;
  const threshold = data.cv_unstable_pct ?? 36;
  $("trends-tir-title").textContent = `${data.target_low}–${data.target_high} mg/dL`;
  $("trends-bands-subtitle").textContent =
    `${data.days} days · ${formatShortDate(data.start)} – ${formatShortDate(data.end)} · ${(data.readings_n || 0).toLocaleString()} readings`;

  const inRange = data.bands?.find((b) => b.key === "in_range");
  $("trends-tir").textContent = has && inRange ? `${Math.round(inRange.pct)}%` : "–";

  drawDonut(data.bands || [], has);
  renderBandLegend(data.bands || [], has);

  if (has && data.average != null) {
    $("trends-average").innerHTML = `${data.average}<small>mg/dL</small>`;
    const band = bandFor(data.average, data.target_low, data.target_high);
    const badge = $("trends-avg-badge");
    badge.textContent = band.label;
    badge.dataset.band = band.key;
  } else {
    $("trends-average").textContent = "–";
    $("trends-avg-badge").textContent = "No data";
    $("trends-avg-badge").removeAttribute("data-band");
  }

  $("trends-gmi").innerHTML = data.gmi != null ? `${data.gmi}<small>%</small>` : "–";

  const avgDelta = $("trends-avg-delta");
  if (data.avg_delta == null) {
    avgDelta.textContent = "";
  } else {
    const sign = data.avg_delta > 0 ? "+" : "";
    avgDelta.textContent = `${sign}${data.avg_delta} vs previous`;
    avgDelta.dataset.delta = data.avg_delta < 0 ? "better" : data.avg_delta > 0 ? "worse" : "same";
  }

  const tirDelta = $("trends-tir-delta");
  if (data.tir_delta == null) {
    tirDelta.textContent = "–";
    tirDelta.dataset.delta = "";
  } else {
    const sign = data.tir_delta > 0 ? "+" : "";
    tirDelta.innerHTML = `${sign}${data.tir_delta}<small> pts</small>`;
    tirDelta.dataset.delta = data.tir_delta > 0 ? "better" : data.tir_delta < 0 ? "worse" : "same";
  }

  // silence unused warning for threshold in this function scope if needed later
  void threshold;
}

function drawDonut(bands, hasData) {
  const svg = $("tir-donut");
  if (!hasData) {
    svg.innerHTML = `<circle cx="60" cy="60" r="${DONUT_R}" class="donut-track" />`;
    return;
  }
  // Draw high→low so the visual matches the legend order people expect from the rim.
  const ordered = [...bands].reverse().filter((b) => b.pct > 0);
  let offset = 0;
  const arcs = ordered.map((b) => {
    const length = (b.pct / 100) * DONUT_C;
    const arc = `<circle class="donut-seg band-${b.key}" cx="60" cy="60" r="${DONUT_R}"
      stroke-dasharray="${length} ${DONUT_C - length}" stroke-dashoffset="${-offset}" />`;
    offset += length;
    return arc;
  });
  svg.innerHTML = `<circle cx="60" cy="60" r="${DONUT_R}" class="donut-track" />${arcs.join("")}`;
}

function renderBandLegend(bands, hasData) {
  const legend = $("trends-band-legend");
  legend.replaceChildren(
    ...[...bands].reverse().map((b) => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="band-dot band-${b.key}"></span><span></span><strong></strong>`;
      li.children[1].textContent = b.label;
      li.children[2].textContent = hasData ? `${Math.round(b.pct)}%` : "–";
      return li;
    }),
  );
}

function renderTimeOfDay(hours) {
  const svg = $("tod-chart");
  const tip = $("tod-tooltip");
  const callouts = $("tod-callouts");
  const width = 640;
  const height = 220;
  const pad = { top: 18, right: 16, bottom: 28, left: 36 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const x = (hour) => pad.left + (hour / 23) * plotW;
  const y = (pct) => pad.top + (1 - pct / 100) * plotH;

  // Stacked from bottom: low → in range → high (sums to 100).
  const lowTop = hours.map((h) => h.low_pct);
  const midTop = hours.map((h, i) => h.low_pct + h.in_range_pct);
  const highTop = hours.map(() => 100);

  const area = (bottom, top) => stackedAreaPath(hours.map((_, i) => [x(i), y(bottom[i]), y(top[i])]));
  const line = (values) => smoothLine(values.map((v, i) => [x(i), y(v)]));

  const peakHigh = hours.reduce((best, h) => (h.high_pct > best.high_pct ? h : best), hours[0] || { hour: 0, high_pct: 0 });
  const peakLow = hours.reduce((best, h) => (h.low_pct > best.low_pct ? h : best), hours[0] || { hour: 0, low_pct: 0 });
  const bestRange = hours.reduce((best, h) => (h.in_range_pct > best.in_range_pct ? h : best), hours[0] || { hour: 0, in_range_pct: 0 });

  const parts = [
    `<defs>
      <linearGradient id="tod-high-fill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#c88a1e" stop-opacity="0.55"/>
        <stop offset="100%" stop-color="#c88a1e" stop-opacity="0.16"/>
      </linearGradient>
      <linearGradient id="tod-mid-fill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#2f8a6b" stop-opacity="0.5"/>
        <stop offset="100%" stop-color="#2f8a6b" stop-opacity="0.14"/>
      </linearGradient>
      <linearGradient id="tod-low-fill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#d65f4c" stop-opacity="0.55"/>
        <stop offset="100%" stop-color="#d65f4c" stop-opacity="0.16"/>
      </linearGradient>
    </defs>`,
    `<rect class="tod-plot" x="${pad.left}" y="${pad.top}" width="${plotW}" height="${plotH}" />`,
  ];

  [0, 25, 50, 75, 100].forEach((pct) => {
    const yy = y(pct);
    parts.push(`<line class="tod-grid" x1="${pad.left}" y1="${yy}" x2="${width - pad.right}" y2="${yy}" />`);
    parts.push(`<text class="tod-axis" x="${pad.left - 8}" y="${yy + 3}" text-anchor="end">${pct}</text>`);
  });

  parts.push(`<path class="tod-area tod-area-high" d="${area(midTop, highTop)}" fill="url(#tod-high-fill)" />`);
  parts.push(`<path class="tod-area tod-area-mid" d="${area(lowTop, midTop)}" fill="url(#tod-mid-fill)" />`);
  parts.push(`<path class="tod-area tod-area-low" d="${area(hours.map(() => 0), lowTop)}" fill="url(#tod-low-fill)" />`);
  parts.push(`<path class="tod-range-line" d="${line(hours.map((h) => h.in_range_pct))}" />`);

  ;[0, 6, 12, 18, 23].forEach((hour) => {
    parts.push(`<text class="tod-axis" x="${x(hour)}" y="${height - 8}" text-anchor="middle">${String(hour).padStart(2, "0")}</text>`);
  });

  parts.push(`<line class="tod-cursor" id="tod-cursor" x1="0" y1="${pad.top}" x2="0" y2="${height - pad.bottom}" hidden />`);
  hours.forEach((h, i) => {
    parts.push(`<rect class="tod-hit" data-hour="${h.hour}" x="${x(i) - plotW / 48}" y="${pad.top}" width="${plotW / 24}" height="${plotH}" />`);
  });

  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = parts.join("");

  if (hours.some((h) => h.n > 0)) {
    callouts.textContent =
      `Highest highs around ${fmtHour(peakHigh.hour)} (${Math.round(peakHigh.high_pct)}% high) · ` +
      `Most lows around ${fmtHour(peakLow.hour)} (${Math.round(peakLow.low_pct)}% low) · ` +
      `Best in-range stretch around ${fmtHour(bestRange.hour)} (${Math.round(bestRange.in_range_pct)}%)`;
  } else {
    callouts.textContent = "";
  }

  const cursor = svg.querySelector("#tod-cursor");
  const hits = svg.querySelectorAll(".tod-hit");
  hits.forEach((hit) => {
    hit.addEventListener("pointerenter", () => {
      const hour = Number(hit.dataset.hour);
      const h = hours[hour];
      if (!h) return;
      cursor.removeAttribute("hidden");
      cursor.setAttribute("x1", String(x(hour)));
      cursor.setAttribute("x2", String(x(hour)));
      tip.hidden = false;
      tip.innerHTML =
        `<strong>${fmtHour(hour)}</strong>` +
        `<span class="tod-tip-low">Low ${Math.round(h.low_pct)}%</span>` +
        `<span class="tod-tip-mid">In range ${Math.round(h.in_range_pct)}%</span>` +
        `<span class="tod-tip-high">High ${Math.round(h.high_pct)}%</span>`;
      tip.style.left = `${Math.min(Math.max((hour / 23) * 100, 12), 88)}%`;
    });
  });
  svg.addEventListener("pointerleave", () => {
    tip.hidden = true;
    cursor.setAttribute("hidden", "");
  });
}

function fmtHour(hour) {
  return `${String(hour).padStart(2, "0")}:00`;
}

/** Points: [x, yBottom, yTop] → closed smooth stacked band. */
function stackedAreaPath(points) {
  const top = points.map(([px, , yTop]) => [px, yTop]);
  const bottom = points.map(([px, yBottom]) => [px, yBottom]).reverse();
  return `${smoothLine(top)} ${smoothLine(bottom, true)} Z`;
}

function smoothLine(points, reverseContinue = false) {
  if (points.length === 0) return "";
  if (points.length === 1) {
    const [px, py] = points[0];
    return `${reverseContinue ? "L" : "M"} ${px.toFixed(1)} ${py.toFixed(1)}`;
  }
  let d = `${reverseContinue ? "L" : "M"} ${points[0][0].toFixed(1)} ${points[0][1].toFixed(1)}`;
  for (let i = 0; i < points.length - 1; i += 1) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];
    const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`;
  }
  return d;
}

function renderVariability(data) {
  const threshold = data.cv_unstable_pct ?? 36;
  const period = data.variability?.period;
  const scale = data.variability?.spectrum_scale || [
    { key: "perfect", label: "Perfect", upper: 25 },
    { key: "good", label: "Good", upper: 30 },
    { key: "medium", label: "Medium", upper: 36 },
    { key: "bad", label: "Bad", upper: 45 },
    { key: "very_bad", label: "Very bad", upper: null },
  ];

  $("var-explain").textContent =
    `CV is how swingy glucose is around your average. Perfect (<25%), Good, and Medium sit under the ${threshold}% consensus line; Bad and Very bad are at or above it. Libre often doesn’t show this.`;

  renderCvScale(scale, period?.spectrum);

  const badge = $("var-badge");
  if (period) {
    $("var-cv").textContent = period.cv_pct.toFixed(1);
    badge.textContent = period.label;
    badge.dataset.spectrum = period.spectrum;
    $("var-cutoff").textContent = SPECTRUM_COPY[period.spectrum] || period.label;
    $("var-sd").innerHTML = `±${Math.round(period.sd)}<small>mg/dL</small>`;
  } else {
    $("var-cv").textContent = "–";
    badge.textContent = "Not enough data";
    badge.dataset.spectrum = "";
    $("var-cutoff").textContent = `Need about 8 hours of sensor data per day to score CV.`;
    $("var-sd").textContent = "–";
  }

  const within = data.variability?.within_day_cv_pct;
  $("var-within").innerHTML = within != null ? `${within}<small>%</small>` : "–";
  const daySd = data.variability?.day_to_day_sd;
  $("var-day-sd").innerHTML = daySd != null ? `±${daySd}<small>mg/dL</small>` : "–";

  const delta = data.cv_delta;
  const deltaEl = $("var-delta");
  if (delta == null) {
    deltaEl.textContent = "–";
    deltaEl.dataset.delta = "";
  } else {
    const sign = delta > 0 ? "+" : "";
    deltaEl.innerHTML = `${sign}${delta}<small> pts</small>`;
    deltaEl.dataset.delta = delta < 0 ? "better" : delta > 0 ? "worse" : "same";
  }

  const unstableDays = data.variability?.unstable_days ?? 0;
  const daysWithCv = data.variability?.days_with_cv ?? 0;
  $("var-period").textContent = daysWithCv
    ? `${formatShortDate(data.start)} – ${formatShortDate(data.end)} · ${unstableDays} of ${daysWithCv} days at/above ${threshold}%`
    : `${formatShortDate(data.start)} – ${formatShortDate(data.end)}`;

  $("var-chart-start").textContent = formatShortDate(data.start);
  $("var-chart-end").textContent = formatShortDate(data.end);
  drawCvChart(data.variability?.daily || [], threshold);
}

function renderCvScale(scale, activeKey) {
  const root = $("cv-scale");
  root.replaceChildren(
    ...scale.map((item) => {
      const li = document.createElement("li");
      li.dataset.spectrum = item.key;
      if (item.key === activeKey) li.classList.add("active");
      const upper = item.upper == null ? "45%+" : `<${item.upper}%`;
      li.innerHTML = `<span class="cv-scale-dot"></span><strong></strong><span></span>`;
      li.querySelector("strong").textContent = item.label;
      li.querySelector("span:last-child").textContent = upper;
      return li;
    }),
  );
}

function drawCvChart(daily, threshold) {
  const svg = $("var-chart");
  const width = 640;
  const height = 160;
  const pad = { top: 16, right: 12, bottom: 22, left: 36 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const cvs = daily.map((d) => d.cv_pct).filter((v) => v != null);
  // Zoom to the data — no dead space from 0% unless values are truly that low.
  const dataMin = cvs.length ? Math.min(...cvs) : threshold - 8;
  const dataMax = cvs.length ? Math.max(...cvs) : threshold + 8;
  const padAmt = Math.max(3, (dataMax - dataMin) * 0.18);
  let minCv = Math.floor(dataMin - padAmt);
  let maxCv = Math.ceil(dataMax + padAmt);
  if (threshold >= minCv - 2 && threshold <= maxCv + 2) {
    minCv = Math.min(minCv, Math.floor(threshold - 2));
    maxCv = Math.max(maxCv, Math.ceil(threshold + 2));
  }
  if (maxCv - minCv < 10) {
    const mid = (minCv + maxCv) / 2;
    minCv = Math.floor(mid - 5);
    maxCv = Math.ceil(mid + 5);
  }
  minCv = Math.max(0, minCv);

  const y = (v) => pad.top + (1 - (v - minCv) / (maxCv - minCv)) * plotH;
  const x = (i) => pad.left + (daily.length <= 1 ? plotW / 2 : (i / (daily.length - 1)) * plotW);

  const zones = [
    { key: "perfect", from: 0, to: 25 },
    { key: "good", from: 25, to: 30 },
    { key: "medium", from: 30, to: 36 },
    { key: "bad", from: 36, to: 45 },
    { key: "very_bad", from: 45, to: 100 },
  ];

  const parts = [];
  zones.forEach((zone) => {
    const from = Math.max(zone.from, minCv);
    const to = Math.min(zone.to, maxCv);
    if (to <= from) return;
    const top = y(to);
    const bottom = y(from);
    parts.push(
      `<rect class="cv-zone cv-zone-${zone.key}" x="${pad.left}" y="${top}" width="${plotW}" height="${Math.max(0, bottom - top)}" />`,
    );
  });

  // Evenly spaced ticks only — never force min/max/threshold on top of a neighbour.
  const ticks = spacedTicks(minCv, maxCv, 4);
  const minLabelGap = plotH / 5.5;
  ticks.forEach((tick) => {
    const yy = y(tick);
    parts.push(`<line class="cv-grid" x1="${pad.left}" y1="${yy}" x2="${width - pad.right}" y2="${yy}" />`);
    parts.push(`<text class="cv-axis" x="${pad.left - 8}" y="${yy + 3}" text-anchor="end">${tick}</text>`);
  });

  if (threshold >= minCv && threshold <= maxCv) {
    const thresholdY = y(threshold);
    parts.push(`<line class="cv-threshold" x1="${pad.left}" y1="${thresholdY}" x2="${width - pad.right}" y2="${thresholdY}" />`);
    const tooClose = ticks.some((tick) => Math.abs(y(tick) - thresholdY) < minLabelGap);
    if (!tooClose) {
      parts.push(`<text class="cv-axis cv-axis-threshold" x="${pad.left - 8}" y="${thresholdY + 3}" text-anchor="end">${threshold}</text>`);
    }
  }

  const plotted = daily
    .map((d, i) => (d.cv_pct == null ? null : [x(i), y(d.cv_pct), d]))
    .filter(Boolean);
  if (plotted.length >= 2) {
    parts.push(`<path class="cv-line" d="${smoothLine(plotted.map(([px, py]) => [px, py]))}" />`);
  }
  plotted.forEach(([px, py, d]) => {
    parts.push(
      `<circle class="cv-dot spectrum-${d.spectrum || "medium"}" cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="4.5" />`,
    );
  });

  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = parts.join("");
}

function spacedTicks(min, max, count) {
  const span = Math.max(1, max - min);
  const rough = span / Math.max(1, count);
  const niceSteps = [1, 2, 2.5, 5, 10, 15, 20, 25];
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  let step = niceSteps[0] * magnitude;
  for (const candidate of niceSteps) {
    const value = candidate * magnitude;
    if (value >= rough) {
      step = value;
      break;
    }
    step = value;
  }
  step = Math.max(1, Math.round(step));
  const start = Math.ceil(min / step) * step;
  const ticks = [];
  for (let v = start; v <= max + 1e-9; v += step) ticks.push(Math.round(v));
  return ticks.length ? ticks : [Math.round((min + max) / 2)];
}
