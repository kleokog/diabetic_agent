"""LibreLink / LibreView CSV export.

Record types in the export: 0 = sensor history (every 15 minutes), 1 = scan,
4 = insulin, 5 = carbohydrates, 6 = sensor events (no glucose, ignored).
Insulin from connected pens arrives one row per shot, priming shots included.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

MMOL_TO_MG = 18.016
GLUCOSE_MIN, GLUCOSE_MAX = 20, 600
LIBRELINK_APP = "FreeStyle LibreLink"


def is_libre_export(head_lines: list[str]) -> bool:
    return any("Device Timestamp" in line and "Record Type" in line for line in head_lines)


@dataclass
class LibreData:
    unit: str = "mg/dL"
    glucose: list[dict[str, Any]] = field(default_factory=list)
    insulin: list[dict[str, Any]] = field(default_factory=list)
    carbs: list[dict[str, Any]] = field(default_factory=list)
    ketones: list[dict[str, Any]] = field(default_factory=list)
    problems: Counter = field(default_factory=Counter)
    ignored: Counter = field(default_factory=Counter)


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip().replace(",", ".")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _date_order(samples: list[str]) -> str:
    """Return 'dmy' or 'mdy' by looking for a first or second field above 12."""
    for sample in samples:
        parts = re.split(r"[-/.]", sample.split(" ")[0])
        if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
            if len(parts[0]) == 4:
                return "ymd"
            if int(parts[0]) > 12:
                return "dmy"
            if int(parts[1]) > 12:
                return "mdy"
    return "dmy"


def _parse_ts(value: str, order: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    date_part, _, time_part = value.partition(" ")
    parts = re.split(r"[-/.]", date_part)
    if len(parts) != 3:
        return None
    try:
        if order == "ymd":
            y, m, d = (int(p) for p in parts)
        elif order == "mdy":
            m, d, y = (int(p) for p in parts)
        else:
            d, m, y = (int(p) for p in parts)
        hh, mm = (int(p) for p in time_part.strip().split(":")[:2]) if time_part else (0, 0)
        return datetime(y, m, d, hh, mm)
    except ValueError:
        return None


def _find(columns: list[str], *needles: str) -> str | None:
    for column in columns:
        lowered = column.lower()
        if all(n.lower() in lowered for n in needles):
            return column
    return None


def read(path: Path) -> LibreData:
    data = LibreData()
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as handle:
        lines = handle.read().splitlines()
    header_index = next(i for i, line in enumerate(lines[:5]) if "Device Timestamp" in line)
    reader = csv.DictReader(lines[header_index:])
    columns = [c.strip() for c in (reader.fieldnames or []) if c]
    reader.fieldnames = [c.strip() if c else "" for c in reader.fieldnames or []]
    rows = list(reader)

    historic = _find(columns, "historic glucose")
    scan = _find(columns, "scan glucose")
    strip = _find(columns, "strip glucose")
    if historic and "mmol" in historic.lower():
        data.unit = "mmol/L"
    factor = MMOL_TO_MG if data.unit == "mmol/L" else 1.0

    rapid = _find(columns, "rapid-acting insulin (units)")
    rapid_flag = _find(columns, "non-numeric rapid-acting")
    long_ = next((c for c in columns if "long-acting insulin" in c.lower() and "non-numeric" not in c.lower()), None)
    long_flag = _find(columns, "non-numeric long-acting")
    meal_ins = _find(columns, "meal insulin")
    correction_ins = _find(columns, "correction insulin")
    carbs_g = _find(columns, "carbohydrates (grams)")
    notes = _find(columns, "notes")
    ketone_cols = [c for c in columns if "ketone" in c.lower()]

    order = _date_order([r.get("Device Timestamp", "") for r in rows[:2000]])

    for row in rows:
        ts = _parse_ts(row.get("Device Timestamp", ""), order)
        if ts is None:
            data.problems["unreadable_time"] += 1
            continue
        record_type = (row.get("Record Type") or "").strip()
        device = (row.get("Device") or "").strip()
        serial = (row.get("Serial Number") or "").strip()

        for column, kind in ((historic, "sensor"), (scan, "scan"), (strip, "fingerstick")):
            value = _number(row.get(column)) if column else None
            if value is None:
                continue
            mg = value * factor
            if GLUCOSE_MIN <= mg <= GLUCOSE_MAX:
                data.glucose.append({"ts": ts, "mg_dl": round(mg, 1), "kind": kind})
            else:
                data.problems["glucose_out_of_range"] += 1

        for column, flag_column, logged_kind in ((rapid, rapid_flag, "rapid"), (long_, long_flag, "long")):
            units = _number(row.get(column)) if column else None
            flagged = bool(flag_column and (row.get(flag_column) or "").strip())
            if units is None and not flagged:
                continue
            purpose = "unknown"
            if logged_kind == "rapid" and meal_ins and _number(row.get(meal_ins)):
                purpose = "meal"
            elif logged_kind == "rapid" and correction_ins and _number(row.get(correction_ins)):
                purpose = "correction"
            data.insulin.append({
                "ts": ts, "units": units, "logged_kind": logged_kind, "purpose": purpose,
                "device": device or f"pen {serial}", "serial": serial,
                "is_pen": device != LIBRELINK_APP,
            })

        carbs = _number(row.get(carbs_g)) if carbs_g else None
        if carbs is not None and carbs > 0:
            data.carbs.append({"ts": ts, "carbs": carbs, "note": (row.get(notes) or "").strip() or None})

        for column in ketone_cols:
            value = _number(row.get(column))
            if value is not None:
                data.ketones.append({"ts": ts, "value": value})

        if record_type == "6":
            data.ignored["sensor_events"] += 1

    return data


def classify_insulin(entries: list[dict[str, Any]], long_min_units: float, priming_max_units: float,
                     priming_window_min: int) -> None:
    """Fix mislabelled doses and mark priming shots, in place.

    Doses above long_min_units are long-acting whichever column they were logged in.
    For each pen, shots within priming_window_min of each other form one injection:
    the largest shot is the dose and other shots of priming_max_units or less are priming.
    """
    for entry in entries:
        units = entry["units"]
        entry["kind"] = "long" if units is not None and units > long_min_units else entry["logged_kind"]
        entry["reclassified"] = entry["kind"] != entry["logged_kind"]
        entry["likely_priming"] = False

    by_pen: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        if entry["is_pen"] and entry["units"] is not None:
            by_pen[entry["serial"]].append(entry)

    for shots in by_pen.values():
        shots.sort(key=lambda e: e["ts"])
        cluster: list[dict[str, Any]] = []
        for shot in shots + [None]:
            if shot is not None and cluster and (shot["ts"] - cluster[-1]["ts"]).total_seconds() <= priming_window_min * 60:
                cluster.append(shot)
                continue
            if len(cluster) > 1:
                dose = max(cluster, key=lambda e: e["units"])
                for other in cluster:
                    if other is not dose and other["units"] <= priming_max_units:
                        other["likely_priming"] = True
            cluster = [shot] if shot is not None else []

    seen: Counter = Counter()
    for entry in entries:
        base = f"{entry['serial']}|{entry['ts'].isoformat()}|{entry['logged_kind']}|{entry['units']}"
        seen[base] += 1
        entry["source_key"] = f"{base}|{seen[base]}"


def summarise(conn: sqlite3.Connection, data: LibreData, settings: dict[str, Any]) -> dict[str, Any]:
    classify_insulin(data.insulin, settings["long_acting_min_units"], settings["priming_max_units"],
                     settings["priming_window_min"])
    all_ts = [g["ts"] for g in data.glucose] + [i["ts"] for i in data.insulin]
    start, end = (min(all_ts), max(all_ts)) if all_ts else (None, None)

    existing_glucose = set()
    if data.glucose:
        lo = min(g["ts"] for g in data.glucose).isoformat()
        hi = max(g["ts"] for g in data.glucose).isoformat()
        existing_glucose = {(r["ts"], r["kind"]) for r in conn.execute(
            "SELECT ts, kind FROM glucose WHERE ts BETWEEN ? AND ?", (lo, hi))}
    existing_insulin = {r["source_key"] for r in conn.execute(
        "SELECT source_key FROM insulin WHERE source = 'libre' AND source_key IS NOT NULL")}
    existing_carbs = {r["start"] for r in conn.execute("SELECT start FROM eating_occasions WHERE source = 'libre'")}

    def glucose_item(kind: str, label: str) -> dict[str, Any]:
        # Times can repeat inside one export (for example when clocks go back), so count unique times.
        times = {g["ts"].isoformat() for g in data.glucose if g["kind"] == kind}
        new = sum(1 for ts in times if (ts, kind) not in existing_glucose)
        return {"key": kind, "label": label, "count": len(times), "new": new}

    doses = [i for i in data.insulin if not i["likely_priming"]]
    primes = [i for i in data.insulin if i["likely_priming"]]
    items = [
        glucose_item("sensor", "Sensor readings"),
        glucose_item("scan", "Scans"),
        glucose_item("fingerstick", "Finger-prick readings"),
        {
            "key": "insulin", "label": "Insulin doses", "count": len(doses),
            "new": sum(1 for i in data.insulin if i["source_key"] not in existing_insulin and not i["likely_priming"]),
            "detail": f"{sum(1 for i in doses if i['kind'] == 'rapid'):,} rapid · {sum(1 for i in doses if i['kind'] == 'long'):,} long-acting",
        },
        {"key": "carbs", "label": "Carb entries", "count": len(data.carbs),
         "new": sum(1 for c in data.carbs if c["ts"].isoformat() not in existing_carbs)},
        {"key": "ketones", "label": "Ketone readings", "count": len(data.ketones), "new": len(data.ketones)},
    ]
    return {
        "format": "libre",
        "format_label": "LibreLink export",
        "unit": data.unit,
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "items": [item for item in items if item["count"] > 0],
        "insulin": {
            "shots": len(data.insulin),
            "priming": len(primes),
            "reclassified": sum(1 for i in data.insulin if i["reclassified"]),
            "long_acting_min_units": settings["long_acting_min_units"],
            "priming_max_units": settings["priming_max_units"],
        },
        "problems": {
            "unreadable_time": data.problems["unreadable_time"],
            "glucose_out_of_range": data.problems["glucose_out_of_range"],
        },
        "ignored": {"sensor_events": data.ignored["sensor_events"]},
    }


def commit(conn: sqlite3.Connection, data: LibreData, batch_id: int, include: set[str],
           include_priming: bool, from_date: date | None) -> dict[str, int]:
    """Insert the chosen data. classify_insulin must already have run (summarise does this)."""
    def keep(ts: datetime) -> bool:
        return from_date is None or ts.date() >= from_date

    counts: dict[str, int] = {}
    for kind in ("sensor", "scan", "fingerstick"):
        if kind not in include:
            continue
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO glucose (ts, mg_dl, kind, source, import_batch_id) VALUES (?, ?, ?, 'libre', ?)",
            [(g["ts"].isoformat(), g["mg_dl"], kind, batch_id) for g in data.glucose if g["kind"] == kind and keep(g["ts"])],
        )
        counts[kind] = conn.total_changes - before

    if "insulin" in include:
        conn.executemany(
            "INSERT OR IGNORE INTO insulin (ts, kind, units, purpose, likely_priming, excluded, device, logged_kind, "
            "reclassified, source_key, source, import_batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'libre', ?)",
            [
                (i["ts"].isoformat(), i["kind"], i["units"], i["purpose"], int(i["likely_priming"]),
                 int(i["likely_priming"] and not include_priming), i["device"], i["logged_kind"],
                 int(i["reclassified"]), i["source_key"], batch_id)
                for i in data.insulin if keep(i["ts"])
            ],
        )
        row = conn.execute(
            "SELECT SUM(likely_priming = 0), SUM(likely_priming = 1) FROM insulin WHERE import_batch_id = ?", (batch_id,)
        ).fetchone()
        counts["insulin"] = row[0] or 0
        counts["priming"] = row[1] or 0

    if "carbs" in include:
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO eating_occasions (start, end, label, carbs, nutrition_basis, notes, source, import_batch_id) "
            "VALUES (?, ?, 'Logged in LibreLink', ?, 'exact', ?, 'libre', ?)",
            [(c["ts"].isoformat(), c["ts"].isoformat(), c["carbs"], c["note"], batch_id) for c in data.carbs if keep(c["ts"])],
        )
        counts["carbs"] = conn.total_changes - before

    if "ketones" in include:
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO measurements (date, metric, value, unit, source, import_batch_id) "
            "VALUES (?, 'ketones', ?, 'mmol/L', 'libre', ?)",
            [(k["ts"].isoformat(), k["value"], batch_id) for k in data.ketones if keep(k["ts"])],
        )
        counts["ketones"] = conn.total_changes - before
    return counts
