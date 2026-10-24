const dayFormat = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long" });
const dayWithYearFormat = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const shortDateFormat = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });

// Dates from the API are local wall-clock strings without a time zone.
export function parseLocal(value) {
  const [datePart, timePart = "00:00:00"] = value.split("T");
  const [y, m, d] = datePart.split("-").map(Number);
  const [hh, mm, ss = 0] = timePart.split(":").map(Number);
  return new Date(y, m - 1, d, hh, mm, ss);
}

export function formatDayTitle(isoDate) {
  const day = parseLocal(isoDate);
  return day.getFullYear() === new Date().getFullYear() ? dayFormat.format(day) : dayWithYearFormat.format(day);
}

export function formatShortDate(isoDate) {
  return shortDateFormat.format(parseLocal(isoDate));
}

export function formatTime(isoDateTime) {
  const t = parseLocal(isoDateTime);
  return `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`;
}

export function minutesOfDay(isoDateTime) {
  const t = parseLocal(isoDateTime);
  return t.getHours() * 60 + t.getMinutes() + t.getSeconds() / 60;
}

export function bandFor(value, low, high) {
  if (value < 54) return { key: "very_low", label: "Very low" };
  if (value < low) return { key: "low", label: "Low" };
  if (value <= high) return { key: "in_range", label: "In range" };
  if (value <= 250) return { key: "high", label: "High" };
  return { key: "very_high", label: "Very high" };
}
