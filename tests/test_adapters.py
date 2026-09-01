"""Tests for orangejuicer.adapters and new CLI commands (query, workout, export)."""

import json
from datetime import date

import pytest

from orangejuicer.adapters import db_to_reddit_posts, db_to_workout_records
from orangejuicer.db import get_connection
from orangejuicer.demo import generate_demo_data, replay_into_db


@pytest.fixture()
def populated_db(tmp_path):
    """A database pre-loaded with demo data."""
    conn = get_connection(tmp_path / "test.db")
    workouts, reddit = generate_demo_data(num_workouts=30, num_reddit_posts=15, seed=77)
    replay_into_db(conn, workouts, reddit)
    yield conn
    conn.close()


class TestDbToWorkoutRecords:
    def test_returns_workout_records(self, populated_db):
        records = db_to_workout_records(populated_db)
        assert len(records) == 30
        rec = records[0]
        assert rec.workout_id  # non-empty
        assert isinstance(rec.workout_date, date)
        assert rec.calories_burned > 0

    def test_limit(self, populated_db):
        records = db_to_workout_records(populated_db, limit=5)
        assert len(records) == 5

    def test_last_days(self, populated_db):
        records = db_to_workout_records(populated_db, last_days=30)
        cutoff = date.today().toordinal() - 30
        for r in records:
            assert r.workout_date.toordinal() >= cutoff

    def test_coach_filter(self, populated_db):
        records = db_to_workout_records(populated_db, coach="Mike")
        assert all("Mike" in r.coach for r in records)

    def test_studio_filter(self, populated_db):
        records = db_to_workout_records(populated_db, studio="Downtown")
        assert all("Downtown" in r.studio_name for r in records)

    def test_date_range_filter(self, populated_db):
        all_records = db_to_workout_records(populated_db)
        if len(all_records) < 2:
            pytest.skip("Not enough data")
        mid = all_records[len(all_records) // 2].workout_date.isoformat()
        filtered = db_to_workout_records(populated_db, date_from=mid)
        assert len(filtered) <= len(all_records)
        for r in filtered:
            assert r.workout_date.isoformat() >= mid

    def test_zone_times_populated(self, populated_db):
        records = db_to_workout_records(populated_db, limit=5)
        with_zones = [r for r in records if r.zone_time_minutes]
        assert len(with_zones) > 0
        for r in with_zones:
            assert "orange" in r.zone_time_minutes

    def test_empty_db(self, tmp_path):
        conn = get_connection(tmp_path / "empty.db")
        records = db_to_workout_records(conn)
        assert records == []
        conn.close()


class TestDbToRedditPosts:
    def test_returns_reddit_posts(self, populated_db):
        posts = db_to_reddit_posts(populated_db)
        assert len(posts) == 15
        post = posts[0]
        assert post.post_id
        assert post.title

    def test_limit(self, populated_db):
        posts = db_to_reddit_posts(populated_db, limit=3)
        assert len(posts) == 3


class TestExportRoundtrip:
    def test_json_export_reimport(self, populated_db, tmp_path):
        """Export as JSON, load back, verify it matches fixture schema."""
        records = db_to_workout_records(populated_db)
        assert len(records) > 0

        # Export via the DB directly (simulating cmd_export logic)
        rows = populated_db.execute(
            "SELECT * FROM workouts ORDER BY workout_date"
        ).fetchall()
        data = [dict(r) for r in rows]
        path = tmp_path / "export.json"
        path.write_text(json.dumps(data, default=str))

        loaded = json.loads(path.read_text())
        assert len(loaded) == 30
        assert "performance_summary_id" in loaded[0]
