from __future__ import annotations

from datetime import date

from flask import Blueprint, g, jsonify, request

from . import analytics, db
from .coach import get_coach, get_day_coach, refresh_coach, refresh_day_coach
from .coach.service import CoachError

api = Blueprint("api", __name__)


@api.get("/settings")
def get_settings():
    return jsonify(db.get_settings(g.db))


@api.put("/settings")
def put_settings():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object"}), 400
    try:
        return jsonify(db.update_settings(g.db, data))
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@api.get("/today")
def today():
    """Glucose for one day: today by default, or the latest day with data if today has none."""
    settings = db.get_settings(g.db)
    latest = analytics.latest_glucose_date(g.db)
    requested = request.args.get("date")
    if requested:
        try:
            day = date.fromisoformat(requested)
        except ValueError:
            return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    elif latest and latest < date.today():
        day = latest
    else:
        day = date.today()

    summary = analytics.day_summary(
        g.db,
        day,
        settings["target_low"],
        settings["target_high"],
        cv_unstable_pct=float(settings["cv_unstable_pct"]),
    )
    summary.update(
        today=date.today().isoformat(),
        latest_data_date=latest.isoformat() if latest else None,
        target_low=settings["target_low"],
        target_high=settings["target_high"],
        cv_unstable_pct=settings["cv_unstable_pct"],
    )
    return jsonify(summary)


@api.get("/trends")
def trends():
    """Period metrics with glycemic variability as a first-class outcome."""
    settings = db.get_settings(g.db)
    days_raw = request.args.get("days", "14")
    try:
        days = int(days_raw)
    except ValueError:
        return jsonify({"error": "days must be an integer"}), 400
    if days not in (7, 14, 30, 90):
        return jsonify({"error": "days must be 7, 14, 30 or 90"}), 400

    end = None
    if request.args.get("end"):
        try:
            end = date.fromisoformat(request.args["end"])
        except ValueError:
            return jsonify({"error": "end must be YYYY-MM-DD"}), 400

    summary = analytics.trends_summary(
        g.db,
        days=days,
        end=end,
        target_low=settings["target_low"],
        target_high=settings["target_high"],
        cv_unstable_pct=float(settings["cv_unstable_pct"]),
    )
    return jsonify(summary)


@api.get("/lifestyle")
def lifestyle():
    """Simple food + sleep/activity views for Cronometer and Whoop data."""
    settings = db.get_settings(g.db)
    days_raw = request.args.get("days", "14")
    try:
        days = int(days_raw)
    except ValueError:
        return jsonify({"error": "days must be an integer"}), 400
    if days not in (7, 14, 30, 90):
        return jsonify({"error": "days must be 7, 14, 30 or 90"}), 400
    return jsonify(analytics.lifestyle_summary(g.db, days=days, target_high=settings["target_high"]))


def _coach_days_arg(raw: str | None, default: str = "7"):
    try:
        days = int(raw or default)
    except ValueError:
        return None, (jsonify({"error": "days must be an integer"}), 400)
    if days not in (7, 14, 30):
        return None, (jsonify({"error": "days must be 7, 14 or 30"}), 400)
    return days, None


@api.get("/coach")
def coach_get():
    """Latest active finding cards (+ coverage meta). Default window preview: 7 days."""
    days, err = _coach_days_arg(request.args.get("days"), "7")
    if err:
        return err
    return jsonify(get_coach(g.db, days=days))


@api.post("/coach/refresh")
def coach_refresh():
    """Rebuild context for the chosen window, call the LLM, persist ranked findings."""
    payload = request.get_json(silent=True) or {}
    days, err = _coach_days_arg(
        str(payload.get("days")) if payload.get("days") is not None else request.args.get("days"),
        "7",
    )
    if err:
        return err
    try:
        return jsonify(refresh_coach(g.db, days=days))
    except CoachError as exc:
        return jsonify({"error": str(exc)}), exc.status


@api.get("/coach/day")
def coach_day_get():
    """Findings + meal context for one calendar day."""
    raw = request.args.get("date")
    if not raw:
        return jsonify({"error": "date is required (YYYY-MM-DD)"}), 400
    try:
        day = date.fromisoformat(raw)
    except ValueError:
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    return jsonify(get_day_coach(g.db, day))


@api.post("/coach/day/refresh")
def coach_day_refresh():
    """Generate meal-centred findings for one day."""
    payload = request.get_json(silent=True) or {}
    raw = payload.get("date") or request.args.get("date")
    if not raw:
        return jsonify({"error": "date is required (YYYY-MM-DD)"}), 400
    try:
        day = date.fromisoformat(str(raw))
    except ValueError:
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    try:
        return jsonify(refresh_day_coach(g.db, day))
    except CoachError as exc:
        return jsonify({"error": str(exc)}), exc.status
