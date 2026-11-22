"""Coverage-aware context pack for the LLM coach."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from .. import analytics, db
from ..analytics import LOW, VERY_LOW

DEFAULT_COACH_DAYS = 7
ALLOWED_COACH_DAYS = (7, 14, 30)


def _slim_trends(trends: dict[str, Any]) -> dict[str, Any]:
    var = trends.get("variability") or {}
    period = var.get("period")
    hour_highlights = []
    for row in trends.get("hour_bands") or []:
        high = float(row.get("high_pct") or 0)
        low = float(row.get("low_pct") or 0)
        if high >= 35 or low >= 15:
            hour_highlights.append(
                {
                    "hour": row["hour"],
                    "high_pct": high,
                    "low_pct": low,
                    "in_range_pct": row.get("in_range_pct"),
                }
            )

    daily_cv = [
        {
            "date": d["date"],
            "cv_pct": d.get("cv_pct"),
            "spectrum": d.get("spectrum"),
            "average": d.get("average"),
            "n": d.get("n"),
        }
        for d in (var.get("daily") or [])
        if d.get("cv_pct") is not None
    ]
    daily_cv_sorted = sorted(daily_cv, key=lambda d: d["cv_pct"] or 0, reverse=True)
    notable_days = daily_cv_sorted[:3] + sorted(daily_cv, key=lambda d: d["cv_pct"] or 999)[:2]

    lows = trends.get("lows")
    low_count = lows if isinstance(lows, int) else len(lows or [])
    return {
        "start": trends["start"],
        "end": trends["end"],
        "days": trends["days"],
        "readings_n": trends.get("readings_n"),
        "average": trends.get("average"),
        "avg_delta": trends.get("avg_delta"),
        "gmi": trends.get("gmi"),
        "tir_pct": trends.get("tir_pct"),
        "tir_delta": trends.get("tir_delta"),
        "bands": trends.get("bands"),
        "cv": {
            "period": period,
            "within_day_cv_pct": var.get("within_day_cv_pct"),
            "day_to_day_sd": var.get("day_to_day_sd"),
            "unstable_days": var.get("unstable_days"),
            "days_with_cv": var.get("days_with_cv"),
            "cv_delta": trends.get("cv_delta"),
        },
        "notable_cv_days": notable_days[:5],
        "hour_risk_windows": hour_highlights[:8],
        "low_episode_count": low_count,
    }


def _slim_lifestyle(life: dict[str, Any]) -> dict[str, Any]:
    food = life.get("food") or {}
    sleep = life.get("sleep") or {}
    activity = life.get("activity") or {}
    daily_macros = food.get("daily_macros") or []
    high_carb_days = sorted(
        [d for d in daily_macros if d.get("carbs") is not None],
        key=lambda d: d["carbs"],
        reverse=True,
    )[:5]
    act_daily = activity.get("daily") or []
    train_days = [d for d in act_daily if d.get("training_strain") is not None][:8]
    walk_days = [d for d in act_daily if d.get("est_steps") is not None][:8]
    return {
        "start": life.get("start"),
        "end": life.get("end"),
        "has_food": life.get("has_food"),
        "has_sleep": life.get("has_sleep"),
        "has_activity": life.get("has_activity"),
        "food": {
            "logged_days": food.get("logged_days"),
            "avg_carbs": food.get("avg_carbs"),
            "macro_pct": food.get("macro_pct"),
            "avg_meals_per_day": food.get("avg_meals_per_day"),
            "avg_snacks_per_day": food.get("avg_snacks_per_day"),
            "highest_carb_days": high_carb_days,
            "insights": food.get("insights"),
        },
        "sleep": {
            "overall": sleep.get("overall"),
            "weekday": {
                "nights": (sleep.get("weekday") or {}).get("nights"),
                "avg_hours": (sleep.get("weekday") or {}).get("avg_hours"),
                "typical_bedtime": (sleep.get("weekday") or {}).get("typical_bedtime"),
                "typical_wake": (sleep.get("weekday") or {}).get("typical_wake"),
                "avg_quality_pct": (sleep.get("weekday") or {}).get("avg_quality_pct"),
            },
            "weekend": {
                "nights": (sleep.get("weekend") or {}).get("nights"),
                "avg_hours": (sleep.get("weekend") or {}).get("avg_hours"),
                "typical_bedtime": (sleep.get("weekend") or {}).get("typical_bedtime"),
                "typical_wake": (sleep.get("weekend") or {}).get("typical_wake"),
                "avg_quality_pct": (sleep.get("weekend") or {}).get("avg_quality_pct"),
            },
            "insights": sleep.get("insights"),
        },
        "activity": {
            "training_days": activity.get("training_days"),
            "training_day_pct": activity.get("training_day_pct"),
            "avg_training_strain": activity.get("avg_training_strain"),
            "avg_workout_hr": activity.get("avg_workout_hr"),
            "avg_resting_hr": activity.get("avg_resting_hr"),
            "avg_hrv_ms": activity.get("avg_hrv_ms"),
            "avg_recovery_pct": activity.get("avg_recovery_pct"),
            "walk_days": activity.get("walk_days"),
            "avg_walk_min": activity.get("avg_walk_min"),
            "avg_est_steps": activity.get("avg_est_steps"),
            "steps_estimated": activity.get("steps_estimated"),
            "training_day_examples": train_days,
            "walk_day_examples": walk_days,
            "by_type": activity.get("by_type"),
            "insights": activity.get("insights"),
        },
    }


def _collect_low_episodes(rows: list[sqlite3.Row], threshold: int = LOW, min_minutes: int = 15) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    spell_start: datetime | None = None
    spell_nadir = None
    counted = False
    for row in rows:
        ts = datetime.fromisoformat(row["ts"])
        value = float(row["mg_dl"])
        if value < threshold:
            if spell_start is None:
                spell_start, spell_nadir, counted = ts, value, False
            else:
                spell_nadir = min(spell_nadir, value) if spell_nadir is not None else value
            if not counted and (ts - spell_start) >= timedelta(minutes=min_minutes):
                counted = True
        else:
            if counted and spell_start is not None:
                episodes.append(
                    {
                        "start": spell_start.isoformat(timespec="minutes"),
                        "date": spell_start.date().isoformat(),
                        "nadir_mg_dl": round(spell_nadir) if spell_nadir is not None else None,
                        "threshold": threshold,
                        "very_low": spell_nadir is not None and spell_nadir < VERY_LOW,
                    }
                )
            spell_start, spell_nadir, counted = None, None, False
    if counted and spell_start is not None:
        episodes.append(
            {
                "start": spell_start.isoformat(timespec="minutes"),
                "date": spell_start.date().isoformat(),
                "nadir_mg_dl": round(spell_nadir) if spell_nadir is not None else None,
                "threshold": threshold,
                "very_low": spell_nadir is not None and spell_nadir < VERY_LOW,
            }
        )
    return episodes


def _overnight_samples(rows: list[sqlite3.Row], target_high: int) -> list[dict[str, Any]]:
    """Per-night 00:00–06:00 min/max for dawn / overnight pattern examples."""
    by_night: dict[str, list[float]] = {}
    for row in rows:
        ts = datetime.fromisoformat(row["ts"])
        if 0 <= ts.hour < 6:
            by_night.setdefault(ts.date().isoformat(), []).append(float(row["mg_dl"]))
    samples = []
    for day, values in sorted(by_night.items()):
        if len(values) < 4:
            continue
        samples.append(
            {
                "date": day,
                "min_mg_dl": round(min(values)),
                "max_mg_dl": round(max(values)),
                "avg_mg_dl": round(sum(values) / len(values)),
                "above_target": round(max(values)) > target_high,
                "below_70": round(min(values)) < LOW,
            }
        )
    # Prefer nights with clear movement.
    samples.sort(key=lambda s: abs(s["max_mg_dl"] - s["min_mg_dl"]), reverse=True)
    return samples[:6]


def _high_peaks(rows: list[sqlite3.Row], threshold: int = 180) -> list[dict[str, Any]]:
    peaks: list[dict[str, Any]] = []
    in_high = False
    peak_ts = None
    peak_val = None
    for row in rows:
        ts = datetime.fromisoformat(row["ts"])
        value = float(row["mg_dl"])
        if value > threshold:
            if not in_high or (peak_val is not None and value > peak_val):
                peak_ts, peak_val = ts, value
            in_high = True
        elif in_high:
            if peak_ts is not None and peak_val is not None:
                peaks.append(
                    {
                        "t": peak_ts.isoformat(timespec="minutes"),
                        "date": peak_ts.date().isoformat(),
                        "peak_mg_dl": round(peak_val),
                    }
                )
            in_high, peak_ts, peak_val = False, None, None
    if in_high and peak_ts is not None and peak_val is not None:
        peaks.append(
            {
                "t": peak_ts.isoformat(timespec="minutes"),
                "date": peak_ts.date().isoformat(),
                "peak_mg_dl": round(peak_val),
            }
        )
    peaks.sort(key=lambda p: p["peak_mg_dl"], reverse=True)
    return peaks[:8]


def _meal_linked_examples(
    conn: sqlite3.Connection,
    start: date,
    end: date,
    target_high: int,
) -> list[dict[str, Any]]:
    start_s = datetime.combine(start, datetime.min.time()).isoformat(timespec="seconds")
    end_s = datetime.combine(end + timedelta(days=1), datetime.min.time()).isoformat(timespec="seconds")
    meals = conn.execute(
        "SELECT start, label, carbs FROM eating_occasions WHERE start >= ? AND start < ? ORDER BY start",
        (start_s, end_s),
    ).fetchall()
    examples = []
    for meal in meals[:40]:
        meal_ts = datetime.fromisoformat(meal["start"])
        window_end = meal_ts + timedelta(hours=3)
        rows = analytics.stat_readings(analytics.glucose_between(conn, meal_ts, window_end))
        if len(rows) < 3:
            continue
        values = [float(r["mg_dl"]) for r in rows]
        peak = max(values)
        peak_row = max(rows, key=lambda r: float(r["mg_dl"]))
        if peak < target_high + 20:
            continue
        examples.append(
            {
                "meal_t": meal_ts.isoformat(timespec="minutes"),
                "label": meal["label"] or "Meal",
                "carbs": meal["carbs"],
                "pre_mg_dl": round(values[0]),
                "peak_mg_dl": round(peak),
                "peak_t": peak_row["ts"][:16],
                "rise_mg_dl": round(peak - values[0]),
            }
        )
    examples.sort(key=lambda e: e["rise_mg_dl"], reverse=True)
    return examples[:6]


def _workout_linked_examples(
    conn: sqlite3.Connection,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    start_s = datetime.combine(start, datetime.min.time()).isoformat(timespec="seconds")
    end_s = datetime.combine(end + timedelta(days=1), datetime.min.time()).isoformat(timespec="seconds")
    workouts = conn.execute(
        "SELECT start, end, activity, duration_min, strain FROM workouts "
        "WHERE start >= ? AND start < ? ORDER BY start",
        (start_s, end_s),
    ).fetchall()
    examples = []
    for w in workouts[:30]:
        w_start = datetime.fromisoformat(w["start"])
        w_end = datetime.fromisoformat(w["end"]) if w["end"] else w_start + timedelta(minutes=float(w["duration_min"] or 45))
        pre = analytics.stat_readings(analytics.glucose_between(conn, w_start - timedelta(minutes=30), w_start))
        during = analytics.stat_readings(analytics.glucose_between(conn, w_start, w_end + timedelta(hours=2)))
        if len(pre) < 1 or len(during) < 2:
            continue
        pre_v = round(float(pre[-1]["mg_dl"]))
        min_after = round(min(float(r["mg_dl"]) for r in during))
        max_after = round(max(float(r["mg_dl"]) for r in during))
        examples.append(
            {
                "t": w_start.isoformat(timespec="minutes"),
                "activity": w["activity"],
                "duration_min": w["duration_min"],
                "strain": w["strain"],
                "pre_mg_dl": pre_v,
                "min_during_or_2h_mg_dl": min_after,
                "max_during_or_2h_mg_dl": max_after,
                "delta_to_min": min_after - pre_v,
            }
        )
    examples.sort(key=lambda e: abs(e["delta_to_min"]), reverse=True)
    return examples[:6]


def _build_examples(
    conn: sqlite3.Connection,
    start: date,
    end: date,
    target_high: int,
) -> dict[str, Any]:
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time())
    rows = analytics.stat_readings(analytics.glucose_between(conn, start_dt, end_dt))
    low_eps = _collect_low_episodes(rows)
    return {
        "low_episodes": low_eps[:8],
        "very_low_episode_count": sum(1 for e in low_eps if e.get("very_low")),
        "high_peaks": _high_peaks(rows, threshold=max(180, target_high))[:8],
        "overnight_windows": _overnight_samples(rows, target_high),
        "post_meal_spikes": _meal_linked_examples(conn, start, end, target_high),
        "exercise_glucose_examples": _workout_linked_examples(conn, start, end),
        "instruction": (
            "Cite these concrete episodes/dates/times in insight and evidence.days. "
            "Do not invent episodes that are not listed here."
        ),
    }


def build_context_pack(
    conn: sqlite3.Connection,
    *,
    days: int = DEFAULT_COACH_DAYS,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compact analytics + coverage + concrete episode examples for the coach LLM."""
    if days not in ALLOWED_COACH_DAYS:
        days = DEFAULT_COACH_DAYS
    settings = settings or db.get_settings(conn)
    today = date.today()
    latest_glucose = analytics.latest_glucose_date(conn)
    latest_lifestyle = analytics.latest_lifestyle_date(conn)
    candidates = [d for d in (latest_glucose, latest_lifestyle) if d is not None]
    end = min(today, max(candidates)) if candidates else today
    start = end - timedelta(days=days - 1)

    trends = analytics.trends_summary(
        conn,
        days=days,
        end=end,
        target_low=settings["target_low"],
        target_high=settings["target_high"],
        cv_unstable_pct=float(settings["cv_unstable_pct"]),
    )
    lifestyle = analytics.lifestyle_summary(
        conn,
        days=days,
        end=end,
        target_high=settings["target_high"],
    )

    food = lifestyle.get("food") or {}
    sleep = (lifestyle.get("sleep") or {}).get("overall") or {}
    activity = lifestyle.get("activity") or {}

    coverage = {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "days_requested": days,
        "today": today.isoformat(),
        "stale": end < today,
        "days_behind_today": (today - end).days if end < today else 0,
        "latest_glucose_date": latest_glucose.isoformat() if latest_glucose else None,
        "latest_lifestyle_date": latest_lifestyle.isoformat() if latest_lifestyle else None,
        "glucose": {
            "readings_n": trends.get("readings_n") or 0,
            "has_enough_for_cv": bool((trends.get("variability") or {}).get("period")),
            "days_with_cv": (trends.get("variability") or {}).get("days_with_cv") or 0,
            "sparse": (trends.get("readings_n") or 0) < 32,
        },
        "food": {
            "available": bool(lifestyle.get("has_food")),
            "logged_days": food.get("logged_days") or 0,
            "coverage_pct": round(100 * (food.get("logged_days") or 0) / days, 1),
        },
        "sleep": {
            "available": bool(lifestyle.get("has_sleep")),
            "nights": sleep.get("nights") or 0,
            "coverage_pct": round(100 * (sleep.get("nights") or 0) / days, 1),
        },
        "activity": {
            "available": bool(lifestyle.get("has_activity")),
            "training_days": activity.get("training_days") or 0,
            "walk_days": activity.get("walk_days") or 0,
            "steps_are_estimated": bool(activity.get("steps_estimated")),
        },
    }

    return {
        "profile": {
            "diabetes_type": settings.get("diabetes_type"),
            "target_low": settings["target_low"],
            "target_high": settings["target_high"],
            "timezone": settings.get("timezone"),
            "rapid_insulin_name": settings.get("rapid_insulin_name") or None,
            "long_insulin_name": settings.get("long_insulin_name") or None,
            "carb_ratio": settings.get("carb_ratio"),
            "correction_factor": settings.get("correction_factor"),
            "cv_unstable_pct": settings.get("cv_unstable_pct"),
        },
        "coach_brief": (settings.get("coach_brief") or "").strip(),
        "coverage": coverage,
        "trends": _slim_trends(trends),
        "lifestyle": _slim_lifestyle(lifestyle),
        "examples": _build_examples(conn, start, end, settings["target_high"]),
    }


