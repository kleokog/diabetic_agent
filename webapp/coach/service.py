"""Validate, rank, persist, and load coach findings."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from typing import Any

from .. import db
from . import context, llm

SECTIONS = {"safety", "glucose", "food", "sleep", "activity", "insulin"}
CONFIDENCES = {"high", "medium", "low"}
DATA_KEYS = {"glucose", "food", "sleep", "activity", "insulin"}
CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}


class CoachError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 50.0
    return max(0.0, min(100.0, score))


def _as_str(value: Any, limit: int = 500) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _coverage_weak_for(data_used: list[str], coverage: dict[str, Any]) -> bool:
    # Day packs use flat coverage; period packs nest under glucose/food/sleep/activity.
    if "day" in coverage:
        for key in data_used:
            if key == "glucose" and (coverage.get("sparse") or (coverage.get("glucose_readings_n") or 0) < 16):
                return True
            if key == "food" and not coverage.get("has_logged_meals"):
                return True
            if key == "sleep" and not coverage.get("has_sleep"):
                return True
            if key == "activity" and not coverage.get("has_workouts"):
                return True
        return False

    glucose = coverage.get("glucose") or {}
    food = coverage.get("food") or {}
    sleep = coverage.get("sleep") or {}
    activity = coverage.get("activity") or {}
    for key in data_used:
        if key == "glucose" and (glucose.get("sparse") or (glucose.get("readings_n") or 0) < 32):
            return True
        if key == "food" and (not food.get("available") or (food.get("logged_days") or 0) < 3):
            return True
        if key == "sleep" and (not sleep.get("available") or (sleep.get("nights") or 0) < 3):
            return True
        if key == "activity" and not activity.get("available"):
            return True
    return False


def _floor_confidence(confidence: str) -> str:
    if confidence == "high":
        return "medium"
    if confidence == "medium":
        return "low"
    return "low"


def validate_findings(
    raw: list[dict[str, Any]],
    *,
    coverage: dict[str, Any],
) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = _as_str(item.get("title"), 120)
        insight = _as_str(item.get("insight"), 800)
        if not title or not insight:
            continue
        section = _as_str(item.get("section"), 32).lower()
        if section not in SECTIONS:
            section = "glucose"
        confidence = _as_str(item.get("confidence"), 16).lower()
        if confidence not in CONFIDENCES:
            confidence = "medium"
        data_used_raw = item.get("data_used") or []
        if not isinstance(data_used_raw, list):
            data_used_raw = []
        data_used = [str(x) for x in data_used_raw if str(x) in DATA_KEYS]
        if not data_used:
            data_used = ["glucose"]
        if _coverage_weak_for(data_used, coverage):
            confidence = _floor_confidence(confidence)

        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        metrics = evidence.get("metrics") if isinstance(evidence.get("metrics"), list) else []
        days = evidence.get("days") if isinstance(evidence.get("days"), list) else []
        cleaned.append(
            {
                "section": section,
                "title": title,
                "insight": insight,
                "why_it_matters": _as_str(item.get("why_it_matters"), 600) or None,
                "try_text": _as_str(item.get("try_text"), 900) or None,
                "confidence": confidence,
                "score": _clamp_score(item.get("score")),
                "evidence": {
                    "metrics": [str(m)[:80] for m in metrics[:12]],
                    "days": [str(d)[:10] for d in days[:14]],
                    "notes": _as_str(evidence.get("notes"), 400),
                },
                "data_used": data_used,
            }
        )

    cleaned.sort(
        key=lambda f: (
            0 if f["section"] == "safety" else 1,
            -f["score"],
            -CONFIDENCE_RANK.get(f["confidence"], 0),
        )
    )
    return cleaned[:8]


def _row_to_finding(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "period_start": row["period_start"],
        "period_end": row["period_end"],
        "section": row["section"],
        "title": row["title"],
        "insight": row["insight"],
        "why_it_matters": row["why_it_matters"],
        "try_text": row["try_text"],
        "evidence": json.loads(row["evidence"] or "{}"),
        "confidence": row["confidence"],
        "score": row["score"],
        "data_used": json.loads(row["data_used"] or "[]"),
        "status": row["status"],
        "prompt_version": row["prompt_version"],
        "origin": row["origin"],
    }


def list_active_findings(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Period (multi-day) findings only — day reviews use origin llm_day."""
    rows = conn.execute(
        "SELECT * FROM insights WHERE status = 'new' AND origin = 'llm' ORDER BY "
        "CASE section WHEN 'safety' THEN 0 ELSE 1 END, score DESC, id ASC"
    ).fetchall()
    return [_row_to_finding(r) for r in rows]


