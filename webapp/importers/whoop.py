"""Whoop data-export CSVs: sleeps, workouts, physiological cycles."""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any


def is_sleeps_export(head_lines: list[str]) -> bool:
    head = "".join(head_lines).lower()
    return "sleep onset" in head and "asleep duration" in head


def is_workouts_export(head_lines: list[str]) -> bool:
    head = "".join(head_lines).lower()
    return "workout start time" in head and "activity name" in head


def is_cycles_export(head_lines: list[str]) -> bool:
    head = "".join(head_lines).lower()
    return "recovery score" in head and "heart rate variability" in head and "day strain" in head


def _parse_ts(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    # Whoop uses "2026-10-21 01:30:46" local wall time; timezone column is separate.
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    return None


def _num(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _boolish(value: str | None) -> bool:
    return (value or "").strip().lower() in {"true", "1", "yes"}


@dataclass
class WhoopSleeps:
    rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class WhoopWorkouts:
    rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class WhoopCycles:
    rows: list[dict[str, Any]] = field(default_factory=list)


def read_sleeps(path: Path) -> WhoopSleeps:
    data = WhoopSleeps()
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            onset = _parse_ts(row.get("Sleep onset", ""))
            if onset is None:
                continue
            wake = _parse_ts(row.get("Wake onset", ""))
            data.rows.append(
                {
                    "onset": onset,
                    "wake": wake,
                    "is_nap": _boolish(row.get("Nap")),
                    "asleep_min": _num(row.get("Asleep duration (min)")),
                    "in_bed_min": _num(row.get("In bed duration (min)")),
                    "light_min": _num(row.get("Light sleep duration (min)")),
                    "deep_min": _num(row.get("Deep (SWS) duration (min)")),
                    "rem_min": _num(row.get("REM duration (min)")),
                    "awake_min": _num(row.get("Awake duration (min)")),
                    "performance_pct": _num(row.get("Sleep performance %")),
                    "need_min": _num(row.get("Sleep need (min)")),
                    "debt_min": _num(row.get("Sleep debt (min)")),
                    "efficiency_pct": _num(row.get("Sleep efficiency %")),
                    "consistency_pct": _num(row.get("Sleep consistency %")),
                    "resp_rate": _num(row.get("Respiratory rate (rpm)")),
                    "raw": dict(row),
                }
            )
    return data


def read_workouts(path: Path) -> WhoopWorkouts:
    data = WhoopWorkouts()
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            start = _parse_ts(row.get("Workout start time", ""))
            if start is None:
                continue
            end = _parse_ts(row.get("Workout end time", ""))
            zones = {
                "z1": _num(row.get("HR Zone 1 %")),
                "z2": _num(row.get("HR Zone 2 %")),
                "z3": _num(row.get("HR Zone 3 %")),
                "z4": _num(row.get("HR Zone 4 %")),
                "z5": _num(row.get("HR Zone 5 %")),
            }
            data.rows.append(
                {
                    "start": start,
                    "end": end,
                    "duration_min": _num(row.get("Duration (min)")),
                    "activity": (row.get("Activity name") or "Workout").strip(),
                    "strain": _num(row.get("Activity Strain")),
                    "kcal": _num(row.get("Energy burned (cal)")),
                    "avg_hr": _num(row.get("Average HR (bpm)")),
                    "max_hr": _num(row.get("Max HR (bpm)")),
                    "hr_zones": zones,
                    "raw": dict(row),
                }
            )
    return data


def read_cycles(path: Path) -> WhoopCycles:
    data = WhoopCycles()
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            start = _parse_ts(row.get("Cycle start time", ""))
            if start is None:
                continue
            end = _parse_ts(row.get("Cycle end time", ""))
            local_date = start.date().isoformat()
            data.rows.append(
                {
                    "cycle_start": start,
                    "cycle_end": end,
                    "local_date": local_date,
                    "recovery_pct": _num(row.get("Recovery score %")),
                    "resting_hr": _num(row.get("Resting heart rate (bpm)")),
                    "hrv_ms": _num(row.get("Heart rate variability (ms)")),
                    "skin_temp_c": _num(row.get("Skin temp (celsius)")),
                    "spo2_pct": _num(row.get("Blood oxygen %")),
                    "day_strain": _num(row.get("Day Strain")),
                    "kcal": _num(row.get("Energy burned (cal)")),
                    "avg_hr": _num(row.get("Average HR (bpm)")),
                    "max_hr": _num(row.get("Max HR (bpm)")),
                    "raw": dict(row),
                }
            )
    return data


def summarise_sleeps(conn: sqlite3.Connection, data: WhoopSleeps) -> dict[str, Any]:
    existing = {r["onset"] for r in conn.execute("SELECT onset FROM sleep WHERE source = 'whoop'")}
    nights = [r for r in data.rows if not r["is_nap"]]
    naps = [r for r in data.rows if r["is_nap"]]
    ts = [r["onset"] for r in data.rows]
    return {
        "format": "whoop_sleeps",
        "format_label": "Whoop sleeps",
        "unit": "",
        "start": min(ts).isoformat() if ts else None,
        "end": max(ts).isoformat() if ts else None,
        "items": [
            {
                "key": "sleep",
                "label": "Nights of sleep",
                "count": len(nights),
                "new": sum(1 for r in nights if r["onset"].isoformat() not in existing),
                "detail": f"{len(naps)} naps also in file",
            }
        ],
        "insulin": None,
        "problems": {},
        "ignored": {},
        "_rows": data.rows,
    }


def summarise_workouts(conn: sqlite3.Connection, data: WhoopWorkouts) -> dict[str, Any]:
    existing = {
        (r["start"], r["activity"])
        for r in conn.execute("SELECT start, activity FROM workouts WHERE source = 'whoop'")
    }
    ts = [r["start"] for r in data.rows]
    return {
        "format": "whoop_workouts",
        "format_label": "Whoop workouts",
        "unit": "",
        "start": min(ts).isoformat() if ts else None,
        "end": max(ts).isoformat() if ts else None,
        "items": [
            {
                "key": "workouts",
                "label": "Workouts",
                "count": len(data.rows),
                "new": sum(1 for r in data.rows if (r["start"].isoformat(), r["activity"]) not in existing),
                "detail": ", ".join(sorted({r["activity"] for r in data.rows})[:6]),
            }
        ],
        "insulin": None,
        "problems": {},
        "ignored": {},
        "_rows": data.rows,
    }


def summarise_cycles(conn: sqlite3.Connection, data: WhoopCycles) -> dict[str, Any]:
    existing = {r["cycle_start"] for r in conn.execute("SELECT cycle_start FROM daily_physiology WHERE source = 'whoop'")}
    ts = [r["cycle_start"] for r in data.rows]
    return {
        "format": "whoop_cycles",
        "format_label": "Whoop physiological cycles",
        "unit": "",
        "start": min(ts).isoformat() if ts else None,
        "end": max(ts).isoformat() if ts else None,
        "items": [
            {
                "key": "physiology",
                "label": "Daily recovery / strain",
                "count": len(data.rows),
                "new": sum(1 for r in data.rows if r["cycle_start"].isoformat() not in existing),
                "detail": "Recovery %, HRV, resting HR, day strain",
            }
        ],
        "insulin": None,
        "problems": {},
        "ignored": {},
        "_rows": data.rows,
    }


def commit_sleeps(conn: sqlite3.Connection, rows: list[dict[str, Any]], batch_id: int, include: set[str], from_date: date | None) -> dict[str, int]:
    if "sleep" not in include:
        return {}
    count = 0
    for row in rows:
        if from_date and row["onset"].date() < from_date:
            continue
        before = conn.total_changes
        conn.execute(
            "INSERT OR IGNORE INTO sleep (onset, wake, is_nap, asleep_min, in_bed_min, light_min, deep_min, rem_min, "
            "awake_min, performance_pct, need_min, debt_min, efficiency_pct, consistency_pct, resp_rate, raw, source, import_batch_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'whoop', ?)",
            (
                row["onset"].isoformat(),
                row["wake"].isoformat() if row["wake"] else None,
                int(row["is_nap"]),
                row["asleep_min"],
                row["in_bed_min"],
                row["light_min"],
                row["deep_min"],
                row["rem_min"],
                row["awake_min"],
                row["performance_pct"],
                row["need_min"],
                row["debt_min"],
                row["efficiency_pct"],
                row["consistency_pct"],
                row["resp_rate"],
                json.dumps(row["raw"]),
                batch_id,
            ),
        )
        if conn.total_changes > before:
            count += 1
    return {"sleep": count}


def commit_workouts(conn: sqlite3.Connection, rows: list[dict[str, Any]], batch_id: int, include: set[str], from_date: date | None) -> dict[str, int]:
    if "workouts" not in include:
        return {}
    count = 0
    for row in rows:
        if from_date and row["start"].date() < from_date:
            continue
        before = conn.total_changes
        conn.execute(
            "INSERT OR IGNORE INTO workouts (start, end, duration_min, activity, strain, kcal, avg_hr, max_hr, hr_zones, raw, source, import_batch_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'whoop', ?)",
            (
                row["start"].isoformat(),
                row["end"].isoformat() if row["end"] else None,
                row["duration_min"],
                row["activity"],
                row["strain"],
                row["kcal"],
                row["avg_hr"],
                row["max_hr"],
                json.dumps(row["hr_zones"]),
                json.dumps(row["raw"]),
                batch_id,
            ),
        )
        if conn.total_changes > before:
            count += 1
    return {"workouts": count}


def commit_cycles(conn: sqlite3.Connection, rows: list[dict[str, Any]], batch_id: int, include: set[str], from_date: date | None) -> dict[str, int]:
    if "physiology" not in include:
        return {}
    count = 0
    for row in rows:
        if from_date and row["cycle_start"].date() < from_date:
            continue
        before = conn.total_changes
        conn.execute(
            "INSERT OR IGNORE INTO daily_physiology (cycle_start, cycle_end, local_date, recovery_pct, resting_hr, hrv_ms, "
            "skin_temp_c, spo2_pct, day_strain, kcal, avg_hr, max_hr, raw, source, import_batch_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'whoop', ?)",
            (
                row["cycle_start"].isoformat(),
                row["cycle_end"].isoformat() if row["cycle_end"] else None,
                row["local_date"],
                row["recovery_pct"],
                row["resting_hr"],
                row["hrv_ms"],
                row["skin_temp_c"],
                row["spo2_pct"],
                row["day_strain"],
                row["kcal"],
                row["avg_hr"],
                row["max_hr"],
                json.dumps(row["raw"]),
                batch_id,
            ),
        )
        if conn.total_changes > before:
            count += 1
    return {"physiology": count}