def glucose_reading_count(pack: dict[str, Any]) -> int:
    return int(((pack.get("coverage") or {}).get("glucose") or {}).get("readings_n") or 0)


# Match rapid boluses near typical meal times. Day-to-day timing often drifts by 1–2.5h.
_MEAL_INSULIN_MATCH_MIN = 150
_BOLUS_CLUSTER_GAP_MIN = 30


def _schedule_for_day(settings: dict[str, Any], day: date) -> dict[str, Any]:
    schedule = settings.get("meal_schedule") or db.DEFAULT_SETTINGS["meal_schedule"]
    kind = "weekend" if day.weekday() >= 5 else "weekday"
    block = schedule.get(kind) or schedule.get("weekday") or {}
    return {"kind": kind, **block}


def _cluster_rapid_boluses(doses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge rapid shots within a short gap into one bolus event (largest shot marks the time)."""
    rapid = sorted(
        (
            {
                "t": datetime.fromisoformat(str(d["t"])),
                "units": float(d["units"] or 0),
            }
            for d in doses
            if (d.get("kind") or "rapid") == "rapid" and d.get("units") is not None
        ),
        key=lambda d: d["t"],
    )
    if not rapid:
        return []

    clusters: list[dict[str, Any]] = []
    cur = {
        "units": rapid[0]["units"],
        "shots": 1,
        "_peak": rapid[0]["units"],
        "_peak_t": rapid[0]["t"],
        "_last_t": rapid[0]["t"],
    }
    for dose in rapid[1:]:
        gap = (dose["t"] - cur["_last_t"]).total_seconds() / 60
        if gap <= _BOLUS_CLUSTER_GAP_MIN:
            cur["units"] = round(cur["units"] + dose["units"], 1)
            cur["shots"] += 1
            cur["_last_t"] = dose["t"]
            if dose["units"] >= cur["_peak"]:
                cur["_peak"] = dose["units"]
                cur["_peak_t"] = dose["t"]
        else:
            clusters.append(
                {
                    "t": cur["_peak_t"],
                    "units": round(cur["units"], 1),
                    "shots": cur["shots"],
                }
            )
            cur = {
                "units": dose["units"],
                "shots": 1,
                "_peak": dose["units"],
                "_peak_t": dose["t"],
                "_last_t": dose["t"],
            }
    clusters.append(
        {
            "t": cur["_peak_t"],
            "units": round(cur["units"], 1),
            "shots": cur["shots"],
        }
    )
    return clusters


def _align_schedule_with_insulin(
    day: date,
    schedule_meals: list[dict[str, Any]],
    insulin_rows: list[Any],
) -> tuple[list[dict[str, Any]], int]:
    """
    Shift typical meal times toward nearby rapid boluses for this day.
    Larger boluses win when multiple candidates sit near the same slot.
    """
    normalized = []
    for r in insulin_rows:
        if hasattr(r, "keys"):
            keys = r.keys()
            ts = r["ts"] if "ts" in keys else r["t"]
            normalized.append({"t": ts, "units": r["units"], "kind": r["kind"]})
        else:
            normalized.append(r)
    anchors: list[dict[str, Any]] = []
    for m in schedule_meals:
        hh, mm = map(int, str(m.get("time") or "12:00").split(":"))
        anchors.append(
            {
                "label": m.get("label") or "Meal",
                "scheduled_t": datetime.combine(day, datetime.min.time()).replace(hour=hh, minute=mm),
            }
        )
    if not anchors:
        return [], 0

    boluses = _cluster_rapid_boluses(normalized)
    matched: dict[int, dict[str, Any]] = {}
    if boluses:
        candidates: list[tuple[float, int, int]] = []
        for mi, anchor in enumerate(anchors):
            for bi, bolus in enumerate(boluses):
                delta = abs((bolus["t"] - anchor["scheduled_t"]).total_seconds()) / 60
                if delta > _MEAL_INSULIN_MATCH_MIN:
                    continue
                # Prefer bigger boluses that are closer to the typical slot
                score = float(bolus["units"]) * 10 - delta / 6
                candidates.append((score, mi, bi))
        candidates.sort(reverse=True)

        used_meals: set[int] = set()
        used_boluses: set[int] = set()
        for _score, mi, bi in candidates:
            if mi in used_meals or bi in used_boluses:
                continue
            used_meals.add(mi)
            used_boluses.add(bi)
            bolus = boluses[bi]
            matched[mi] = {
                "bolus_t": bolus["t"],
                "units": bolus["units"],
                "shots": bolus["shots"],
                "delta_min": round((bolus["t"] - anchors[mi]["scheduled_t"]).total_seconds() / 60),
            }

    meals: list[dict[str, Any]] = []
    aligned_n = 0
    prev_t: datetime | None = None
    for mi, anchor in enumerate(anchors):
        hit = matched.get(mi)
        scheduled_iso = anchor["scheduled_t"].isoformat(timespec="minutes")
        if hit:
            meal_t = hit["bolus_t"]
            # Keep chronological order if a late breakfast match would land after lunch
            if prev_t is not None and meal_t <= prev_t:
                meal_t = prev_t + timedelta(minutes=20)
            aligned_n += 1
            meals.append(
                {
                    "t": meal_t.isoformat(timespec="minutes"),
                    "label": anchor["label"],
                    "carbs": None,
                    "protein": None,
                    "fat": None,
                    "kcal": None,
                    "source": "estimated",
                    "scheduled_t": scheduled_iso,
                    "insulin_units": hit["units"],
                    "insulin_shots": hit["shots"],
                    "shift_min": hit["delta_min"],
                }
            )
            prev_t = meal_t
        else:
            meal_t = anchor["scheduled_t"]
            if prev_t is not None and meal_t <= prev_t:
                meal_t = prev_t + timedelta(minutes=45)
            meals.append(
                {
                    "t": meal_t.isoformat(timespec="minutes"),
                    "label": anchor["label"],
                    "carbs": None,
                    "protein": None,
                    "fat": None,
                    "kcal": None,
                    "source": "scheduled",
                    "scheduled_t": scheduled_iso,
                    "insulin_units": None,
                    "insulin_shots": None,
                    "shift_min": None,
                }
            )
            prev_t = meal_t
    return meals, aligned_n


def _resolve_day_meals(
    conn: sqlite3.Connection,
    day: date,
    settings: dict[str, Any],
) -> dict[str, Any]:
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    logged = conn.execute(
        "SELECT start, label, carbs, protein, fat, kcal FROM eating_occasions "
        "WHERE start >= ? AND start < ? ORDER BY start",
        (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
    ).fetchall()
    schedule = _schedule_for_day(settings, day)
    if logged:
        meals = [
            {
                "t": r["start"][:16],
                "label": r["label"] or "Meal",
                "carbs": r["carbs"],
                "protein": r["protein"],
                "fat": r["fat"],
                "kcal": r["kcal"],
                "source": "logged",
            }
            for r in logged
        ]
        return {
            "source": "logged",
            "schedule_kind": schedule.get("kind"),
            "meals": meals,
            "note": "Using Cronometer/logged eating occasions for this day.",
        }

    schedule_meals = list(schedule.get("meals") or [])
    insulin_rows = analytics.insulin_between(conn, start, end)
    meals, aligned_n = _align_schedule_with_insulin(day, schedule_meals, insulin_rows)

    if aligned_n:
        return {
            "source": "estimated",
            "schedule_kind": schedule.get("kind"),
            "meals": meals,
            "aligned_with_insulin": aligned_n,
            "note": (
                f"No food log — estimated meal times from your {schedule.get('kind')} "
                f"schedule, shifted using {aligned_n} of {len(meals)} rapid insulin "
                f"bolus(es) that day (timing varies day to day)."
            ),
        }

    return {
        "source": "scheduled",
        "schedule_kind": schedule.get("kind"),
        "meals": meals,
        "aligned_with_insulin": 0,
        "note": (
            f"No food log for this day — using typical {schedule.get('kind')} "
            f"main-meal schedule from Settings ({len(meals)} meals). "
            "No nearby rapid boluses to refine timing."
        ),
    }


def _assess_meal_window(pre: int, peak: int, rise: int, target_high: int) -> str:
    """How to interpret a meal window — used to stop blaming dinner for a pre-existing high."""
    if pre < LOW:
        return "started_low"
    if pre > target_high:
        return "started_high"
    if peak <= target_high and rise <= 55:
        return "well_managed"
    if peak > target_high and rise >= 40:
        return "post_meal_high"
    if peak > target_high:
        return "mild_overshoot"
    return "moderate_rise"


def _meal_glucose_windows(
    conn: sqlite3.Connection,
    meals: list[dict[str, Any]],
    target_high: int,
) -> list[dict[str, Any]]:
    windows = []
    for meal in meals:
        meal_ts = datetime.fromisoformat(meal["t"])
        lookback = analytics.stat_readings(
            analytics.glucose_between(conn, meal_ts - timedelta(hours=3), meal_ts)
        )
        pre_rows = analytics.stat_readings(
            analytics.glucose_between(conn, meal_ts - timedelta(minutes=20), meal_ts)
        )
        post_rows = analytics.stat_readings(
            analytics.glucose_between(conn, meal_ts, meal_ts + timedelta(hours=3))
        )
        if len(post_rows) < 2:
            continue
        post_vals = [float(r["mg_dl"]) for r in post_rows]
        peak = max(post_vals)
        peak_row = max(post_rows, key=lambda r: float(r["mg_dl"]))
        pre = round(float(pre_rows[-1]["mg_dl"])) if pre_rows else round(post_vals[0])
        at_2h = None
        for r in post_rows:
            ts = datetime.fromisoformat(r["ts"])
            if abs((ts - meal_ts).total_seconds() - 7200) <= 20 * 60:
                at_2h = round(float(r["mg_dl"]))
                break
        rise = round(peak - pre)
        lookback_vals = [float(r["mg_dl"]) for r in lookback]
        prior_min = round(min(lookback_vals)) if lookback_vals else None
        prior_max = round(max(lookback_vals)) if lookback_vals else None
        windows.append(
            {
                "meal_t": meal["t"],
                "label": meal.get("label"),
                "source": meal.get("source"),
                "scheduled_t": meal.get("scheduled_t"),
                "insulin_units": meal.get("insulin_units"),
                "carbs": meal.get("carbs"),
                "pre_mg_dl": pre,
                "peak_mg_dl": round(peak),
                "peak_t": peak_row["ts"][:16],
                "rise_mg_dl": rise,
                "at_2h_mg_dl": at_2h,
                "above_target": round(peak) > target_high,
                "assessment": _assess_meal_window(pre, round(peak), rise, target_high),
                "hours_before": {
                    "min_mg_dl": prior_min,
                    "max_mg_dl": prior_max,
                    "had_near_low": prior_min is not None and prior_min < 80,
                    "had_high": prior_max is not None and prior_max > target_high,
                },
            }
        )
    return windows


def _soft_low_spells(rows: list[sqlite3.Row], soft_threshold: int = 80, min_minutes: int = 20) -> list[dict[str, Any]]:
    """Dips under 80 that may not count as formal hypos (<70) but still drive corrections/rebounds."""
    spells: list[dict[str, Any]] = []
    start: datetime | None = None
    nadir = None
    last: datetime | None = None
    for row in rows:
        ts = datetime.fromisoformat(row["ts"])
        value = float(row["mg_dl"])
        if value < soft_threshold:
            if start is None:
                start, nadir = ts, value
            else:
                nadir = min(nadir, value) if nadir is not None else value
            last = ts
        else:
            if start is not None and last is not None and (last - start) >= timedelta(minutes=min_minutes):
                # Skip if already a formal hypo (<70 for 15+ min) — those are in low_episodes
                if nadir is None or nadir >= LOW:
                    spells.append(
                        {
                            "start": start.isoformat(timespec="minutes"),
                            "end": last.isoformat(timespec="minutes"),
                            "nadir_mg_dl": round(nadir) if nadir is not None else None,
                            "note": "near-low (under 80), not a formal hypo under 70",
                        }
                    )
            start, nadir, last = None, None, None
    if start is not None and last is not None and (last - start) >= timedelta(minutes=min_minutes):
        if nadir is None or nadir >= LOW:
            spells.append(
                {
                    "start": start.isoformat(timespec="minutes"),
                    "end": last.isoformat(timespec="minutes"),
                    "nadir_mg_dl": round(nadir) if nadir is not None else None,
                    "note": "near-low (under 80), not a formal hypo under 70",
                }
            )
    return spells[:8]


def _glucose_at(rows: list[sqlite3.Row], when: datetime, window_min: int = 20) -> int | None:
    best = None
    best_delta = None
    for row in rows:
        ts = datetime.fromisoformat(row["ts"])
        delta = abs((ts - when).total_seconds())
        if delta <= window_min * 60 and (best_delta is None or delta < best_delta):
            best_delta = delta
            best = round(float(row["mg_dl"]))
    return best


def _insulin_with_glucose(
    insulin: list[dict[str, Any]],
    rows: list[sqlite3.Row],
) -> list[dict[str, Any]]:
    out = []
    for d in insulin:
        ts = datetime.fromisoformat(d["t"])
        g = _glucose_at(rows, ts)
        out.append(
            {
                "t": d["t"][:16],
                "units": d.get("units"),
                "kind": d.get("kind"),
                "glucose_mg_dl": g,
                "bolus_while_low": bool(
                    d.get("kind") == "rapid" and g is not None and g < 90 and (d.get("units") or 0) >= 2
                ),
            }
        )
    return out


def _event_arcs(
    rows: list[sqlite3.Row],
    insulin_ctx: list[dict[str, Any]],
    target_high: int,
) -> list[dict[str, Any]]:
    """Causal chains the coach must prefer over isolated meal cards."""
    arcs: list[dict[str, Any]] = []
    for dose in insulin_ctx:
        if not dose.get("bolus_while_low"):
            continue
        arcs.append(
            {
                "kind": "bolus_while_low",
                "t": dose["t"],
                "units": dose["units"],
                "glucose_mg_dl": dose["glucose_mg_dl"],
                "summary": (
                    f"Rapid {dose['units']} u at {dose['t'][11:16]} while glucose was "
                    f"{dose['glucose_mg_dl']} mg/dL — hypo risk / likely later correction."
                ),
            }
        )

    # Local trough < 90 followed within 4h by a peak above target (rebound / overcorrection pattern)
    vals = [(datetime.fromisoformat(r["ts"]), float(r["mg_dl"])) for r in rows]
    for i, (ts, v) in enumerate(vals):
        if v >= 90:
            continue
        # local min in ±20 min
        nearby = [vv for tt, vv in vals if abs((tt - ts).total_seconds()) <= 20 * 60]
        if nearby and v > min(nearby) + 0.5:
            continue
        later = [(tt, vv) for tt, vv in vals if 15 * 60 <= (tt - ts).total_seconds() <= 4 * 3600]
        if not later:
            continue
        peak_t, peak_v = max(later, key=lambda x: x[1])
        if peak_v <= max(target_high, 180):
            continue
        arcs.append(
            {
                "kind": "low_then_high",
                "trough_t": ts.isoformat(timespec="minutes"),
                "trough_mg_dl": round(v),
                "peak_t": peak_t.isoformat(timespec="minutes"),
                "peak_mg_dl": round(peak_v),
                "summary": (
                    f"Glucose near {round(v)} mg/dL at {ts.strftime('%H:%M')}, then rose to "
                    f"{round(peak_v)} mg/dL by {peak_t.strftime('%H:%M')} — treat as "
                    f"correction/rebound chain, not as a meal failure if the next meal started high."
                ),
            }
        )

    # Dedupe low_then_high that share the same peak hour
    seen_peaks: set[str] = set()
    deduped = []
    for arc in arcs:
        if arc["kind"] == "low_then_high":
            key = arc["peak_t"][:13]
            if key in seen_peaks:
                continue
            seen_peaks.add(key)
        deduped.append(arc)
    return deduped[:8]


def build_day_context_pack(
    conn: sqlite3.Connection,
    day: date,
    *,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Context for coaching a single calendar day (full-day, not meal-only)."""
    settings = settings or db.get_settings(conn)
    day_summary = analytics.day_summary(
        conn,
        day,
        settings["target_low"],
        settings["target_high"],
        cv_unstable_pct=float(settings["cv_unstable_pct"]),
    )
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    rows = analytics.stat_readings(analytics.glucose_between(conn, start, end))
    meals_info = _resolve_day_meals(conn, day, settings)
    meal_windows = _meal_glucose_windows(conn, meals_info["meals"], settings["target_high"])

    sleep = conn.execute(
        "SELECT onset, wake, asleep_min, performance_pct FROM sleep "
        "WHERE is_nap = 0 AND onset >= ? AND onset < ?",
        ((start - timedelta(hours=12)).isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
    ).fetchall()
    sleep_rows = []
    for r in sleep:
        sleep_rows.append(
            {
                "onset": r["onset"][:16],
                "wake": (r["wake"] or "")[:16] or None,
                "hours": round(r["asleep_min"] / 60, 1) if r["asleep_min"] is not None else None,
                "performance_pct": r["performance_pct"],
            }
        )

    workouts = day_summary.get("workouts") or []
    insulin = day_summary.get("insulin") or []
    insulin_ctx = _insulin_with_glucose(insulin, rows)
    soft_lows = _soft_low_spells(rows)
    arcs = _event_arcs(rows, insulin_ctx, settings["target_high"])

    coverage = {
        "day": day.isoformat(),
        "weekday": day.strftime("%A"),
        "is_weekend": day.weekday() >= 5,
        "glucose_readings_n": len(rows),
        "sparse": len(rows) < 16,
        "meals_source": meals_info["source"],
        "has_logged_meals": meals_info["source"] == "logged",
        "meals_aligned_with_insulin": int(meals_info.get("aligned_with_insulin") or 0),
        "has_sleep": bool(sleep_rows),
        "has_workouts": bool(workouts),
        "has_insulin": bool(insulin),
        "has_event_arcs": bool(arcs),
        "well_managed_meals": sum(1 for w in meal_windows if w.get("assessment") == "well_managed"),
        "problem_meals": sum(1 for w in meal_windows if w.get("assessment") == "post_meal_high"),
    }

    examples = {
        "low_episodes": _collect_low_episodes(rows)[:8],
        "soft_lows": soft_lows,
        "high_peaks": _high_peaks(rows, threshold=max(180, settings["target_high"]))[:8],
        "overnight_windows": _overnight_samples(rows, settings["target_high"]),
        "meal_glucose_windows": meal_windows,
        "insulin_with_glucose": insulin_ctx,
        "event_arcs": arcs,
        "instruction": (
            "Whole-day review. Prefer event_arcs and safety (lows, bolus_while_low, rebound highs) "
            "over per-meal report cards. Only critique meals with assessment=post_meal_high. "
            "If assessment=started_high, the high predates the meal — explain the prior arc. "
            "If assessment=well_managed, do not invent improvement tries for that meal. "
            "Cite exact times and mg/dL from these examples only."
        ),
    }

    return {
        "mode": "day",
        "day": day.isoformat(),
        "profile": {
            "diabetes_type": settings.get("diabetes_type"),
            "target_low": settings["target_low"],
            "target_high": settings["target_high"],
            "timezone": settings.get("timezone"),
            "rapid_insulin_name": settings.get("rapid_insulin_name") or None,
            "long_insulin_name": settings.get("long_insulin_name") or None,
            "carb_ratio": settings.get("carb_ratio"),
            "correction_factor": settings.get("correction_factor"),
            "cv_unstable_pct": settings.get("cv_unstable_pct"),
        },
        "coach_brief": (settings.get("coach_brief") or "").strip(),
        "coverage": coverage,
        "day_summary": {
            "average": day_summary.get("average"),
            "min": day_summary.get("min"),
            "max": day_summary.get("max"),
            "bands": day_summary.get("bands"),
            "variability": day_summary.get("variability"),
            "low_episode_count": day_summary.get("lows"),
            "hours_above_target": day_summary.get("hours_above_target"),
            "insulin_totals": day_summary.get("insulin_totals"),
            "insulin": insulin_ctx,
            "workouts": [
                {
                    "t": w["t"][:16],
                    "activity": w.get("activity"),
                    "duration_min": w.get("duration_min"),
                }
                for w in workouts[:8]
            ],
        },
        "meals": meals_info,
        "sleep": sleep_rows,
        "examples": examples,
    }


def list_glucose_days(conn: sqlite3.Connection, *, limit: int = 60) -> list[str]:
    rows = conn.execute(
        """
        SELECT day FROM (
            SELECT substr(ts, 1, 10) AS day FROM glucose GROUP BY 1
        ) ORDER BY day DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [r["day"] for r in rows]
