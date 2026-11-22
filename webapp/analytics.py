"""Glucose statistics used by the screens and, later, by the coach."""

from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

VERY_LOW = 54
LOW = 70
VERY_HIGH = 250
SENSOR_READINGS_PER_DAY = 96  # LibreLink history stores one reading every 15 minutes.
# About 8 hours of 15-minute sensor history — enough for a meaningful day CV.
MIN_DAY_READINGS_FOR_CV = 32
DEFAULT_CV_UNSTABLE_PCT = 36.0

# Everyday CV scale. Consensus “unstable” still starts at 36% (Bad and above).
CV_SPECTRUM: list[tuple[str, str, float | None]] = [
    ("perfect", "Perfect", 25.0),
    ("good", "Good", 30.0),
    ("medium", "Medium", 36.0),
    ("bad", "Bad", 45.0),
    ("very_bad", "Very bad", None),
]


def cv_spectrum(cv_pct: float) -> dict[str, str]:
    """Map a CV% to Perfect / Good / Medium / Bad / Very bad."""
    for key, label, upper in CV_SPECTRUM:
        if upper is None or cv_pct < upper:
            return {"key": key, "label": label}
    return {"key": "very_bad", "label": "Very bad"}


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


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def std_dev(values: list[float]) -> float | None:
    """Sample standard deviation (n−1), matching typical CGM report practice."""
    if len(values) < 2:
        return None
    avg = sum(values) / len(values)
    variance = sum((v - avg) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def cv_percent(values: list[float]) -> float | None:
    """Coefficient of variation: (SD / mean) × 100. Primary glycemic variability metric."""
    avg = mean(values)
    sd = std_dev(values)
    if avg is None or sd is None or avg <= 0:
        return None
    return 100.0 * sd / avg


def gmi_percent(average_mg_dl: float) -> float:
    """Glucose Management Indicator (estimated HbA1c %) from mean glucose."""
    return round(3.31 + 0.02392 * average_mg_dl, 1)


def variability(
    values: list[float],
    *,
    unstable_pct: float = DEFAULT_CV_UNSTABLE_PCT,
    min_readings: int = 2,
) -> dict[str, Any] | None:
    """CV%, SD, and five-level spectrum label for a set of glucose readings."""
    if len(values) < min_readings:
        return None
    avg = mean(values)
    sd = std_dev(values)
    cv = cv_percent(values)
    if avg is None or sd is None or cv is None:
        return None
    spectrum = cv_spectrum(cv)
    return {
        "cv_pct": round(cv, 1),
        "sd": round(sd, 1),
        "mean": round(avg),
        "stable": cv < unstable_pct,
        "spectrum": spectrum["key"],
        "label": spectrum["label"],
        "threshold_pct": unstable_pct,
        "n": len(values),
    }


def day_summary(
    conn: sqlite3.Connection,
    day: date,
    target_low: int,
    target_high: int,
    *,
    cv_unstable_pct: float = DEFAULT_CV_UNSTABLE_PCT,
) -> dict[str, Any]:
    start = datetime.combine(day, datetime.min.time())
    rows = glucose_between(conn, start, start + timedelta(days=1))
    stats_rows = stat_readings(rows)
    values = [r["mg_dl"] for r in stats_rows]
    sensor_count = sum(1 for r in rows if r["kind"] == "sensor")
    prev_day, next_day = adjacent_glucose_dates(conn, day)
    day_cv = variability(values, unstable_pct=cv_unstable_pct, min_readings=MIN_DAY_READINGS_FOR_CV)

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
        "variability": day_cv,
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

    end = start + timedelta(days=1)
    meals = conn.execute(
        "SELECT start, label, carbs FROM eating_occasions WHERE start >= ? AND start < ? ORDER BY start",
        (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
    ).fetchall()
    summary["meals"] = [
        {"t": m["start"], "label": m["label"] or "Meal", "carbs": m["carbs"]} for m in meals
    ]
    workouts = conn.execute(
        "SELECT start, end, activity, duration_min FROM workouts WHERE start >= ? AND start < ? ORDER BY start",
        (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
    ).fetchall()
    summary["workouts"] = [
        {
            "t": w["start"],
            "end": w["end"],
            "activity": w["activity"],
            "duration_min": w["duration_min"],
        }
        for w in workouts
    ]
    return summary


def insulin_between(conn: sqlite3.Connection, start: datetime, end: datetime) -> list[sqlite3.Row]:
    """Doses that count: priming shots and other excluded entries are left out."""
    return conn.execute(
        "SELECT ts, units, kind FROM insulin WHERE excluded = 0 AND ts >= ? AND ts < ? ORDER BY ts",
        (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
    ).fetchall()


def _period_bundle(
    conn: sqlite3.Connection,
    start: date,
    end_exclusive: date,
    *,
    cv_unstable_pct: float = DEFAULT_CV_UNSTABLE_PCT,
) -> tuple[list[float], list[sqlite3.Row], list[dict[str, Any]]]:
    """Sensor-preferred values, raw stat rows, and per-day CV rows for a period."""
    all_values: list[float] = []
    all_rows: list[sqlite3.Row] = []
    daily: list[dict[str, Any]] = []
    day = start
    while day < end_exclusive:
        day_start = datetime.combine(day, datetime.min.time())
        rows = stat_readings(glucose_between(conn, day_start, day_start + timedelta(days=1)))
        values = [r["mg_dl"] for r in rows]
        all_values.extend(values)
        all_rows.extend(rows)
        day_var = variability(values, unstable_pct=cv_unstable_pct, min_readings=MIN_DAY_READINGS_FOR_CV)
        daily.append(
            {
                "date": day.isoformat(),
                "cv_pct": day_var["cv_pct"] if day_var else None,
                "spectrum": day_var["spectrum"] if day_var else None,
                "label": day_var["label"] if day_var else None,
                "average": round(sum(values) / len(values)) if values else None,
                "n": len(values),
            }
        )
        day += timedelta(days=1)
    return all_values, all_rows, daily


def hour_band_shares(
    rows: list[sqlite3.Row],
    target_low: int,
    target_high: int,
) -> list[dict[str, Any]]:
    """For each hour, % of readings below goal / in range / above goal."""
    buckets: list[list[float]] = [[] for _ in range(24)]
    for row in rows:
        hour = datetime.fromisoformat(row["ts"]).hour
        buckets[hour].append(row["mg_dl"])

    result = []
    for hour, values in enumerate(buckets):
        total = len(values)
        if total:
            low_n = sum(1 for v in values if round(v) < target_low)
            high_n = sum(1 for v in values if round(v) > target_high)
            in_n = total - low_n - high_n
            result.append(
                {
                    "hour": hour,
                    "low_pct": round(100 * low_n / total, 1),
                    "in_range_pct": round(100 * in_n / total, 1),
                    "high_pct": round(100 * high_n / total, 1),
                    "n": total,
                }
            )
        else:
            result.append({"hour": hour, "low_pct": 0.0, "in_range_pct": 0.0, "high_pct": 0.0, "n": 0})
    return result


def period_variability(
    values: list[float],
    daily: list[dict[str, Any]],
    *,
    cv_unstable_pct: float = DEFAULT_CV_UNSTABLE_PCT,
) -> dict[str, Any]:
    """Period CV plus within-day / day-to-day breakdown and a daily CV series."""
    period = variability(values, unstable_pct=cv_unstable_pct, min_readings=MIN_DAY_READINGS_FOR_CV)

    day_cvs = [d["cv_pct"] for d in daily if d["cv_pct"] is not None]
    day_means = [float(d["average"]) for d in daily if d["average"] is not None]
    within_day = round(sum(day_cvs) / len(day_cvs), 1) if day_cvs else None
    day_sd = std_dev(day_means)
    day_to_day_sd = round(day_sd, 1) if day_sd is not None else None
    unstable_days = sum(1 for cv in day_cvs if cv >= cv_unstable_pct)
    spectrum_days = {
        key: sum(1 for d in daily if d.get("spectrum") == key) for key, _, _ in CV_SPECTRUM
    }

    return {
        "period": period,
        "within_day_cv_pct": within_day,
        "day_to_day_sd": day_to_day_sd,
        "days_with_cv": len(day_cvs),
        "unstable_days": unstable_days,
        "spectrum_days": spectrum_days,
        "daily": daily,
        "values_n": len(values),
        "spectrum_scale": [
            {"key": key, "label": label, "upper": upper} for key, label, upper in CV_SPECTRUM
        ],
    }


def trends_summary(
    conn: sqlite3.Connection,
    *,
    days: int = 14,
    end: date | None = None,
    target_low: int = 80,
    target_high: int = 150,
    cv_unstable_pct: float = DEFAULT_CV_UNSTABLE_PCT,
) -> dict[str, Any]:
    """Trends for the last N days ending on `end` (default: latest glucose day)."""
    latest = latest_glucose_date(conn)
    if end is None:
        end = latest or date.today()
    # `end` is inclusive for the UI; analytics uses an exclusive upper bound.
    end_exclusive = end + timedelta(days=1)
    start = end_exclusive - timedelta(days=days)
    prev_end_exclusive = start
    prev_start = prev_end_exclusive - timedelta(days=days)

    values, rows, daily = _period_bundle(conn, start, end_exclusive, cv_unstable_pct=cv_unstable_pct)
    prev_values, _, prev_daily = _period_bundle(
        conn, prev_start, prev_end_exclusive, cv_unstable_pct=cv_unstable_pct
    )

    current = period_variability(values, daily, cv_unstable_pct=cv_unstable_pct)
    previous = period_variability(prev_values, prev_daily, cv_unstable_pct=cv_unstable_pct)

    avg = mean(values)
    prev_avg = mean(prev_values)
    bands_now = band_shares(values, target_low, target_high)
    bands_prev = band_shares(prev_values, target_low, target_high)
    in_range = next((b["pct"] for b in bands_now if b["key"] == "in_range"), 0.0)
    prev_in_range = next((b["pct"] for b in bands_prev if b["key"] == "in_range"), None)

    prev_cv = previous["period"]["cv_pct"] if previous["period"] else None
    cur_cv = current["period"]["cv_pct"] if current["period"] else None
    cv_delta = round(cur_cv - prev_cv, 1) if cur_cv is not None and prev_cv is not None else None
    avg_delta = round(avg - prev_avg) if avg is not None and prev_avg is not None else None
    tir_delta = (
        round(in_range - prev_in_range, 1) if prev_in_range is not None and values else None
    )

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": days,
        "prev_start": prev_start.isoformat(),
        "prev_end": (prev_end_exclusive - timedelta(days=1)).isoformat(),
        "latest_data_date": latest.isoformat() if latest else None,
        "target_low": target_low,
        "target_high": target_high,
        "cv_unstable_pct": cv_unstable_pct,
        "bands": bands_now,
        "average": round(avg) if avg is not None else None,
        "gmi": gmi_percent(avg) if avg is not None else None,
        "avg_delta": avg_delta,
        "tir_pct": in_range if values else None,
        "tir_delta": tir_delta,
        "hour_bands": hour_band_shares(rows, target_low, target_high),
        "variability": current,
        "previous_variability": previous["period"],
        "cv_delta": cv_delta,
        "readings_n": len(values),
        "lows": low_episodes(rows),
    }


def _window_ending(latest: date | None, days: int) -> tuple[date, date]:
    end = latest or date.today()
    start = end - timedelta(days=days - 1)
    return start, end


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _circular_mean_minutes(values: list[float]) -> float | None:
    """Mean of clock times in minutes-past-midnight, handling midnight wrap."""
    if not values:
        return None
    sin_sum = sum(math.sin(v / 1440 * 2 * math.pi) for v in values)
    cos_sum = sum(math.cos(v / 1440 * 2 * math.pi) for v in values)
    angle = math.atan2(sin_sum / len(values), cos_sum / len(values))
    minutes = (angle / (2 * math.pi)) * 1440
    if minutes < 0:
        minutes += 1440
    return minutes


def _fmt_clock(minutes: float | None) -> str | None:
    if minutes is None:
        return None
    total = int(round(minutes)) % 1440
    return f"{total // 60:02d}:{total % 60:02d}"


def _is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def _is_snack_label(label: str | None, groups_json: str | None = None) -> bool:
    text = f"{label or ''} {groups_json or ''}".lower()
    return "snack" in text


def _is_walking(activity: str | None) -> bool:
    name = (activity or "").strip().lower()
    return name in {"walking", "walk", "hike", "hiking"} or "walk" in name


# Whoop exports have no step count; ~100 steps/min is a casual-walk estimate.
WALK_STEPS_PER_MIN = 100


def _date_range(start: date, end: date) -> list[str]:
    days: list[str] = []
    cur = start
    while cur <= end:
        days.append(cur.isoformat())
        cur += timedelta(days=1)
    return days


def latest_lifestyle_date(conn: sqlite3.Connection) -> date | None:
    row = conn.execute(
        """
        SELECT MAX(day) AS d FROM (
            SELECT substr(start, 1, 10) AS day FROM eating_occasions
            UNION ALL SELECT date FROM daily_nutrition WHERE source = 'cronometer'
            UNION ALL SELECT substr(onset, 1, 10) FROM sleep WHERE is_nap = 0
            UNION ALL SELECT substr(start, 1, 10) FROM workouts
            UNION ALL SELECT local_date FROM daily_physiology
        )
        """
    ).fetchone()
    return date.fromisoformat(row["d"]) if row and row["d"] else None


def lifestyle_summary(
    conn: sqlite3.Connection,
    *,
    days: int = 14,
    end: date | None = None,
    target_high: int = 150,
) -> dict[str, Any]:
    """Aggregate food / sleep / activity — one shared calendar window for all sections."""
    # Prefer the latest lifestyle timestamp so older imports still visualise; never past today.
    if end is None:
        latest = latest_lifestyle_date(conn)
        end = min(date.today(), latest) if latest else date.today()
    else:
        end = min(date.today(), end)
    start = end - timedelta(days=days - 1)
    day_list = _date_range(start, end)
    start_s = datetime.combine(start, datetime.min.time()).isoformat(timespec="seconds")
    end_s = datetime.combine(end + timedelta(days=1), datetime.min.time()).isoformat(timespec="seconds")

    # ----- Food aggregates -----
    occasions = conn.execute(
        "SELECT start, label, groups, carbs, protein, fat, kcal FROM eating_occasions "
        "WHERE start >= ? AND start < ?",
        (start_s, end_s),
    ).fetchall()

    daily_macros: dict[str, dict[str, float]] = defaultdict(
        lambda: {"carbs": 0.0, "protein": 0.0, "fat": 0.0, "kcal": 0.0}
    )
    for row in occasions:
        day = row["start"][:10]
        for key in ("carbs", "protein", "fat", "kcal"):
            if row[key] is not None:
                daily_macros[day][key] += float(row[key])

    for row in conn.execute(
        "SELECT date, nutrients FROM daily_nutrition WHERE source = 'cronometer' AND date >= ? AND date <= ?",
        (start.isoformat(), end.isoformat()),
    ):
        nutrients = json.loads(row["nutrients"])
        for key in ("carbs", "protein", "fat", "kcal"):
            if nutrients.get(key) is not None:
                daily_macros[row["date"]][key] = float(nutrients[key])

    macro_series = []
    for day in day_list:
        if day not in daily_macros:
            macro_series.append({"date": day, "carbs": None, "protein": None, "fat": None})
            continue
        m = daily_macros[day]
        macro_series.append(
            {
                "date": day,
                "carbs": round(m["carbs"], 1),
                "protein": round(m["protein"], 1),
                "fat": round(m["fat"], 1),
            }
        )

    logged_food_days = [d for d in day_list if d in daily_macros]
    tot_c = sum(daily_macros[d]["carbs"] for d in logged_food_days)
    tot_p = sum(daily_macros[d]["protein"] for d in logged_food_days)
    tot_f = sum(daily_macros[d]["fat"] for d in logged_food_days)
    # Energy share: carbs 4, protein 4, fat 9 kcal/g.
    c_kcal, p_kcal, f_kcal = tot_c * 4, tot_p * 4, tot_f * 9
    macro_kcal = c_kcal + p_kcal + f_kcal
    macro_pct = {
        "carbs": round(100 * c_kcal / macro_kcal, 1) if macro_kcal else None,
        "protein": round(100 * p_kcal / macro_kcal, 1) if macro_kcal else None,
        "fat": round(100 * f_kcal / macro_kcal, 1) if macro_kcal else None,
    }

    meals_per_day: dict[str, int] = defaultdict(int)
    snacks_per_day: dict[str, int] = defaultdict(int)
    for row in occasions:
        day = row["start"][:10]
        if _is_snack_label(row["label"], row["groups"]):
            snacks_per_day[day] += 1
        else:
            meals_per_day[day] += 1
    n_food_days = max(1, len(logged_food_days))
    food_insights = []
    avg_carbs = _avg([daily_macros[d]["carbs"] for d in logged_food_days if daily_macros[d]["carbs"]])
    avg_meals = round(sum(meals_per_day.values()) / n_food_days, 1) if logged_food_days else None
    avg_snacks = round(sum(snacks_per_day.values()) / n_food_days, 1) if logged_food_days else None
    if avg_carbs is not None:
        food_insights.append(f"About {avg_carbs:.0f} g carbs on logged days.")
    if avg_meals is not None:
        food_insights.append(f"Roughly {avg_meals} meals and {avg_snacks} snacks per logged day.")
    if macro_pct["carbs"] is not None:
        food_insights.append(
            f"Energy split ≈ {macro_pct['carbs']:.0f}% carbs, {macro_pct['protein']:.0f}% protein, {macro_pct['fat']:.0f}% fat."
        )
    if len(logged_food_days) < days:
        food_insights.append(f"Food logged on {len(logged_food_days)} of {days} days in this window.")

    # ----- Sleep aggregates -----
    sleeps = conn.execute(
        "SELECT onset, wake, asleep_min, performance_pct, efficiency_pct FROM sleep "
        "WHERE onset >= ? AND onset < ? AND is_nap = 0 ORDER BY onset",
        (start_s, end_s),
    ).fetchall()

    def sleep_bucket(rows: list) -> dict[str, Any]:
        hours = [(r["asleep_min"] / 60) for r in rows if r["asleep_min"] is not None]
        quality = [float(r["performance_pct"]) for r in rows if r["performance_pct"] is not None]
        if not quality:
            quality = [float(r["efficiency_pct"]) for r in rows if r["efficiency_pct"] is not None]
        onsets = []
        wakes = []
        for r in rows:
            onsets.append(datetime.fromisoformat(r["onset"]).hour * 60 + datetime.fromisoformat(r["onset"]).minute)
            if r["wake"]:
                wakes.append(datetime.fromisoformat(r["wake"]).hour * 60 + datetime.fromisoformat(r["wake"]).minute)
        onset_m = _circular_mean_minutes(onsets)
        wake_m = _circular_mean_minutes(wakes)
        return {
            "nights": len(rows),
            "avg_hours": _avg(hours),
            "avg_quality_pct": _avg(quality),
            "typical_bedtime": _fmt_clock(onset_m),
            "typical_wake": _fmt_clock(wake_m),
            "bedtime_minutes": round(onset_m) if onset_m is not None else None,
            "wake_minutes": round(wake_m) if wake_m is not None else None,
        }

    weekday_sleeps = [r for r in sleeps if not _is_weekend(datetime.fromisoformat(r["onset"]).date())]
    weekend_sleeps = [r for r in sleeps if _is_weekend(datetime.fromisoformat(r["onset"]).date())]
    sleep_all = sleep_bucket(list(sleeps))
    sleep_weekday = sleep_bucket(weekday_sleeps)
    sleep_weekend = sleep_bucket(weekend_sleeps)

    sleep_insights = []
    if sleep_all["avg_hours"] is not None:
        sleep_insights.append(f"Averaging {sleep_all['avg_hours']} h asleep.")
    if sleep_all["typical_bedtime"] and sleep_all["typical_wake"]:
        sleep_insights.append(f"Typical sleep window {sleep_all['typical_bedtime']}–{sleep_all['typical_wake']}.")
    if sleep_weekday["avg_hours"] is not None and sleep_weekend["avg_hours"] is not None:
        delta = round(sleep_weekend["avg_hours"] - sleep_weekday["avg_hours"], 1)
        if abs(delta) >= 0.4:
            sleep_insights.append(
                f"Weekends run {abs(delta)} h {'longer' if delta > 0 else 'shorter'} than weekdays."
            )
        else:
            sleep_insights.append("Weekday and weekend sleep length look similar.")
    if sleep_all["avg_quality_pct"] is not None:
        sleep_insights.append(f"Sleep performance around {sleep_all['avg_quality_pct']:.0f}%.")
    if sleep_all["nights"] < days:
        sleep_insights.append(f"Sleep logged on {sleep_all['nights']} of {days} nights.")

    # ----- Activity aggregates -----
    workouts = conn.execute(
        "SELECT start, activity, duration_min, strain, avg_hr, max_hr FROM workouts "
        "WHERE start >= ? AND start < ?",
        (start_s, end_s),
    ).fetchall()
    phys = conn.execute(
        "SELECT local_date, recovery_pct, hrv_ms, resting_hr, day_strain FROM daily_physiology "
        "WHERE local_date >= ? AND local_date <= ? ORDER BY local_date",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    phys_by_day = {r["local_date"]: r for r in phys}

    walks = [r for r in workouts if _is_walking(r["activity"])]
    training = [r for r in workouts if not _is_walking(r["activity"])]

    train_strain_by_day: dict[str, float] = defaultdict(float)
    train_min_by_day: dict[str, float] = defaultdict(float)
    walk_min_by_day: dict[str, float] = defaultdict(float)
    for r in training:
        day = r["start"][:10]
        if r["strain"] is not None:
            train_strain_by_day[day] += float(r["strain"])
        if r["duration_min"] is not None:
            train_min_by_day[day] += float(r["duration_min"])
    for r in walks:
        day = r["start"][:10]
        if r["duration_min"] is not None:
            walk_min_by_day[day] += float(r["duration_min"])

    daily_activity = []
    for day in day_list:
        walk_min = round(walk_min_by_day[day], 1) if day in walk_min_by_day else None
        est_steps = round(walk_min * WALK_STEPS_PER_MIN) if walk_min is not None else None
        strain = round(train_strain_by_day[day], 1) if day in train_strain_by_day else None
        phys_row = phys_by_day.get(day)
        day_strain = phys_row["day_strain"] if phys_row is not None else None
        # Prefer summed training strain; fall back to Whoop day strain only when there was training.
        intensity = strain
        if intensity is None and day in train_min_by_day and day_strain is not None:
            intensity = round(float(day_strain), 1)
        daily_activity.append(
            {
                "date": day,
                "training_strain": intensity,
                "training_min": round(train_min_by_day[day], 1) if day in train_min_by_day else None,
                "walk_min": walk_min,
                "est_steps": est_steps,
            }
        )

    training_days = {r["start"][:10] for r in training}
    walk_days = {r["start"][:10] for r in walks}
    daily_walk_mins = [walk_min_by_day[d] for d in day_list if d in walk_min_by_day]
    daily_est_steps = [m * WALK_STEPS_PER_MIN for m in daily_walk_mins]
    train_strains = [train_strain_by_day[d] for d in day_list if d in train_strain_by_day]

    activity = {
        "training_days": len(training_days),
        "training_day_pct": round(100 * len(training_days) / days, 1),
        "avg_training_strain": _avg(train_strains),
        "avg_training_min": _avg([float(r["duration_min"]) for r in training if r["duration_min"] is not None]),
        "avg_workout_hr": _avg([float(r["avg_hr"]) for r in training if r["avg_hr"] is not None]),
        "avg_recovery_pct": _avg([float(r["recovery_pct"]) for r in phys if r["recovery_pct"] is not None]),
        "avg_resting_hr": _avg([float(r["resting_hr"]) for r in phys if r["resting_hr"] is not None]),
        "avg_hrv_ms": _avg([float(r["hrv_ms"]) for r in phys if r["hrv_ms"] is not None]),
        "walk_days": len(walk_days),
        "avg_walk_min": _avg(daily_walk_mins),
        "avg_est_steps": round(sum(daily_est_steps) / len(daily_est_steps)) if daily_est_steps else None,
        "steps_estimated": True,
        "steps_per_walk_min": WALK_STEPS_PER_MIN,
        "daily": daily_activity,
        "by_type": [],
    }
    type_counts: dict[str, int] = defaultdict(int)
    for r in training:
        type_counts[r["activity"] or "Workout"] += 1
    activity["by_type"] = [
        {"activity": name, "count": count}
        for name, count in sorted(type_counts.items(), key=lambda item: -item[1])[:6]
    ]

    activity_insights = []
    activity_insights.append(
        f"Trained on {activity['training_days']} of {days} days ({activity['training_day_pct']:.0f}%) — walking excluded."
    )
    if activity["avg_training_strain"] is not None:
        activity_insights.append(f"Average training strain ~{activity['avg_training_strain']:.1f} on training days.")
    if activity["avg_walk_min"] is not None:
        steps_bit = (
            f" (~{activity['avg_est_steps']:,} est. steps)"
            if activity["avg_est_steps"] is not None
            else ""
        )
        activity_insights.append(f"Walking ~{activity['avg_walk_min']:.0f} min/day on walk days{steps_bit}.")
    if activity["avg_workout_hr"] is not None:
        activity_insights.append(f"Average training heart rate ~{activity['avg_workout_hr']:.0f} bpm.")
    if activity["avg_resting_hr"] is not None and activity["avg_hrv_ms"] is not None:
        activity_insights.append(
            f"Resting HR ~{activity['avg_resting_hr']:.0f} bpm · HRV ~{activity['avg_hrv_ms']:.0f} ms."
        )
    activity_insights.append(
        f"Whoop has no step export — steps are estimated at ~{WALK_STEPS_PER_MIN}/min of walking."
    )

    has_food = bool(logged_food_days)
    has_sleep = bool(sleeps)
    has_activity = bool(workouts) or bool(phys)

    return {
        "days": days,
        "start": start.isoformat(),
        "end": end.isoformat(),
        # Kept for older UI callers; all three sections share start/end.
        "food_start": start.isoformat(),
        "food_end": end.isoformat(),
        "whoop_start": start.isoformat(),
        "whoop_end": end.isoformat(),
        "target_high": target_high,
        "has_food": has_food,
        "has_sleep": has_sleep,
        "has_activity": has_activity,
        "food": {
            "daily_macros": macro_series,
            "daily_carbs": [{"date": d["date"], "carbs": d["carbs"]} for d in macro_series],
            "avg_carbs": avg_carbs,
            "macro_pct": macro_pct,
            "avg_meals_per_day": avg_meals,
            "avg_snacks_per_day": avg_snacks,
            "logged_days": len(logged_food_days),
            "insights": food_insights,
        },
        "sleep": {
            "overall": sleep_all,
            "weekday": sleep_weekday,
            "weekend": sleep_weekend,
            "insights": sleep_insights,
        },
        "activity": {**activity, "insights": activity_insights},
    }
