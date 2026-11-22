"""Cronometer exports: servings (times) + dailysummary (nutrition)."""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

NUTRIENT_COLS = {
    "carbs": "Carbs (g)",
    "net_carbs": "Net Carbs (g)",
    "fibre": "Fiber (g)",
    "sugar": "Sugars (g)",
    "protein": "Protein (g)",
    "fat": "Fat (g)",
    "alcohol": "Alcohol (g)",
    "kcal": "Energy (kcal)",
}


def is_servings_export(head_lines: list[str]) -> bool:
    head = "".join(head_lines).lower()
    return "food name" in head and "group" in head and "time" in head and "day" in head


def is_daily_summary_export(head_lines: list[str]) -> bool:
    head = "".join(head_lines).lower()
    return "net carbs" in head and "group" in head and "date" in head and "energy (kcal)" in head


@dataclass
class CronometerServings:
    items: list[dict[str, Any]] = field(default_factory=list)
    problems: dict[str, int] = field(default_factory=lambda: defaultdict(int))


@dataclass
class CronometerDaily:
    rows: list[dict[str, Any]] = field(default_factory=list)
    problems: dict[str, int] = field(default_factory=lambda: defaultdict(int))


def _parse_servings_ts(day: str, time_str: str) -> datetime | None:
    raw = f"{day.strip()} {time_str.strip()}"
    for fmt in ("%Y-%m-%d %I:%M %p", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def read_servings(path: Path) -> CronometerServings:
    data = CronometerServings()
    with open(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            ts = _parse_servings_ts(row.get("Day", ""), row.get("Time", ""))
            if ts is None:
                data.problems["unreadable_time"] += 1
                continue
            data.items.append(
                {
                    "ts": ts,
                    "day": ts.date().isoformat(),
                    "grp": (row.get("Group") or "").strip() or "Uncategorized",
                    "name": (row.get("Food Name") or "").strip() or "Food",
                    "amount": (row.get("Amount") or "").strip(),
                    "category": (row.get("Category") or "").strip(),
                }
            )
    data.items.sort(key=lambda item: item["ts"])
    return data


def read_daily_summary(path: Path) -> CronometerDaily:
    data = CronometerDaily()
    with open(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            day = (row.get("Date") or "").strip()
            grp = (row.get("Group") or "").strip()
            if not day or not grp:
                data.problems["bad_row"] += 1
                continue
            nutrients = {}
            for key, col in NUTRIENT_COLS.items():
                raw = (row.get(col) or "").strip()
                try:
                    nutrients[key] = float(raw) if raw else None
                except ValueError:
                    nutrients[key] = None
            data.rows.append({"date": day, "grp": grp, "nutrients": nutrients})
    return data


def _cluster_occasions(items: list[dict[str, Any]], gap_min: int) -> list[dict[str, Any]]:
    if not items:
        return []
    gap = timedelta(minutes=gap_min)
    occasions: list[dict[str, Any]] = []
    current = {"items": [items[0]], "start": items[0]["ts"], "end": items[0]["ts"]}
    for item in items[1:]:
        if item["ts"] - current["end"] > gap:
            occasions.append(current)
            current = {"items": [item], "start": item["ts"], "end": item["ts"]}
        else:
            current["items"].append(item)
            current["end"] = item["ts"]
    occasions.append(current)

    for occ in occasions:
        groups = sorted({i["grp"] for i in occ["items"]})
        # Prefer Dinner/Lunch/Breakfast label when only one meal group; else "Eating".
        meal_groups = [g for g in groups if g not in ("Uncategorized", "Snacks")]
        if len(meal_groups) == 1 and len(groups) == 1:
            label = meal_groups[0]
        elif len(groups) == 1:
            label = groups[0]
        else:
            label = "Eating"
        occ["label"] = label
        occ["groups"] = groups
        occ["day"] = occ["start"].date().isoformat()
    return occasions


def _nutrition_for_occasion(occ: dict[str, Any], group_map: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    """Attach Cronometer group nutrition when the occasion owns whole groups."""
    owned: list[dict[str, Any]] = []
    for grp in occ["groups"]:
        totals = group_map.get((occ["day"], grp))
        if not totals:
            continue
        # Only claim exact group nutrition if every serving of that group that day is in this occasion.
        # Without the full-day item list here, we attach when the occasion is a single Cronometer group.
        if len(occ["groups"]) == 1:
            owned.append(totals)
    if not owned:
        return {"nutrition_basis": "none"}
    merged = {key: 0.0 for key in NUTRIENT_COLS}
    for totals in owned:
        for key in merged:
            val = totals.get(key)
            if val is not None:
                merged[key] += val
    return {**merged, "nutrition_basis": "exact"}


def summarise_servings(conn: sqlite3.Connection, data: CronometerServings, settings: dict[str, Any]) -> dict[str, Any]:
    gap = int(settings.get("occasion_gap_min") or 45)
    occasions = _cluster_occasions(data.items, gap)
    existing = {
        (r["start"], r["end"])
        for r in conn.execute("SELECT start, end FROM eating_occasions WHERE source = 'cronometer'")
    }
    start = occasions[0]["start"] if occasions else None
    end = occasions[-1]["end"] if occasions else None
    new = sum(1 for o in occasions if (o["start"].isoformat(), o["end"].isoformat()) not in existing)
    return {
        "format": "cronometer_servings",
        "format_label": "Cronometer servings",
        "unit": "",
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "items": [
            {
                "key": "occasions",
                "label": "Eating occasions",
                "count": len(occasions),
                "new": new,
                "detail": f"Grouped by gaps over {gap} minutes · {len(data.items)} foods",
            }
        ],
        "insulin": None,
        "problems": dict(data.problems),
        "ignored": {},
        "_occasions": occasions,
    }


def summarise_daily(conn: sqlite3.Connection, data: CronometerDaily) -> dict[str, Any]:
    groups = [r for r in data.rows if r["grp"] != "Total"]
    totals = [r for r in data.rows if r["grp"] == "Total"]
    existing_g = {(r["date"], r["grp"]) for r in conn.execute(
        "SELECT date, grp FROM group_totals WHERE source = 'cronometer'"
    )}
    existing_d = {r["date"] for r in conn.execute("SELECT date FROM daily_nutrition WHERE source = 'cronometer'")}
    dates = sorted({r["date"] for r in data.rows})
    return {
        "format": "cronometer_daily",
        "format_label": "Cronometer daily summary",
        "unit": "",
        "start": dates[0] if dates else None,
        "end": dates[-1] if dates else None,
        "items": [
            {
                "key": "group_totals",
                "label": "Meal-group nutrition",
                "count": len(groups),
                "new": sum(1 for r in groups if (r["date"], r["grp"]) not in existing_g),
                "detail": "Breakfast / Lunch / Dinner / Snacks macros",
            },
            {
                "key": "daily_nutrition",
                "label": "Daily nutrition totals",
                "count": len(totals),
                "new": sum(1 for r in totals if r["date"] not in existing_d),
            },
        ],
        "insulin": None,
        "problems": dict(data.problems),
        "ignored": {},
        "_rows": data.rows,
    }


def commit_servings(
    conn: sqlite3.Connection,
    occasions: list[dict[str, Any]],
    batch_id: int,
    include: set[str],
    from_date: date | None,
) -> dict[str, int]:
    if "occasions" not in include:
        return {}
    group_map = {
        (r["date"], r["grp"]): json.loads(r["nutrients"])
        for r in conn.execute("SELECT date, grp, nutrients FROM group_totals WHERE source = 'cronometer'")
    }
    counts = {"occasions": 0, "food_items": 0}
    for occ in occasions:
        if from_date and occ["start"].date() < from_date:
            continue
        start_s, end_s = occ["start"].isoformat(), occ["end"].isoformat()
        exists = conn.execute(
            "SELECT id FROM eating_occasions WHERE source = 'cronometer' AND start = ? AND end = ?",
            (start_s, end_s),
        ).fetchone()
        if exists:
            continue
        nutrition = _nutrition_for_occasion(occ, group_map)
        cur = conn.execute(
            "INSERT INTO eating_occasions (start, end, label, groups, carbs, net_carbs, fibre, sugar, protein, fat, "
            "alcohol, kcal, nutrition_basis, source, import_batch_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'cronometer', ?)",
            (
                start_s,
                end_s,
                occ["label"],
                json.dumps(occ["groups"]),
                nutrition.get("carbs"),
                nutrition.get("net_carbs"),
                nutrition.get("fibre"),
                nutrition.get("sugar"),
                nutrition.get("protein"),
                nutrition.get("fat"),
                nutrition.get("alcohol"),
                nutrition.get("kcal"),
                nutrition.get("nutrition_basis", "none"),
                batch_id,
            ),
        )
        occasion_id = cur.lastrowid
        counts["occasions"] += 1
        for item in occ["items"]:
            conn.execute(
                "INSERT INTO food_items (ts, name, amount, category, grp, occasion_id, nutrition_basis, source, import_batch_id) "
                "VALUES (?, ?, ?, ?, ?, ?, 'none', 'cronometer', ?)",
                (
                    item["ts"].isoformat(),
                    item["name"],
                    item["amount"],
                    item["category"],
                    item["grp"],
                    occasion_id,
                    batch_id,
                ),
            )
            counts["food_items"] += 1
    return counts


def commit_daily(
    conn: sqlite3.Connection,
    rows: list[dict[str, Any]],
    batch_id: int,
    include: set[str],
    from_date: date | None,
) -> dict[str, int]:
    counts = {"group_totals": 0, "daily_nutrition": 0}
    for row in rows:
        day = date.fromisoformat(row["date"])
        if from_date and day < from_date:
            continue
        payload = json.dumps(row["nutrients"])
        if row["grp"] == "Total":
            if "daily_nutrition" not in include:
                continue
            before = conn.total_changes
            conn.execute(
                "INSERT INTO daily_nutrition (date, nutrients, source, import_batch_id) VALUES (?, ?, 'cronometer', ?) "
                "ON CONFLICT(date, source) DO UPDATE SET nutrients = excluded.nutrients, import_batch_id = excluded.import_batch_id",
                (row["date"], payload, batch_id),
            )
            if conn.total_changes > before:
                counts["daily_nutrition"] += 1
        else:
            if "group_totals" not in include:
                continue
            before = conn.total_changes
            conn.execute(
                "INSERT INTO group_totals (date, grp, nutrients, source, import_batch_id) VALUES (?, ?, ?, 'cronometer', ?) "
                "ON CONFLICT(date, grp, source) DO UPDATE SET nutrients = excluded.nutrients, import_batch_id = excluded.import_batch_id",
                (row["date"], row["grp"], payload, batch_id),
            )
            if conn.total_changes > before:
                counts["group_totals"] += 1

    # Backfill occasion macros for single-group occasions still missing nutrition.
    _backfill_occasion_nutrition(conn)
    return counts


def _backfill_occasion_nutrition(conn: sqlite3.Connection) -> None:
    group_map = {
        (r["date"], r["grp"]): json.loads(r["nutrients"])
        for r in conn.execute("SELECT date, grp, nutrients FROM group_totals WHERE source = 'cronometer'")
    }
    rows = conn.execute(
        "SELECT id, start, groups FROM eating_occasions WHERE source = 'cronometer' AND (carbs IS NULL OR nutrition_basis = 'none')"
    ).fetchall()
    for row in rows:
        groups = json.loads(row["groups"] or "[]")
        if len(groups) != 1:
            continue
        day = row["start"][:10]
        nutrients = group_map.get((day, groups[0]))
        if not nutrients:
            continue
        conn.execute(
            "UPDATE eating_occasions SET carbs = ?, net_carbs = ?, fibre = ?, sugar = ?, protein = ?, fat = ?, "
            "alcohol = ?, kcal = ?, nutrition_basis = 'exact' WHERE id = ?",
            (
                nutrients.get("carbs"),
                nutrients.get("net_carbs"),
                nutrients.get("fibre"),
                nutrients.get("sugar"),
                nutrients.get("protein"),
                nutrients.get("fat"),
                nutrients.get("alcohol"),
                nutrients.get("kcal"),
                row["id"],
            ),
        )
