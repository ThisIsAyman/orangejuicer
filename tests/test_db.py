"""Tests for orangejuicer.db — schema, upserts, and sync log."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from orangejuicer.db import (
    get_connection,
    get_sync_cursor,
    update_sync_cursor,
    upsert_body_composition,
    upsert_reddit_post,
    upsert_rower_summary,
    upsert_studio,
    upsert_telemetry_batch,
    upsert_treadmill_summary,
    upsert_workout,
)


@pytest.fixture()
def db(tmp_path):
    """Yield a fresh database connection for each test."""
    conn = get_connection(tmp_path / "test.db")
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_all_tables_created(self, db):
        tables = {
            r["name"]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        expected = {
            "meta", "studios", "workouts", "treadmill_summary", "rower_summary",
            "telemetry", "reddit_posts", "benchmarks", "body_composition", "sync_log",
        }
        assert expected == tables

    def test_schema_version_set(self, db):
        row = db.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        assert row is not None
        assert int(row["value"]) >= 1

    def test_foreign_keys_enabled(self, db):
        row = db.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1

    def test_wal_mode(self, db):
        row = db.execute("PRAGMA journal_mode").fetchone()
        assert row[0] == "wal"

    def test_reopen_is_idempotent(self, tmp_path):
        path = tmp_path / "reopen.db"
        conn1 = get_connection(path)
        conn1.close()
        conn2 = get_connection(path)
        ver = conn2.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        assert int(ver["value"]) >= 1
        conn2.close()


# ---------------------------------------------------------------------------
# Studio upserts
# ---------------------------------------------------------------------------

def _studio(**overrides):
    base = {
        "studio_uuid": "studio-1",
        "name": "Downtown",
        "phone_number": "555-0100",
        "email": "dt@otf.com",
        "latitude": 40.7,
        "longitude": -74.0,
        "time_zone": "America/New_York",
        "address_line1": "123 Main St",
        "city": "New York",
        "state": "NY",
        "postal_code": "10001",
        "country": "US",
        "mbo_studio_id": "mbo-1",
    }
    base.update(overrides)
    return base


class TestStudioUpsert:
    def test_insert(self, db):
        upsert_studio(db, _studio())
        db.commit()
        row = db.execute("SELECT * FROM studios WHERE studio_uuid = 'studio-1'").fetchone()
        assert row["name"] == "Downtown"

    def test_update_preserves_existing(self, db):
        upsert_studio(db, _studio())
        upsert_studio(db, _studio(name="Uptown", email=None))
        db.commit()
        row = db.execute("SELECT * FROM studios WHERE studio_uuid = 'studio-1'").fetchone()
        assert row["name"] == "Uptown"
        assert row["email"] == "dt@otf.com"  # COALESCE preserves old value


# ---------------------------------------------------------------------------
# Workout upserts
# ---------------------------------------------------------------------------

def _workout(**overrides):
    base = {
        "performance_summary_id": "ps-1",
        "class_history_uuid": "ch-1",
        "booking_id": "bk-1",
        "class_uuid": "cl-1",
        "workout_date": "2024-03-15",
        "starts_at": "2024-03-15T09:00:00",
        "class_name": "Orange 60",
        "class_type": "ORANGE_60",
        "coach_name": "Coach Mike",
        "studio_uuid": None,
        "calories_burned": 500,
        "splat_points": 18,
        "step_count": 8000,
        "active_time_seconds": 3600,
        "avg_hr": 142,
        "max_hr": 170,
        "peak_hr": 175,
        "peak_hr_percent": 92,
        "avg_hr_percent": 75,
        "zone_gray_min": 5,
        "zone_blue_min": 10,
        "zone_green_min": 15,
        "zone_orange_min": 20,
        "zone_red_min": 5,
        "class_rating": 3,
        "coach_rating": 3,
        "raw_json": '{"test": true}',
    }
    base.update(overrides)
    return base


class TestWorkoutUpsert:
    def test_insert(self, db):
        upsert_workout(db, _workout())
        db.commit()
        row = db.execute("SELECT * FROM workouts WHERE performance_summary_id = 'ps-1'").fetchone()
        assert row["calories_burned"] == 500
        assert row["coach_name"] == "Coach Mike"

    def test_upsert_updates(self, db):
        upsert_workout(db, _workout())
        upsert_workout(db, _workout(calories_burned=600))
        db.commit()
        row = db.execute("SELECT * FROM workouts WHERE performance_summary_id = 'ps-1'").fetchone()
        assert row["calories_burned"] == 600

    def test_with_studio_fk(self, db):
        upsert_studio(db, _studio())
        upsert_workout(db, _workout(studio_uuid="studio-1"))
        db.commit()
        row = db.execute("SELECT * FROM workouts WHERE performance_summary_id = 'ps-1'").fetchone()
        assert row["studio_uuid"] == "studio-1"


# ---------------------------------------------------------------------------
# Equipment summary upserts
# ---------------------------------------------------------------------------

class TestEquipmentSummaryUpsert:
    def test_treadmill(self, db):
        upsert_workout(db, _workout())
        upsert_treadmill_summary(db, {
            "performance_summary_id": "ps-1",
            "avg_pace": 8.5, "avg_speed": 7.0, "max_pace": 7.0, "max_speed": 9.0,
            "moving_time": 1200.0, "total_distance": 2.5,
            "avg_incline": 1.0, "max_incline": 5.0, "elevation_gained": 50.0,
        })
        db.commit()
        row = db.execute("SELECT * FROM treadmill_summary WHERE performance_summary_id = 'ps-1'").fetchone()
        assert row["total_distance"] == 2.5

    def test_rower(self, db):
        upsert_workout(db, _workout())
        upsert_rower_summary(db, {
            "performance_summary_id": "ps-1",
            "avg_pace": 120.0, "avg_speed": 3.0, "max_pace": 100.0, "max_speed": 4.0,
            "moving_time": 900.0, "total_distance": 2000.0,
            "avg_cadence": 28.0, "avg_power": 150.0, "max_cadence": 32.0,
        })
        db.commit()
        row = db.execute("SELECT * FROM rower_summary WHERE performance_summary_id = 'ps-1'").fetchone()
        assert row["total_distance"] == 2000.0


# ---------------------------------------------------------------------------
# Telemetry upserts
# ---------------------------------------------------------------------------

class TestTelemetryUpsert:
    def test_batch_insert(self, db):
        upsert_workout(db, _workout())
        rows = [
            {
                "performance_summary_id": "ps-1", "relative_timestamp": i * 10,
                "hr": 130 + i, "agg_splats": i, "agg_calories": i * 5,
                "timestamp": None, "tread_speed": 7.0, "tread_incline": 1.0,
                "tread_distance": i * 0.1, "row_speed": None, "row_spm": None,
                "row_distance": None, "row_pace": None,
            }
            for i in range(10)
        ]
        upsert_telemetry_batch(db, "ps-1", rows)
        db.commit()
        count = db.execute("SELECT COUNT(*) as c FROM telemetry WHERE performance_summary_id = 'ps-1'").fetchone()
        assert count["c"] == 10

    def test_resync_replaces(self, db):
        upsert_workout(db, _workout())
        rows_v1 = [
            {
                "performance_summary_id": "ps-1", "relative_timestamp": 0,
                "hr": 130, "agg_splats": 0, "agg_calories": 0,
                "timestamp": None, "tread_speed": None, "tread_incline": None,
                "tread_distance": None, "row_speed": None, "row_spm": None,
                "row_distance": None, "row_pace": None,
            },
        ]
        upsert_telemetry_batch(db, "ps-1", rows_v1)
        rows_v2 = [
            {
                "performance_summary_id": "ps-1", "relative_timestamp": 0,
                "hr": 140, "agg_splats": 1, "agg_calories": 5,
                "timestamp": None, "tread_speed": None, "tread_incline": None,
                "tread_distance": None, "row_speed": None, "row_spm": None,
                "row_distance": None, "row_pace": None,
            },
            {
                "performance_summary_id": "ps-1", "relative_timestamp": 10,
                "hr": 145, "agg_splats": 2, "agg_calories": 10,
                "timestamp": None, "tread_speed": None, "tread_incline": None,
                "tread_distance": None, "row_speed": None, "row_spm": None,
                "row_distance": None, "row_pace": None,
            },
        ]
        upsert_telemetry_batch(db, "ps-1", rows_v2)
        db.commit()
        count = db.execute("SELECT COUNT(*) as c FROM telemetry WHERE performance_summary_id = 'ps-1'").fetchone()
        assert count["c"] == 2
        row = db.execute("SELECT hr FROM telemetry WHERE performance_summary_id = 'ps-1' AND relative_timestamp = 0").fetchone()
        assert row["hr"] == 140


# ---------------------------------------------------------------------------
# Reddit post upserts
# ---------------------------------------------------------------------------

class TestRedditPostUpsert:
    def test_insert(self, db):
        upsert_reddit_post(db, {
            "post_id": "r1", "title": "My OTF results", "raw_text": "Got 20 splats!",
            "created_utc": 1700000000.0, "score": 42, "url": "https://reddit.com/r1",
            "splat_points": 20, "calories": 500, "avg_heart_rate": 145, "max_heart_rate": 180,
        })
        db.commit()
        row = db.execute("SELECT * FROM reddit_posts WHERE post_id = 'r1'").fetchone()
        assert row["splat_points"] == 20
        assert row["raw_text"] == "Got 20 splats!"

    def test_upsert_updates_score(self, db):
        post = {
            "post_id": "r1", "title": "My OTF results", "raw_text": "Got 20 splats!",
            "created_utc": 1700000000.0, "score": 42, "url": "https://reddit.com/r1",
            "splat_points": 20, "calories": 500, "avg_heart_rate": 145, "max_heart_rate": 180,
        }
        upsert_reddit_post(db, post)
        post["score"] = 99
        upsert_reddit_post(db, post)
        db.commit()
        row = db.execute("SELECT score FROM reddit_posts WHERE post_id = 'r1'").fetchone()
        assert row["score"] == 99


# ---------------------------------------------------------------------------
# Sync log
# ---------------------------------------------------------------------------

class TestSyncLog:
    def test_no_entry_returns_none(self, db):
        assert get_sync_cursor(db, "workouts") is None

    def test_update_and_read(self, db):
        update_sync_cursor(db, "workouts", "2024-03-15", full_sync_done=True)
        db.commit()
        cursor = get_sync_cursor(db, "workouts")
        assert cursor is not None
        assert cursor["cursor"] == "2024-03-15"
        assert cursor["full_sync_done"] == 1

    def test_incremental_preserves_full_sync_flag(self, db):
        update_sync_cursor(db, "workouts", "2024-01-01", full_sync_done=True)
        update_sync_cursor(db, "workouts", "2024-03-15", full_sync_done=False)
        db.commit()
        cursor = get_sync_cursor(db, "workouts")
        assert cursor["full_sync_done"] == 1  # MAX preserves the 1
        assert cursor["cursor"] == "2024-03-15"
