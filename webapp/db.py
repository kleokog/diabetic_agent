"""SQLite storage for the diabetes coach.

All timestamps are local wall-clock times stored as ISO strings
(``YYYY-MM-DDTHH:MM:SS``), because LibreLink records the phone's local time
without a time zone. Importers convert any source that has a time zone
(for example Whoop) to local time before storing it.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "diabetes.db"

SCHEMA_V1 = """
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    file_name TEXT,
    format TEXT,
    imported_at TEXT NOT NULL,
    counts TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE glucose (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mg_dl REAL NOT NULL,
    kind TEXT NOT NULL,
    source TEXT NOT NULL,
    import_batch_id INTEGER REFERENCES import_batches(id),
    UNIQUE (ts, kind)
);
CREATE INDEX idx_glucose_ts ON glucose(ts);

CREATE TABLE insulin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    units REAL,
    purpose TEXT NOT NULL DEFAULT 'unknown',
    insulin_name TEXT,
    likely_priming INTEGER NOT NULL DEFAULT 0,
    excluded INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    source TEXT NOT NULL,
    import_batch_id INTEGER REFERENCES import_batches(id)
);
CREATE INDEX idx_insulin_ts ON insulin(ts);

CREATE TABLE eating_occasions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    label TEXT,
    groups TEXT NOT NULL DEFAULT '[]',
    carbs REAL,
    net_carbs REAL,
    fibre REAL,
    sugar REAL,
    protein REAL,
    fat REAL,
    alcohol REAL,
    kcal REAL,
    nutrition_basis TEXT NOT NULL DEFAULT 'exact',
    time_estimated INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    source TEXT NOT NULL,
    import_batch_id INTEGER REFERENCES import_batches(id)
);
CREATE INDEX idx_occasions_start ON eating_occasions(start);

CREATE TABLE food_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    name TEXT NOT NULL,
    amount TEXT,
    category TEXT,
    grp TEXT,
    occasion_id INTEGER REFERENCES eating_occasions(id) ON DELETE CASCADE,
    carbs REAL,
    fibre REAL,
    sugar REAL,
    protein REAL,
    fat REAL,
    alcohol REAL,
    kcal REAL,
    nutrition_basis TEXT NOT NULL DEFAULT 'exact',
    source TEXT NOT NULL,
    import_batch_id INTEGER REFERENCES import_batches(id)
);
CREATE INDEX idx_food_items_ts ON food_items(ts);

CREATE TABLE group_totals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    grp TEXT NOT NULL,
    nutrients TEXT NOT NULL,
    source TEXT NOT NULL,
    import_batch_id INTEGER REFERENCES import_batches(id),
    UNIQUE (date, grp, source)
);

CREATE TABLE food_estimates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    food_name TEXT NOT NULL,
    amount TEXT NOT NULL DEFAULT '',
    nutrients TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (food_name, amount)
);

CREATE TABLE daily_nutrition (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    nutrients TEXT NOT NULL,
    source TEXT NOT NULL,
    import_batch_id INTEGER REFERENCES import_batches(id),
    UNIQUE (date, source)
);

CREATE TABLE workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start TEXT NOT NULL,
    end TEXT,
    duration_min REAL,
    activity TEXT NOT NULL,
    strain REAL,
    intensity TEXT,
    kcal REAL,
    avg_hr REAL,
    max_hr REAL,
    hr_zones TEXT,
    raw TEXT,
    source TEXT NOT NULL,
    import_batch_id INTEGER REFERENCES import_batches(id),
    UNIQUE (start, activity, source)
);
CREATE INDEX idx_workouts_start ON workouts(start);

CREATE TABLE daily_physiology (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_start TEXT NOT NULL,
    cycle_end TEXT,
    local_date TEXT NOT NULL,
    recovery_pct REAL,
    resting_hr REAL,
    hrv_ms REAL,
    skin_temp_c REAL,
    spo2_pct REAL,
    day_strain REAL,
    kcal REAL,
    avg_hr REAL,
    max_hr REAL,
    raw TEXT,
    source TEXT NOT NULL,
    import_batch_id INTEGER REFERENCES import_batches(id),
    UNIQUE (cycle_start, source)
);

CREATE TABLE sleep (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    onset TEXT NOT NULL,
    wake TEXT,
    is_nap INTEGER NOT NULL DEFAULT 0,
    asleep_min REAL,
    in_bed_min REAL,
    light_min REAL,
    deep_min REAL,
    rem_min REAL,
    awake_min REAL,
    performance_pct REAL,
    need_min REAL,
    debt_min REAL,
    efficiency_pct REAL,
    consistency_pct REAL,
    resp_rate REAL,
    raw TEXT,
    source TEXT NOT NULL,
    import_batch_id INTEGER REFERENCES import_batches(id),
    UNIQUE (onset, source)
);
CREATE INDEX idx_sleep_onset ON sleep(onset);

CREATE TABLE wellbeing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mood INTEGER,
    stress INTEGER,
    energy INTEGER,
    tags TEXT NOT NULL DEFAULT '[]',
    note TEXT,
    source TEXT NOT NULL,
    import_batch_id INTEGER REFERENCES import_batches(id)
);
CREATE INDEX idx_wellbeing_ts ON wellbeing(ts);

