"""Glucose statistics used by the screens and, later, by the coach."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

VERY_LOW = 54
LOW = 70
VERY_HIGH = 250
SENSOR_READINGS_PER_DAY = 96  # LibreLink history stores one reading every 15 minutes.


def bands(target_low: int, target_high: int) -> list[dict[str, Any]]:
    """The five time-in-range bands, built around the user's goal range."""
    return [
        {"key": "very_low", "label": f"Below {VERY_LOW}", "min": None, "max": VERY_LOW - 1},
        {"key": "low", "label": f"{VERY_LOW}–{target_low - 1}", "min": VERY_LOW, "max": target_low - 1},
        {"key": "in_range", "label": f"{target_low}–{target_high}", "min": target_low, "max": target_high},
        {"key": "high", "label": f"{target_high + 1}–{VERY_HIGH}", "min": target_high + 1, "max": VERY_HIGH},
        {"key": "very_high", "label": f"Above {VERY_HIGH}", "min": VERY_HIGH + 1, "max": None},
    ]


def band_shares(values: list[float], target_low: int, target_high: int) -> list[dict[str, Any]]:
    result = []
    total = len(values)
    for band in bands(target_low, target_high):
        lo = band["min"] if band["min"] is not None else float("-inf")
        hi = band["max"] if band["max"] is not None else float("inf")
        # Values are rounded to whole mg/dL so readings like 150.4 fall into a band.
        count = sum(1 for v in values if lo <= round(v) <= hi)
        result.append({**band, "pct": round(100 * count / total, 1) if total else 0.0})
    return result


def glucose_between(conn: sqlite3.Connection, start: datetime, end: datetime) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT ts, mg_dl, kind FROM glucose WHERE ts >= ? AND ts < ? ORDER BY ts",
        (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
    ).fetchall()


def stat_readings(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    """Readings used for statistics: sensor history when present, otherwise everything."""
    sensor = [r for r in rows if r["kind"] == "sensor"]
    return sensor or list(rows)


def latest_glucose_date(conn: sqlite3.Connection) -> date | None:
    row = conn.execute("SELECT MAX(ts) AS ts FROM glucose").fetchone()
    return datetime.fromisoformat(row["ts"]).date() if row and row["ts"] else None


def adjacent_glucose_dates(conn: sqlite3.Connection, day: date) -> tuple[date | None, date | None]:
    start = datetime.combine(day, datetime.min.time()).isoformat()
    end = datetime.combine(day + timedelta(days=1), datetime.min.time()).isoformat()
    prev_row = conn.execute("SELECT MAX(ts) AS ts FROM glucose WHERE ts < ?", (start,)).fetchone()
    next_row = conn.execute("SELECT MIN(ts) AS ts FROM glucose WHERE ts >= ?", (end,)).fetchone()
    prev_day = datetime.fromisoformat(prev_row["ts"]).date() if prev_row["ts"] else None
    next_day = datetime.fromisoformat(next_row["ts"]).date() if next_row["ts"] else None
    return prev_day, next_day


def trend(rows: list[sqlite3.Row]) -> dict[str, Any] | None:
    """Direction of travel from readings in the 30 minutes before the latest one."""
    if len(rows) < 2:
        return None
    last = rows[-1]
    last_ts = datetime.fromisoformat(last["ts"])
    window = [r for r in rows if last_ts - datetime.fromisoformat(r["ts"]) <= timedelta(minutes=30)]
    first = window[0]
    minutes = (last_ts - datetime.fromisoformat(first["ts"])).total_seconds() / 60
    if minutes < 5:
        return None
    rate = (last["mg_dl"] - first["mg_dl"]) / minutes
    if rate >= 2:
        direction = "rising_fast"
    elif rate >= 1:
        direction = "rising"
    elif rate <= -2:
        direction = "falling_fast"
    elif rate <= -1:
        direction = "falling"
    else:
        direction = "steady"
    return {"direction": direction, "mg_dl_per_min": round(rate, 2)}


def low_episodes(rows: list[sqlite3.Row], threshold: int = LOW, min_minutes: int = 15) -> int:
    """Count separate spells below the threshold that last at least min_minutes."""
    episodes = 0
    spell_start: datetime | None = None
    counted = False
    for row in rows:
        ts = datetime.fromisoformat(row["ts"])
        if row["mg_dl"] < threshold:
            if spell_start is None:
                spell_start, counted = ts, False
            if not counted and (ts - spell_start) >= timedelta(minutes=min_minutes):
                episodes += 1
                counted = True
        else:
            spell_start = None
    return episodes


def hours_above(rows: list[sqlite3.Row], threshold: int, step_minutes: int = 15) -> float:
    return round(sum(step_minutes for r in rows if r["mg_dl"] > threshold) / 60, 1)


def day_summary(conn: sqlite3.Connection, day: date, target_low: int, target_high: int) -> dict[str, Any]:
    start = datetime.combine(day, datetime.min.time())
    rows = glucose_between(conn, start, start + timedelta(days=1))
    stats_rows = stat_readings(rows)
    values = [r["mg_dl"] for r in stats_rows]
    sensor_count = sum(1 for r in rows if r["kind"] == "sensor")
    prev_day, next_day = adjacent_glucose_dates(conn, day)

    summary: dict[str, Any] = {
        "date": day.isoformat(),
        "prev_date": prev_day.isoformat() if prev_day else None,
        "next_date": next_day.isoformat() if next_day else None,
        "readings": [{"t": r["ts"], "v": round(r["mg_dl"]), "kind": r["kind"]} for r in rows],
        "bands": band_shares(values, target_low, target_high),
        "coverage_pct": min(100, round(100 * sensor_count / SENSOR_READINGS_PER_DAY)),
        "average": round(sum(values) / len(values)) if values else None,
        "min": round(min(values)) if values else None,
        "max": round(max(values)) if values else None,
        "lows": low_episodes(stats_rows),
        "hours_above_target": hours_above(stats_rows, target_high),
        "latest": None,
    }
    if rows:
        last = rows[-1]
        summary["latest"] = {"t": last["ts"], "v": round(last["mg_dl"]), "trend": trend(rows)}

    doses = insulin_between(conn, start, start + timedelta(days=1))
    summary["insulin"] = [{"t": d["ts"], "units": d["units"], "kind": d["kind"]} for d in doses]
    summary["insulin_totals"] = {
        kind: round(sum(d["units"] or 0 for d in doses if d["kind"] == kind), 1) for kind in ("rapid", "long")
    }
    # Long-acting is often taken around midnight, so show the latest dose up to 18 hours before the day too.
    last_long = conn.execute(
        "SELECT ts, units FROM insulin WHERE excluded = 0 AND kind = 'long' AND ts >= ? AND ts < ? ORDER BY ts DESC LIMIT 1",
        ((start - timedelta(hours=18)).isoformat(timespec="seconds"), (start + timedelta(days=1)).isoformat(timespec="seconds")),
    ).fetchone()
    summary["last_long"] = {"t": last_long["ts"], "units": last_long["units"]} if last_long else None
    return summary


def insulin_between(conn: sqlite3.Connection, start: datetime, end: datetime) -> list[sqlite3.Row]:
    """Doses that count: priming shots and other excluded entries are left out."""
    return conn.execute(
        "SELECT ts, units, kind FROM insulin WHERE excluded = 0 AND ts >= ? AND ts < ? ORDER BY ts",
        (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
    ).fetchall()
