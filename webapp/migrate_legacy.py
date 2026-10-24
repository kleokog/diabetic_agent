"""Copy glucose readings and meals from the old Streamlit database.

Run once from the project folder:  python -m webapp.migrate_legacy
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from . import db

LEGACY_DB = db.PROJECT_ROOT / "diabetic_agent.db"


def normalise_ts(value: str) -> str:
    return datetime.fromisoformat(value).replace(microsecond=0).isoformat()


def migrate_legacy(legacy_path: Path, conn: sqlite3.Connection) -> dict[str, int]:
    if conn.execute("SELECT 1 FROM import_batches WHERE source = 'legacy' AND status = 'active'").fetchone():
        return {"skipped": 1}

    legacy = sqlite3.connect(f"file:{legacy_path}?mode=ro", uri=True)
    legacy.row_factory = sqlite3.Row

    with conn:
        batch_id = conn.execute(
            "INSERT INTO import_batches (source, file_name, format, imported_at) VALUES ('legacy', ?, 'streamlit_db', ?)",
            (legacy_path.name, datetime.now().isoformat(timespec="seconds")),
        ).lastrowid

        readings = legacy.execute("SELECT timestamp, value FROM blood_sugar_levels ORDER BY timestamp, id").fetchall()
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO glucose (ts, mg_dl, kind, source, import_batch_id) VALUES (?, ?, 'sensor', 'legacy', ?)",
            [(normalise_ts(r["timestamp"]), float(r["value"]), batch_id) for r in readings],
        )
        glucose_added = conn.total_changes - before

        meals_added = 0
        for meal in legacy.execute("SELECT * FROM meal_logs ORDER BY timestamp").fetchall():
            ts = normalise_ts(meal["timestamp"])
            conn.execute(
                "INSERT INTO eating_occasions (start, end, label, groups, carbs, protein, fat, kcal, "
                "nutrition_basis, time_estimated, notes, source, import_batch_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'exact', 1, ?, 'legacy', ?)",
                (
                    ts, ts, meal["meal_type"], json.dumps([meal["meal_type"]]),
                    meal["total_carbs"], meal["total_protein"], meal["total_fat"], meal["total_calories"],
                    meal["notes"], batch_id,
                ),
            )
            meals_added += 1

        counts = {
            "glucose_read": len(readings),
            "glucose_added": glucose_added,
            "glucose_duplicates": len(readings) - glucose_added,
            "eating_occasions_added": meals_added,
        }
        conn.execute("UPDATE import_batches SET counts = ? WHERE id = ?", (json.dumps(counts), batch_id))

    legacy.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-db", type=Path, default=LEGACY_DB)
    args = parser.parse_args()

    conn = db.connect()
    db.migrate(conn)
    counts = migrate_legacy(args.legacy_db, conn)
    conn.close()
    if counts.get("skipped"):
        print("Legacy data was already migrated; nothing to do.")
    else:
        print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