CREATE TABLE measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    source TEXT NOT NULL,
    import_batch_id INTEGER REFERENCES import_batches(id)
);

CREATE TABLE insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    rule_id TEXT,
    origin TEXT NOT NULL,
    section TEXT NOT NULL,
    title TEXT NOT NULL,
    insight TEXT NOT NULL,
    why_it_matters TEXT,
    try_text TEXT,
    evidence TEXT NOT NULL DEFAULT '{}',
    confidence TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0,
    data_used TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'new',
    prompt_version TEXT
);

CREATE TABLE experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insight_id INTEGER REFERENCES insights(id),
    title TEXT NOT NULL,
    metric TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    baseline TEXT,
    result TEXT
);

CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL
);
"""

SCHEMA_V2 = """
ALTER TABLE insulin ADD COLUMN device TEXT;
ALTER TABLE insulin ADD COLUMN logged_kind TEXT;
ALTER TABLE insulin ADD COLUMN reclassified INTEGER NOT NULL DEFAULT 0;
ALTER TABLE insulin ADD COLUMN source_key TEXT;
CREATE UNIQUE INDEX idx_insulin_source_key ON insulin(source, source_key) WHERE source_key IS NOT NULL;
CREATE UNIQUE INDEX idx_measurements_unique ON measurements(date, metric, source);
CREATE UNIQUE INDEX idx_occasions_libre ON eating_occasions(start, source) WHERE source = 'libre';
"""

MIGRATIONS: list[tuple[int, str]] = [(1, SCHEMA_V1), (2, SCHEMA_V2)]

DEFAULT_SETTINGS: dict[str, Any] = {
    "name": "",
    "diabetes_type": "Type 1",
    "target_low": 80,
    "target_high": 150,
    "timezone": "Europe/London",
    "rapid_insulin_name": "",
    "long_insulin_name": "",
    "carb_ratio": None,
    "correction_factor": None,
    "default_meal_times": {
        "Breakfast": "08:00",
        "Lunch": "13:00",
        "Dinner": "20:00",
        "Snacks": "16:00",
    },
    "occasion_gap_min": 45,
    "long_acting_min_units": 25,
    "priming_max_units": 2,
    "priming_window_min": 5,
    "coach_brief": "",
}

INTEGER_SETTINGS = {"target_low", "target_high", "occasion_gap_min", "priming_window_min"}
NUMBER_SETTINGS = {"long_acting_min_units", "priming_max_units"}


def db_path() -> Path:
    return Path(os.environ.get("DIABETES_DB", DEFAULT_DB_PATH))


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path) if path else db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    """Apply any pending migrations and return the resulting schema version."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, sql in MIGRATIONS:
        if version > current:
            with conn:
                conn.executescript(sql)
                conn.execute(f"PRAGMA user_version = {version}")
            current = version
    return current


def get_settings(conn: sqlite3.Connection) -> dict[str, Any]:
    stored = {row["key"]: json.loads(row["value"]) for row in conn.execute("SELECT key, value FROM settings")}
    return {**DEFAULT_SETTINGS, **stored}


def update_settings(conn: sqlite3.Connection, values: dict[str, Any]) -> dict[str, Any]:
    clean = validate_settings(values, current=get_settings(conn))
    with conn:
        conn.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [(key, json.dumps(value)) for key, value in clean.items()],
        )
    return get_settings(conn)


def validate_settings(values: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in values.items():
        if key not in DEFAULT_SETTINGS:
            raise ValueError(f"Unknown setting: {key}")
        if key in INTEGER_SETTINGS:
            value = int(value)
        elif key in NUMBER_SETTINGS:
            value = float(value)
        elif key in ("carb_ratio", "correction_factor"):
            value = float(value) if value not in (None, "") else None
        elif key == "default_meal_times":
            if not isinstance(value, dict):
                raise ValueError("default_meal_times must be an object")
        elif value is not None:
            value = str(value).strip()
        clean[key] = value

    merged = {**(current or DEFAULT_SETTINGS), **clean}
    low, high = merged["target_low"], merged["target_high"]
    if not 60 <= low <= 120:
        raise ValueError("The lower target must be between 60 and 120 mg/dL")
    if not 120 <= high <= 250:
        raise ValueError("The upper target must be between 120 and 250 mg/dL")
    if low >= high:
        raise ValueError("The lower target must be below the upper target")
    if not 10 <= merged["long_acting_min_units"] <= 100:
        raise ValueError("The long-acting threshold must be between 10 and 100 units")
    if not 0 <= merged["priming_max_units"] <= 5:
        raise ValueError("The priming size must be between 0 and 5 units")
    if not 1 <= merged["priming_window_min"] <= 30:
        raise ValueError("The priming window must be between 1 and 30 minutes")
    if "coach_brief" in clean and len(clean["coach_brief"] or "") > 4000:
        raise ValueError("The coach brief is limited to 4,000 characters")
    return clean
