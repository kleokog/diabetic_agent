"""Upload, review, import and undo data files."""

from __future__ import annotations

import json
import secrets
import time
from datetime import date, datetime
from pathlib import Path

from flask import Blueprint, g, jsonify, request

from . import db
from .importers import libre

imports = Blueprint("imports", __name__)

UPLOAD_DIR = db.PROJECT_ROOT / "data" / "uploads"
DATA_TABLES = ("glucose", "insulin", "eating_occasions", "food_items", "group_totals", "daily_nutrition",
               "workouts", "daily_physiology", "sleep", "wellbeing", "measurements")


def _detect(path: Path) -> str | None:
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        head = [handle.readline() for _ in range(3)]
    if libre.is_libre_export(head):
        return "libre"
    return None


def _remove_stale_uploads(max_age_hours: int = 24) -> None:
    """Uploads that were previewed but never imported are deleted after a day."""
    cutoff = time.time() - max_age_hours * 3600
    for path in UPLOAD_DIR.glob("*"):
        if path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)


def _upload_path(token: str) -> Path:
    if not token.isalnum():
        raise ValueError("Invalid upload token")
    return UPLOAD_DIR / f"{token}.csv"


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
    (UPLOAD_DIR / f"{token}.json").write_text(json.dumps({"file_name": upload.filename}))

    file_format = _detect(path)
    if file_format is None:
        path.unlink(missing_ok=True)
        return jsonify({"error": "This file isn't recognised. LibreLink exports are supported now; Cronometer and Whoop are coming next."}), 400

    data = libre.read(path)
    summary = libre.summarise(g.db, data, db.get_settings(g.db))
    summary.update(token=token, file_name=upload.filename)
    return jsonify(summary)


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
    include = set(body.get("include") or [])
    data = libre.read(path)
    libre.summarise(g.db, data, db.get_settings(g.db))

    with g.db:
        batch_id = g.db.execute(
            "INSERT INTO import_batches (source, file_name, format, imported_at) VALUES ('libre', ?, 'libre', ?)",
            (meta["file_name"], datetime.now().isoformat(timespec="seconds")),
        ).lastrowid
        counts = libre.commit(g.db, data, batch_id, include, bool(body.get("include_priming")), from_date)
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
    return jsonify({"removed": {k: v for k, v in removed.items() if v}})