def list_day_findings(conn: sqlite3.Connection, day: date) -> list[dict[str, Any]]:
    day_s = day.isoformat()
    rows = conn.execute(
        "SELECT * FROM insights WHERE status = 'new' AND origin = 'llm_day' "
        "AND period_start = ? AND period_end = ? ORDER BY "
        "CASE section WHEN 'safety' THEN 0 ELSE 1 END, score DESC, id ASC",
        (day_s, day_s),
    ).fetchall()
    return [_row_to_finding(r) for r in rows]


def _normalize_days(days: int | None) -> int:
    if days in context.ALLOWED_COACH_DAYS:
        return int(days)
    return context.DEFAULT_COACH_DAYS


def get_coach(conn: sqlite3.Connection, *, days: int | None = None) -> dict[str, Any]:
    days = _normalize_days(days)
    findings = list_active_findings(conn)
    period_start = period_end = generated_at = None
    findings_days = None
    if findings:
        period_start = findings[0]["period_start"]
        period_end = findings[0]["period_end"]
        generated_at = findings[0]["created_at"]
        try:
            findings_days = (
                date.fromisoformat(period_end) - date.fromisoformat(period_start)
            ).days + 1
        except ValueError:
            findings_days = None

    pack = context.build_context_pack(conn, days=days)
    coverage = pack.get("coverage")
    if not findings:
        period_start = coverage.get("window_start")
        period_end = coverage.get("window_end")

    return {
        "findings": findings,
        "days": days,
        "findings_days": findings_days,
        "period_start": period_start,
        "period_end": period_end,
        "generated_at": generated_at,
        "coverage": coverage,
        "allowed_days": list(context.ALLOWED_COACH_DAYS),
        "api_key_configured": llm.api_key_configured(),
        "prompt_version": llm.PROMPT_VERSION,
        "model": llm.model_name() if llm.api_key_configured() else None,
    }


def refresh_coach(conn: sqlite3.Connection, *, days: int | None = None) -> dict[str, Any]:
    if not llm.api_key_configured():
        raise CoachError(
            "Add OPENAI_API_KEY to your .env file to generate coach recommendations.",
            status=503,
        )

    days = _normalize_days(days)
    settings = db.get_settings(conn)
    pack = context.build_context_pack(conn, days=days, settings=settings)
    if context.glucose_reading_count(pack) < 16:
        raise CoachError(
            "Not enough glucose data to coach yet. Import a LibreLink export first.",
            status=422,
        )

    try:
        raw = llm.generate_findings(pack)
    except Exception as exc:  # noqa: BLE001 — surface as 502 to the client
        raise CoachError(f"Coach model failed: {exc}", status=502) from exc

    findings = validate_findings(raw, coverage=pack.get("coverage") or {})
    if not findings:
        raise CoachError("The coach returned no usable findings. Try again.", status=502)

    coverage = pack["coverage"]
    period_start = coverage["window_start"]
    period_end = coverage["window_end"]
    created_at = _now_iso()

    with conn:
        conn.execute(
            "UPDATE insights SET status = 'superseded' WHERE status = 'new' AND origin = 'llm'"
        )
        for finding in findings:
            conn.execute(
                """
                INSERT INTO insights (
                    created_at, period_start, period_end, rule_id, origin, section,
                    title, insight, why_it_matters, try_text, evidence, confidence,
                    score, data_used, status, prompt_version
                ) VALUES (?, ?, ?, ?, 'llm', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)
                """,
                (
                    created_at,
                    period_start,
                    period_end,
                    None,
                    finding["section"],
                    finding["title"],
                    finding["insight"],
                    finding["why_it_matters"],
                    finding["try_text"],
                    json.dumps(finding["evidence"]),
                    finding["confidence"],
                    finding["score"],
                    json.dumps(finding["data_used"]),
                    llm.PROMPT_VERSION,
                ),
            )

    result = get_coach(conn, days=days)
    result["generated_at"] = created_at
    return result


