import { formatTime, minutesOfDay } from "./format.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const MAX_GAP_MINUTES = 40;
const PADDING = { top: 14, right: 12, bottom: 26, left: 34 };
const BASE_HEIGHT = 240;
const MARKER_WIDTH = 26;
const MARKER_ROW_HEIGHT = 20;

function el(name, attrs = {}) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/**
 * Draws one day of glucose: the goal band shaded, the line coloured by range,
 * scan readings as dots, and a hover/touch cursor with the exact value.
 */
export function renderDayChart(container, tooltip, { readings, insulin = [], targetLow, targetHigh }) {
  container.querySelectorAll("svg, .chart-empty").forEach((node) => node.remove());
  tooltip.hidden = true;

  if (!readings.length && !insulin.length) {
    container.style.height = "";
    const empty = document.createElement("div");
    empty.className = "chart-empty";
    empty.textContent = "No readings for this day";
    container.prepend(empty);
    return;
  }

  const width = container.clientWidth;
  const innerW = width - PADDING.left - PADDING.right;
  const xOf = (minutes) => PADDING.left + (minutes / 1440) * innerW;

  // Insulin markers sit in rows under the plot; a marker drops to the next row when it would overlap.
  const markerRows = [];
  const markers = insulin.map((dose) => {
    const minutes = minutesOfDay(dose.t);
    const px = xOf(minutes);
    let row = markerRows.findIndex((lastX) => px - lastX >= MARKER_WIDTH + 2);
    if (row === -1) {
      row = markerRows.length;
      markerRows.push(px);
    } else {
      markerRows[row] = px;
    }
    return { ...dose, minutes, px, row };
  });
  const markerSpace = markerRows.length ? markerRows.length * MARKER_ROW_HEIGHT + 8 : 0;
  container.style.height = `${BASE_HEIGHT + markerSpace}px`;

  const height = container.clientHeight;
  const bottom = PADDING.bottom + markerSpace;
  const innerH = height - PADDING.top - bottom;

  const maxValue = Math.max(260, ...readings.map((r) => r.v)) + 10;
  const minValue = Math.min(40, ...readings.map((r) => r.v));
  const x = xOf;
  const y = (value) => PADDING.top + (1 - (value - minValue) / (maxValue - minValue)) * innerH;

  const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "Glucose over the day" });

  // The line colour follows the value: a vertical gradient with hard stops at the thresholds.
  const gradientId = "glucose-gradient";
  const defs = el("defs");
  const gradient = el("linearGradient", { id: gradientId, gradientUnits: "userSpaceOnUse", x1: 0, x2: 0, y1: y(maxValue), y2: y(minValue) });
  const stops = [
    [maxValue, "--very-high"], [251, "--very-high"], [250, "--high"], [targetHigh + 1, "--high"],
    [targetHigh, "--in-range"], [targetLow, "--in-range"], [targetLow - 1, "--low"], [54, "--low"],
    [53, "--very-low"], [minValue, "--very-low"],
  ];
  for (const [value, colour] of stops) {
    const offset = Math.min(1, Math.max(0, (maxValue - value) / (maxValue - minValue)));
    gradient.append(el("stop", { offset, "stop-color": cssVar(colour) }));
  }
  defs.append(gradient);
  svg.append(defs);

  svg.append(el("rect", { class: "target-band", x: PADDING.left, width: innerW, y: y(targetHigh), height: y(targetLow) - y(targetHigh), rx: 4 }));
  svg.append(el("line", { class: "low-line", x1: PADDING.left, x2: PADDING.left + innerW, y1: y(70), y2: y(70) }));

  for (const value of [targetLow, targetHigh, 250]) {
    const label = el("text", { class: "axis-label", x: PADDING.left - 8, y: y(value) + 4, "text-anchor": "end" });
    label.textContent = value;
    svg.append(label);
  }
  for (const hour of [0, 6, 12, 18, 24]) {
    svg.append(el("line", { class: "grid-line", x1: x(hour * 60), x2: x(hour * 60), y1: PADDING.top + innerH, y2: PADDING.top + innerH + 4 }));
    const label = el("text", { class: "axis-label", x: x(hour * 60), y: height - 6, "text-anchor": hour === 0 ? "start" : hour === 24 ? "end" : "middle" });
    label.textContent = `${String(hour).padStart(2, "0")}:00`;
    svg.append(label);
  }

  const sensor = readings.filter((r) => r.kind === "sensor");
  const lineSource = sensor.length ? sensor : readings;
  let path = "";
  let previous = null;
  for (const reading of lineSource) {
    const minutes = minutesOfDay(reading.t);
    const move = previous === null || minutes - previous > MAX_GAP_MINUTES;
    path += `${move ? "M" : "L"}${x(minutes).toFixed(1)},${y(reading.v).toFixed(1)}`;
    previous = minutes;
  }
  svg.append(el("path", { class: "glucose-line", d: path, stroke: `url(#${gradientId})` }));

  if (sensor.length) {
    for (const reading of readings.filter((r) => r.kind !== "sensor")) {
      svg.append(el("circle", { class: "scan-dot", cx: x(minutesOfDay(reading.t)), cy: y(reading.v), r: 3.5, fill: `url(#${gradientId})` }));
    }
  }

  const plotBottom = PADDING.top + innerH;
  for (const marker of markers) {
    svg.append(el("line", { class: `dose-line dose-${marker.kind}`, x1: marker.px, x2: marker.px, y1: PADDING.top, y2: plotBottom }));
    const top = plotBottom + 8 + marker.row * MARKER_ROW_HEIGHT;
    const group = el("g", { class: `dose dose-${marker.kind}` });
    group.append(el("rect", { x: marker.px - MARKER_WIDTH / 2, y: top, width: MARKER_WIDTH, height: 16, rx: 8 }));
    const label = el("text", { x: marker.px, y: top + 11.5, "text-anchor": "middle" });
    label.textContent = marker.units === null ? "?" : String(marker.units).replace(/\.0$/, "");
    group.append(label);
    svg.append(group);
  }

  const cursorLine = el("line", { class: "cursor-line", y1: PADDING.top, y2: PADDING.top + innerH, visibility: "hidden" });
  const cursorDot = el("circle", { class: "cursor-dot", r: 5, visibility: "hidden", stroke: `url(#${gradientId})` });
  svg.append(cursorLine, cursorDot);
  container.prepend(svg);

  const points = readings.map((r) => ({ ...r, minutes: minutesOfDay(r.t) }));
  const hide = () => {
    cursorLine.setAttribute("visibility", "hidden");
    cursorDot.setAttribute("visibility", "hidden");
    tooltip.hidden = true;
  };
  svg.addEventListener("pointermove", (event) => {
    if (!points.length) return;
    const rect = svg.getBoundingClientRect();
    const minutes = ((event.clientX - rect.left - PADDING.left) / innerW) * 1440;
    const nearest = points.reduce((best, p) => (Math.abs(p.minutes - minutes) < Math.abs(best.minutes - minutes) ? p : best));
    if (Math.abs(nearest.minutes - minutes) > MAX_GAP_MINUTES) return hide();
    const px = x(nearest.minutes);
    const py = y(nearest.v);
    cursorLine.setAttribute("x1", px);
    cursorLine.setAttribute("x2", px);
    cursorDot.setAttribute("cx", px);
    cursorDot.setAttribute("cy", py);
    cursorLine.setAttribute("visibility", "visible");
    cursorDot.setAttribute("visibility", "visible");
    const nearbyDoses = markers
      .filter((m) => Math.abs(m.minutes - nearest.minutes) <= 10)
      .map((m) => `${m.units ?? "?"} u ${m.kind === "long" ? "long-acting" : "rapid"}`);
    tooltip.textContent = [`${formatTime(nearest.t)} · ${nearest.v} mg/dL${nearest.kind === "scan" ? " · scan" : ""}`, ...nearbyDoses].join(" · ");
    tooltip.style.left = `${Math.min(Math.max(px, 70), width - 70)}px`;
    tooltip.style.top = `${Math.max(py - 44, -8)}px`;
    tooltip.hidden = false;
  });
  svg.addEventListener("pointerleave", hide);
}
