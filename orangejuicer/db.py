"""SQLite database layer for orangejuicer.

Provides schema creation, migrations, connection management, and upsert
functions for all entities.  The database file defaults to
``~/.orangejuicer/orangejuicer.db`` and can be overridden with the
``OJ_DB_PATH`` environment variable.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


def default_db_path() -> Path:
    """Return the default database file path."""
    env = os.environ.get("OJ_DB_PATH")
    if env:
        return Path(env)
    return Path.home() / ".orangejuicer" / "orangejuicer.db"


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open (or create) the database and ensure the schema is up to date."""
    path = Path(db_path) if db_path else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row

    _ensure_schema(conn)
    return conn


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS studios (
    studio_uuid   TEXT PRIMARY KEY,
    name          TEXT,
    phone_number  TEXT,
    email         TEXT,
    latitude      REAL,
    longitude     REAL,
    time_zone     TEXT,
    address_line1 TEXT,
    city          TEXT,
    state         TEXT,
    postal_code   TEXT,
    country       TEXT,
    mbo_studio_id TEXT,
    updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS workouts (
    performance_summary_id TEXT PRIMARY KEY,
    class_history_uuid     TEXT,
    booking_id             TEXT,
    class_uuid             TEXT,
    workout_date           TEXT NOT NULL,
    starts_at              TEXT,
    class_name             TEXT,
    class_type             TEXT,
    coach_name             TEXT,
    studio_uuid            TEXT REFERENCES studios(studio_uuid),
    calories_burned        INTEGER,
    splat_points           INTEGER,
    step_count             INTEGER,
    active_time_seconds    INTEGER,
    avg_hr                 INTEGER,
    max_hr                 INTEGER,
    peak_hr                INTEGER,
    peak_hr_percent        INTEGER,
    avg_hr_percent         INTEGER,
    zone_gray_min          INTEGER,
    zone_blue_min          INTEGER,
    zone_green_min         INTEGER,
    zone_orange_min        INTEGER,
    zone_red_min           INTEGER,
    class_rating           INTEGER,
    coach_rating           INTEGER,
    raw_json               TEXT,
    synced_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(workout_date);
CREATE INDEX IF NOT EXISTS idx_workouts_studio ON workouts(studio_uuid);
CREATE INDEX IF NOT EXISTS idx_workouts_coach ON workouts(coach_name);

CREATE TABLE IF NOT EXISTS treadmill_summary (
    performance_summary_id TEXT PRIMARY KEY REFERENCES workouts(performance_summary_id),
    avg_pace               REAL,
    avg_speed              REAL,
    max_pace               REAL,
    max_speed              REAL,
    moving_time            REAL,
    total_distance         REAL,
    avg_incline            REAL,
    max_incline            REAL,
    elevation_gained       REAL
);

CREATE TABLE IF NOT EXISTS rower_summary (
    performance_summary_id TEXT PRIMARY KEY REFERENCES workouts(performance_summary_id),
    avg_pace               REAL,
    avg_speed              REAL,
    max_pace               REAL,
    max_speed              REAL,
    moving_time            REAL,
    total_distance         REAL,
    avg_cadence            REAL,
    avg_power              REAL,
    max_cadence            REAL
);

CREATE TABLE IF NOT EXISTS telemetry (
    performance_summary_id TEXT NOT NULL REFERENCES workouts(performance_summary_id),
    relative_timestamp     INTEGER NOT NULL,
    hr                     INTEGER,
    agg_splats             INTEGER,
    agg_calories           INTEGER,
    timestamp              TEXT,
    tread_speed            REAL,
    tread_incline          REAL,
    tread_distance         REAL,
    row_speed              REAL,
    row_spm                REAL,
    row_distance           REAL,
    row_pace               INTEGER,
    PRIMARY KEY (performance_summary_id, relative_timestamp)
);

CREATE TABLE IF NOT EXISTS reddit_posts (
    post_id        TEXT PRIMARY KEY,
    title          TEXT,
    raw_text       TEXT,
    created_utc    REAL,
    score          INTEGER,
    url            TEXT,
    splat_points   INTEGER,
    calories       INTEGER,
    avg_heart_rate INTEGER,
    max_heart_rate INTEGER,
    synced_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_reddit_created ON reddit_posts(created_utc);

CREATE TABLE IF NOT EXISTS benchmarks (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    performance_summary_id TEXT REFERENCES workouts(performance_summary_id),
    challenge_category_id  INTEGER,
    challenge_name         TEXT,
    equipment_id           INTEGER,
    equipment_name         TEXT,
    result_value           REAL,
    result_unit            TEXT,
    recorded_at            TEXT,
    synced_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS body_composition (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at  TEXT NOT NULL,
    weight       REAL,
    body_fat_pct REAL,
    muscle_mass  REAL,
    bmi          REAL,
    raw_json     TEXT,
    synced_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS sync_log (
    entity         TEXT PRIMARY KEY,
    last_synced    TEXT NOT NULL,
    cursor         TEXT,
    full_sync_done INTEGER NOT NULL DEFAULT 0
);
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables if needed and run migrations."""
    conn.executescript(_SCHEMA_SQL)

    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    current = int(row["value"]) if row else 0

    if current < SCHEMA_VERSION:
        _run_migrations(conn, current, SCHEMA_VERSION)
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('schema_version', ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()
        logger.info("Database schema at version %d.", SCHEMA_VERSION)


def _run_migrations(conn: sqlite3.Connection, from_ver: int, to_ver: int) -> None:
    """Run incremental migrations. Add new migrations here as the schema evolves."""
    # Migration 0 → 1: initial schema (handled by CREATE TABLE IF NOT EXISTS above)
    if from_ver < 1:
        logger.info("Initialising database schema (v%d → v%d).", from_ver, to_ver)


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------


def upsert_studio(conn: sqlite3.Connection, studio: dict[str, Any]) -> None:
    """Insert or update a studio record."""
    conn.execute(
        """INSERT INTO studios (
            studio_uuid, name, phone_number, email, latitude, longitude,
            time_zone, address_line1, city, state, postal_code, country,
            mbo_studio_id
        ) VALUES (
            :studio_uuid, :name, :phone_number, :email, :latitude, :longitude,
            :time_zone, :address_line1, :city, :state, :postal_code, :country,
            :mbo_studio_id
        ) ON CONFLICT(studio_uuid) DO UPDATE SET
            name          = COALESCE(excluded.name, studios.name),
            phone_number  = COALESCE(excluded.phone_number, studios.phone_number),
            email         = COALESCE(excluded.email, studios.email),
            latitude      = COALESCE(excluded.latitude, studios.latitude),
            longitude     = COALESCE(excluded.longitude, studios.longitude),
            time_zone     = COALESCE(excluded.time_zone, studios.time_zone),
            address_line1 = COALESCE(excluded.address_line1, studios.address_line1),
            city          = COALESCE(excluded.city, studios.city),
            state         = COALESCE(excluded.state, studios.state),
            postal_code   = COALESCE(excluded.postal_code, studios.postal_code),
            country       = COALESCE(excluded.country, studios.country),
            mbo_studio_id = COALESCE(excluded.mbo_studio_id, studios.mbo_studio_id),
            updated_at    = strftime('%Y-%m-%dT%H:%M:%fZ','now')
        """,
        studio,
    )


def upsert_workout(conn: sqlite3.Connection, workout: dict[str, Any]) -> None:
    """Insert or update a workout record."""
    conn.execute(
        """INSERT INTO workouts (
            performance_summary_id, class_history_uuid, booking_id, class_uuid,
            workout_date, starts_at, class_name, class_type, coach_name, studio_uuid,
            calories_burned, splat_points, step_count, active_time_seconds,
            avg_hr, max_hr, peak_hr, peak_hr_percent, avg_hr_percent,
            zone_gray_min, zone_blue_min, zone_green_min, zone_orange_min, zone_red_min,
            class_rating, coach_rating, raw_json
        ) VALUES (
            :performance_summary_id, :class_history_uuid, :booking_id, :class_uuid,
            :workout_date, :starts_at, :class_name, :class_type, :coach_name, :studio_uuid,
            :calories_burned, :splat_points, :step_count, :active_time_seconds,
            :avg_hr, :max_hr, :peak_hr, :peak_hr_percent, :avg_hr_percent,
            :zone_gray_min, :zone_blue_min, :zone_green_min, :zone_orange_min, :zone_red_min,
            :class_rating, :coach_rating, :raw_json
        ) ON CONFLICT(performance_summary_id) DO UPDATE SET
            class_history_uuid = excluded.class_history_uuid,
            booking_id         = excluded.booking_id,
            class_uuid         = excluded.class_uuid,
            workout_date       = excluded.workout_date,
            starts_at          = excluded.starts_at,
            class_name         = excluded.class_name,
            class_type         = excluded.class_type,
            coach_name         = excluded.coach_name,
            studio_uuid        = excluded.studio_uuid,
            calories_burned    = excluded.calories_burned,
            splat_points       = excluded.splat_points,
            step_count         = excluded.step_count,
            active_time_seconds = excluded.active_time_seconds,
            avg_hr             = excluded.avg_hr,
            max_hr             = excluded.max_hr,
            peak_hr            = excluded.peak_hr,
            peak_hr_percent    = excluded.peak_hr_percent,
            avg_hr_percent     = excluded.avg_hr_percent,
            zone_gray_min      = excluded.zone_gray_min,
            zone_blue_min      = excluded.zone_blue_min,
            zone_green_min     = excluded.zone_green_min,
            zone_orange_min    = excluded.zone_orange_min,
            zone_red_min       = excluded.zone_red_min,
            class_rating       = excluded.class_rating,
            coach_rating       = excluded.coach_rating,
            raw_json           = excluded.raw_json,
            synced_at          = strftime('%Y-%m-%dT%H:%M:%fZ','now')
        """,
        workout,
    )


def upsert_treadmill_summary(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    """Insert or update a treadmill summary record."""
    conn.execute(
        """INSERT INTO treadmill_summary (
            performance_summary_id, avg_pace, avg_speed, max_pace, max_speed,
            moving_time, total_distance, avg_incline, max_incline, elevation_gained
        ) VALUES (
            :performance_summary_id, :avg_pace, :avg_speed, :max_pace, :max_speed,
            :moving_time, :total_distance, :avg_incline, :max_incline, :elevation_gained
        ) ON CONFLICT(performance_summary_id) DO UPDATE SET
            avg_pace        = excluded.avg_pace,
            avg_speed       = excluded.avg_speed,
            max_pace        = excluded.max_pace,
            max_speed       = excluded.max_speed,
            moving_time     = excluded.moving_time,
            total_distance  = excluded.total_distance,
            avg_incline     = excluded.avg_incline,
            max_incline     = excluded.max_incline,
            elevation_gained = excluded.elevation_gained
        """,
        data,
    )


def upsert_rower_summary(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    """Insert or update a rower summary record."""
    conn.execute(
        """INSERT INTO rower_summary (
            performance_summary_id, avg_pace, avg_speed, max_pace, max_speed,
            moving_time, total_distance, avg_cadence, avg_power, max_cadence
        ) VALUES (
            :performance_summary_id, :avg_pace, :avg_speed, :max_pace, :max_speed,
            :moving_time, :total_distance, :avg_cadence, :avg_power, :max_cadence
        ) ON CONFLICT(performance_summary_id) DO UPDATE SET
            avg_pace    = excluded.avg_pace,
            avg_speed   = excluded.avg_speed,
            max_pace    = excluded.max_pace,
            max_speed   = excluded.max_speed,
            moving_time = excluded.moving_time,
            total_distance = excluded.total_distance,
            avg_cadence = excluded.avg_cadence,
            avg_power   = excluded.avg_power,
            max_cadence = excluded.max_cadence
        """,
        data,
    )


def upsert_telemetry_batch(
    conn: sqlite3.Connection,
    performance_summary_id: str,
    rows: list[dict[str, Any]],
) -> None:
    """Insert or replace a batch of telemetry rows for a single workout.

    Deletes existing telemetry for the workout first to handle re-syncs cleanly,
    then bulk-inserts all rows in a single transaction.
    """
    conn.execute(
        "DELETE FROM telemetry WHERE performance_summary_id = ?",
        (performance_summary_id,),
    )
    conn.executemany(
        """INSERT INTO telemetry (
            performance_summary_id, relative_timestamp, hr, agg_splats, agg_calories,
            timestamp, tread_speed, tread_incline, tread_distance,
            row_speed, row_spm, row_distance, row_pace
        ) VALUES (
            :performance_summary_id, :relative_timestamp, :hr, :agg_splats, :agg_calories,
            :timestamp, :tread_speed, :tread_incline, :tread_distance,
            :row_speed, :row_spm, :row_distance, :row_pace
        )""",
        rows,
    )


def upsert_reddit_post(conn: sqlite3.Connection, post: dict[str, Any]) -> None:
    """Insert or update a Reddit post."""
    conn.execute(
        """INSERT INTO reddit_posts (
            post_id, title, raw_text, created_utc, score, url,
            splat_points, calories, avg_heart_rate, max_heart_rate
        ) VALUES (
            :post_id, :title, :raw_text, :created_utc, :score, :url,
            :splat_points, :calories, :avg_heart_rate, :max_heart_rate
        ) ON CONFLICT(post_id) DO UPDATE SET
            title          = excluded.title,
            raw_text       = excluded.raw_text,
            score          = excluded.score,
            splat_points   = excluded.splat_points,
            calories       = excluded.calories,
            avg_heart_rate = excluded.avg_heart_rate,
            max_heart_rate = excluded.max_heart_rate,
            synced_at      = strftime('%Y-%m-%dT%H:%M:%fZ','now')
        """,
        post,
    )


def upsert_benchmark(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    """Insert a benchmark result (append-only with dedup on natural key)."""
    conn.execute(
        """INSERT INTO benchmarks (
            performance_summary_id, challenge_category_id, challenge_name,
            equipment_id, equipment_name, result_value, result_unit, recorded_at
        ) VALUES (
            :performance_summary_id, :challenge_category_id, :challenge_name,
            :equipment_id, :equipment_name, :result_value, :result_unit, :recorded_at
        ) ON CONFLICT DO NOTHING
        """,
        data,
    )


def upsert_body_composition(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    """Insert a body composition record."""
    conn.execute(
        """INSERT INTO body_composition (
            recorded_at, weight, body_fat_pct, muscle_mass, bmi, raw_json
        ) VALUES (
            :recorded_at, :weight, :body_fat_pct, :muscle_mass, :bmi, :raw_json
        )""",
        data,
    )


# ---------------------------------------------------------------------------
# Sync log helpers
# ---------------------------------------------------------------------------


def get_sync_cursor(conn: sqlite3.Connection, entity: str) -> dict[str, Any] | None:
    """Return the sync log entry for *entity*, or None if never synced."""
    row = conn.execute(
        "SELECT entity, last_synced, cursor, full_sync_done FROM sync_log WHERE entity = ?",
        (entity,),
    ).fetchone()
    return dict(row) if row else None


def update_sync_cursor(
    conn: sqlite3.Connection,
    entity: str,
    cursor: str,
    full_sync_done: bool = False,
) -> None:
    """Update the sync cursor for *entity*."""
    conn.execute(
        """INSERT INTO sync_log (entity, last_synced, cursor, full_sync_done)
        VALUES (:entity, strftime('%Y-%m-%dT%H:%M:%fZ','now'), :cursor, :full_sync_done)
        ON CONFLICT(entity) DO UPDATE SET
            last_synced    = strftime('%Y-%m-%dT%H:%M:%fZ','now'),
            cursor         = excluded.cursor,
            full_sync_done = MAX(sync_log.full_sync_done, excluded.full_sync_done)
        """,
        {"entity": entity, "cursor": cursor, "full_sync_done": int(full_sync_done)},
    )
