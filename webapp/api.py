from __future__ import annotations

from datetime import date

from flask import Blueprint, g, jsonify, request

from . import analytics, db

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

    summary = analytics.day_summary(g.db, day, settings["target_low"], settings["target_high"])
    summary.update(
        today=date.today().isoformat(),
        latest_data_date=latest.isoformat() if latest else None,
        target_low=settings["target_low"],
        target_high=settings["target_high"],
    )
    return jsonify(summary)