def get_day_coach(conn: sqlite3.Connection, day: date) -> dict[str, Any]:
    pack = context.build_day_context_pack(conn, day)
    findings = list_day_findings(conn, day)
    generated_at = findings[0]["created_at"] if findings else None
    days_with_data = context.list_glucose_days(conn, limit=90)
    coached = {
        r["period_start"]
        for r in conn.execute(
            "SELECT DISTINCT period_start FROM insights "
            "WHERE status = 'new' AND origin = 'llm_day'"
        )
    }
    day_list = [
        {"date": d, "coached": d in coached, "selected": d == day.isoformat()}
        for d in days_with_data
    ]
    return {
        "mode": "day",
        "day": day.isoformat(),
        "findings": findings,
        "generated_at": generated_at,
        "coverage": pack.get("coverage"),
        "meals": pack.get("meals"),
        "meal_windows": (pack.get("examples") or {}).get("meal_glucose_windows") or [],
        "day_list": day_list,
        "prev_date": _adjacent(days_with_data, day.isoformat(), -1),
        "next_date": _adjacent(days_with_data, day.isoformat(), 1),
        "api_key_configured": llm.api_key_configured(),
        "prompt_version": llm.DAY_PROMPT_VERSION,
        "model": llm.model_name() if llm.api_key_configured() else None,
    }


def _adjacent(days: list[str], current: str, step: int) -> str | None:
    """days are newest-first. step -1 = older day, step +1 = newer day."""
    if not days:
        return None
    if current not in days:
        return days[0]
    idx = days.index(current) + (-step)
    if 0 <= idx < len(days):
        return days[idx]
    return None


def refresh_day_coach(conn: sqlite3.Connection, day: date) -> dict[str, Any]:
    if not llm.api_key_configured():
        raise CoachError(
            "Add OPENAI_API_KEY to your .env file to generate coach recommendations.",
            status=503,
        )
    settings = db.get_settings(conn)
    pack = context.build_day_context_pack(conn, day, settings=settings)
    if (pack.get("coverage") or {}).get("glucose_readings_n", 0) < 8:
        raise CoachError("Not enough glucose readings on this day to coach.", status=422)

    try:
        raw = llm.generate_day_findings(pack)
    except Exception as exc:  # noqa: BLE001
        raise CoachError(f"Coach model failed: {exc}", status=502) from exc

    findings = validate_findings(raw, coverage=pack.get("coverage") or {})
    findings = findings[:6]
    if not findings:
        raise CoachError("The coach returned no usable findings for this day.", status=502)

    day_s = day.isoformat()
    created_at = _now_iso()
    with conn:
        conn.execute(
            "UPDATE insights SET status = 'superseded' WHERE status = 'new' "
            "AND origin = 'llm_day' AND period_start = ? AND period_end = ?",
            (day_s, day_s),
        )
        for finding in findings:
            conn.execute(
                """
                INSERT INTO insights (
                    created_at, period_start, period_end, rule_id, origin, section,
                    title, insight, why_it_matters, try_text, evidence, confidence,
                    score, data_used, status, prompt_version
                ) VALUES (?, ?, ?, ?, 'llm_day', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)
                """,
                (
                    created_at,
                    day_s,
                    day_s,
                    None,
                    finding["section"],
                    finding["title"],
                    finding["insight"],
                    finding["why_it_matters"],
                    finding["try_text"],
                    json.dumps(finding["evidence"]),
                    finding["confidence"],
                    finding["score"],
                    json.dumps(finding["data_used"]),
                    llm.DAY_PROMPT_VERSION,
                ),
            )

    result = get_day_coach(conn, day)
    result["generated_at"] = created_at
    return result
