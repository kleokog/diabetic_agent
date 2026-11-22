"""Upload, review, import and undo data files."""

from __future__ import annotations

import json
import secrets
import time
from datetime import date, datetime
from pathlib import Path

from flask import Blueprint, g, jsonify, request

from . import db
from .importers import cronometer, libre, whoop

imports = Blueprint("imports", __name__)

UPLOAD_DIR = db.PROJECT_ROOT / "data" / "uploads"
DATA_TABLES = (
    "glucose",
    "insulin",
    "eating_occasions",
    "food_items",
    "group_totals",
    "daily_nutrition",
    "workouts",
    "daily_physiology",
    "sleep",
    "wellbeing",
    "measurements",
)


def _detect(path: Path) -> str | None:
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        head = [handle.readline() for _ in range(3)]
    if libre.is_libre_export(head):
        return "libre"
    if cronometer.is_servings_export(head):
        return "cronometer_servings"
    if cronometer.is_daily_summary_export(head):
        return "cronometer_daily"
    if whoop.is_sleeps_export(head):
        return "whoop_sleeps"
    if whoop.is_workouts_export(head):
        return "whoop_workouts"
    if whoop.is_cycles_export(head):
        return "whoop_cycles"
    return None


def _remove_stale_uploads(max_age_hours: int = 24) -> None:
    cutoff = time.time() - max_age_hours * 3600
    for path in UPLOAD_DIR.glob("*"):
        if path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)


def _upload_path(token: str) -> Path:
    if not token.isalnum():
        raise ValueError("Invalid upload token")
    return UPLOAD_DIR / f"{token}.csv"


def _preview_for(fmt: str, path: Path, conn, settings: dict) -> dict:
    if fmt == "libre":
        data = libre.read(path)
        return libre.summarise(conn, data, settings)
    if fmt == "cronometer_servings":
        data = cronometer.read_servings(path)
        return cronometer.summarise_servings(conn, data, settings)
    if fmt == "cronometer_daily":
        data = cronometer.read_daily_summary(path)
        return cronometer.summarise_daily(conn, data)
    if fmt == "whoop_sleeps":
        return whoop.summarise_sleeps(conn, whoop.read_sleeps(path))
    if fmt == "whoop_workouts":
        return whoop.summarise_workouts(conn, whoop.read_workouts(path))
    if fmt == "whoop_cycles":
        return whoop.summarise_cycles(conn, whoop.read_cycles(path))
    raise ValueError(f"Unknown format: {fmt}")


def _source_for(fmt: str) -> str:
    if fmt.startswith("cronometer"):
        return "cronometer"
    if fmt.startswith("whoop"):
        return "whoop"
    return "libre"


def _commit_for(fmt: str, path: Path, conn, batch_id: int, include: set[str], include_priming: bool, from_date: date | None, settings: dict) -> dict[str, int]:
    if fmt == "libre":
        data = libre.read(path)
        libre.summarise(conn, data, settings)
        return libre.commit(conn, data, batch_id, include, include_priming, from_date)
    if fmt == "cronometer_servings":
        data = cronometer.read_servings(path)
        summary = cronometer.summarise_servings(conn, data, settings)
        return cronometer.commit_servings(conn, summary["_occasions"], batch_id, include, from_date)
    if fmt == "cronometer_daily":
        data = cronometer.read_daily_summary(path)
        summary = cronometer.summarise_daily(conn, data)
        return cronometer.commit_daily(conn, summary["_rows"], batch_id, include, from_date)
    if fmt == "whoop_sleeps":
        data = whoop.read_sleeps(path)
        return whoop.commit_sleeps(conn, data.rows, batch_id, include, from_date)
    if fmt == "whoop_workouts":
        data = whoop.read_workouts(path)
        return whoop.commit_workouts(conn, data.rows, batch_id, include, from_date)
    if fmt == "whoop_cycles":
        data = whoop.read_cycles(path)
        return whoop.commit_cycles(conn, data.rows, batch_id, include, from_date)
    raise ValueError(f"Unknown format: {fmt}")


@imports.post("/preview")
def preview():
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({"error": "Choose a file to import"}), 400

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    _remove_stale_uploads()
    token = secrets.token_hex(8)
    path = _upload_path(token)
    upload.save(path)

    file_format = _detect(path)
    if file_format is None:
        path.unlink(missing_ok=True)
        return jsonify({
            "error": "This file isn't recognised. Supported: LibreLink, Cronometer servings/daily summary, Whoop sleeps/workouts/physiological cycles.",
        }), 400

    (UPLOAD_DIR / f"{token}.json").write_text(json.dumps({"file_name": upload.filename, "format": file_format}))
    summary = _preview_for(file_format, path, g.db, db.get_settings(g.db))
    # Strip private working keys before sending to the browser.
    public = {k: v for k, v in summary.items() if not k.startswith("_")}
    public.update(token=token, file_name=upload.filename)
    return jsonify(public)


@imports.post("/commit")
def commit():
    body = request.get_json(silent=True) or {}
    try:
        path = _upload_path(str(body.get("token", "")))
        from_date = date.fromisoformat(body["from_date"]) if body.get("from_date") else None
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not path.exists():
        return jsonify({"error": "This upload has expired. Choose the file again."}), 400

    meta = json.loads((UPLOAD_DIR / f"{path.stem}.json").read_text())
    fmt = meta.get("format") or _detect(path)
    if not fmt:
        return jsonify({"error": "Could not detect file format"}), 400
    include = set(body.get("include") or [])
    settings = db.get_settings(g.db)
    source = _source_for(fmt)

    with g.db:
        batch_id = g.db.execute(
            "INSERT INTO import_batches (source, file_name, format, imported_at) VALUES (?, ?, ?, ?)",
            (source, meta["file_name"], fmt, datetime.now().isoformat(timespec="seconds")),
        ).lastrowid
        counts = _commit_for(fmt, path, g.db, batch_id, include, bool(body.get("include_priming")), from_date, settings)
        if any(counts.values()):
            g.db.execute("UPDATE import_batches SET counts = ? WHERE id = ?", (json.dumps(counts), batch_id))
        else:
            g.db.execute("DELETE FROM import_batches WHERE id = ?", (batch_id,))
            batch_id = None

    path.unlink(missing_ok=True)
    (UPLOAD_DIR / f"{path.stem}.json").unlink(missing_ok=True)
    return jsonify({"batch_id": batch_id, "counts": counts})


@imports.get("")
def history():
    rows = g.db.execute(
        "SELECT id, source, file_name, imported_at, counts, status FROM import_batches ORDER BY id DESC LIMIT 50"
    ).fetchall()
    return jsonify([{**dict(r), "counts": json.loads(r["counts"])} for r in rows])


@imports.post("/<int:batch_id>/undo")
def undo(batch_id: int):
    batch = g.db.execute("SELECT status FROM import_batches WHERE id = ?", (batch_id,)).fetchone()
    if batch is None:
        return jsonify({"error": "Import not found"}), 404
    if batch["status"] != "active":
        return jsonify({"error": "This import was already undone"}), 400
    removed = {}
    with g.db:
        for table in DATA_TABLES:
            removed[table] = g.db.execute(f"DELETE FROM {table} WHERE import_batch_id = ?", (batch_id,)).rowcount
        g.db.execute("UPDATE import_batches SET status = 'undone' WHERE id = ?", (batch_id,))
    return jsonify({"removed": removed})
