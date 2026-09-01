"""Tests for orangejuicer.demo — synthetic data generation and fixture replay."""

import json
from pathlib import Path

import pytest

from orangejuicer.db import get_connection
from orangejuicer.demo import (
    generate_demo_data,
    load_fixtures,
    replay_into_db,
    save_fixtures,
)


@pytest.fixture()
def db(tmp_path):
    conn = get_connection(tmp_path / "test.db")
    yield conn
    conn.close()


class TestGeneration:
    def test_generates_correct_counts(self):
        workouts, reddit = generate_demo_data(num_workouts=50, num_reddit_posts=30)
        assert len(workouts) == 50
        assert len(reddit) == 30

    def test_deterministic_with_same_seed(self):
        w1, r1 = generate_demo_data(num_workouts=10, num_reddit_posts=5, seed=99)
        w2, r2 = generate_demo_data(num_workouts=10, num_reddit_posts=5, seed=99)
        assert [w["performance_summary_id"] for w in w1] == [w["performance_summary_id"] for w in w2]
        assert [r["post_id"] for r in r1] == [r["post_id"] for r in r2]

    def test_different_seeds_produce_different_data(self):
        w1, _ = generate_demo_data(num_workouts=10, seed=1)
        w2, _ = generate_demo_data(num_workouts=10, seed=2)
        assert w1[0]["performance_summary_id"] != w2[0]["performance_summary_id"]

    def test_workouts_have_required_fields(self):
        workouts, _ = generate_demo_data(num_workouts=5, num_reddit_posts=0)
        required = {
            "performance_summary_id", "workout_date", "starts_at",
            "class_name", "coach_name", "studio_uuid",
            "calories_burned", "splat_points", "avg_hr", "max_hr",
        }
        for w in workouts:
            missing = required - set(w.keys())
            assert not missing, f"Missing fields: {missing}"

    def test_workouts_sorted_by_date(self):
        workouts, _ = generate_demo_data(num_workouts=50, num_reddit_posts=0)
        dates = [w["workout_date"] for w in workouts]
        assert dates == sorted(dates)

    def test_telemetry_generated(self):
        workouts, _ = generate_demo_data(num_workouts=5, num_reddit_posts=0)
        with_telemetry = [w for w in workouts if w.get("_telemetry")]
        assert len(with_telemetry) == 5
        # Each workout should have ~150 telemetry points
        for w in with_telemetry:
            assert 50 < len(w["_telemetry"]) < 300

    def test_studios_from_known_set(self):
        workouts, _ = generate_demo_data(num_workouts=20, num_reddit_posts=0)
        studio_ids = {w["studio_uuid"] for w in workouts}
        known = {"studio-demo-001", "studio-demo-002", "studio-demo-003"}
        assert studio_ids.issubset(known)

    def test_reddit_posts_have_required_fields(self):
        _, reddit = generate_demo_data(num_workouts=0, num_reddit_posts=10)
        required = {"post_id", "title", "created_utc", "score", "url"}
        for post in reddit:
            missing = required - set(post.keys())
            assert not missing, f"Missing fields: {missing}"

    def test_progressive_improvement(self):
        """Verify that later workouts tend to have more splat points."""
        workouts, _ = generate_demo_data(num_workouts=100, num_reddit_posts=0)
        first_quarter = workouts[:25]
        last_quarter = workouts[-25:]
        avg_early = sum(w["splat_points"] for w in first_quarter) / 25
        avg_late = sum(w["splat_points"] for w in last_quarter) / 25
        assert avg_late > avg_early, f"Expected improvement: early={avg_early:.1f}, late={avg_late:.1f}"

    def test_realistic_calorie_range(self):
        workouts, _ = generate_demo_data(num_workouts=50, num_reddit_posts=0)
        for w in workouts:
            assert 200 <= w["calories_burned"] <= 1200, f"Unrealistic calories: {w['calories_burned']}"

    def test_realistic_hr_range(self):
        workouts, _ = generate_demo_data(num_workouts=50, num_reddit_posts=0)
        for w in workouts:
            assert 100 <= w["avg_hr"] <= 200
            assert w["avg_hr"] <= w["max_hr"]


class TestFixtureIO:
    def test_save_and_load_roundtrip(self, tmp_path):
        workouts, reddit = generate_demo_data(num_workouts=5, num_reddit_posts=3)
        wp = tmp_path / "w.json"
        rp = tmp_path / "r.json"

        save_fixtures(workouts, reddit, workouts_path=wp, reddit_path=rp)
        loaded_w, loaded_r = load_fixtures(workouts_path=wp, reddit_path=rp)

        assert len(loaded_w) == 5
        assert len(loaded_r) == 3
        assert loaded_w[0]["performance_summary_id"] == workouts[0]["performance_summary_id"]

    def test_load_missing_files_returns_empty(self, tmp_path):
        w, r = load_fixtures(
            workouts_path=tmp_path / "nonexistent_w.json",
            reddit_path=tmp_path / "nonexistent_r.json",
        )
        assert w == []
        assert r == []


class TestReplayIntoDB:
    def test_replay_workouts(self, db):
        workouts, reddit = generate_demo_data(num_workouts=10, num_reddit_posts=5)
        results = replay_into_db(db, workouts, reddit)

        assert results["workouts"] == 10
        assert results["reddit"] == 5

        row_count = db.execute("SELECT COUNT(*) as c FROM workouts").fetchone()["c"]
        assert row_count == 10

    def test_replay_creates_studios(self, db):
        workouts, _ = generate_demo_data(num_workouts=20, num_reddit_posts=0)
        replay_into_db(db, workouts, [])

        studios = db.execute("SELECT COUNT(*) as c FROM studios").fetchone()["c"]
        assert studios > 0

    def test_replay_creates_telemetry(self, db):
        workouts, _ = generate_demo_data(num_workouts=3, num_reddit_posts=0)
        replay_into_db(db, workouts, [])

        telem_count = db.execute("SELECT COUNT(*) as c FROM telemetry").fetchone()["c"]
        assert telem_count > 100  # ~150 per workout × 3

    def test_replay_creates_treadmill_summary(self, db):
        workouts, _ = generate_demo_data(num_workouts=20, num_reddit_posts=0)
        replay_into_db(db, workouts, [])

        tread_count = db.execute("SELECT COUNT(*) as c FROM treadmill_summary").fetchone()["c"]
        assert tread_count > 0

    def test_replay_creates_rower_summary(self, db):
        workouts, _ = generate_demo_data(num_workouts=20, num_reddit_posts=0)
        replay_into_db(db, workouts, [])

        rower_count = db.execute("SELECT COUNT(*) as c FROM rower_summary").fetchone()["c"]
        assert rower_count > 0

    def test_replay_sets_sync_cursors(self, db):
        workouts, reddit = generate_demo_data(num_workouts=5, num_reddit_posts=5)
        replay_into_db(db, workouts, reddit)

        from orangejuicer.db import get_sync_cursor
        w_cursor = get_sync_cursor(db, "workouts")
        assert w_cursor is not None
        assert w_cursor["full_sync_done"] == 1

        r_cursor = get_sync_cursor(db, "reddit")
        assert r_cursor is not None

    def test_replay_idempotent(self, db):
        """Running replay twice should upsert without duplicates."""
        workouts, reddit = generate_demo_data(num_workouts=5, num_reddit_posts=3)
        replay_into_db(db, workouts, reddit)
        replay_into_db(db, workouts, reddit)

        assert db.execute("SELECT COUNT(*) as c FROM workouts").fetchone()["c"] == 5
        assert db.execute("SELECT COUNT(*) as c FROM reddit_posts").fetchone()["c"] == 3

    def test_fixture_roundtrip_through_db(self, db, tmp_path):
        """Generate → save → load → replay → verify full pipeline."""
        workouts, reddit = generate_demo_data(num_workouts=10, num_reddit_posts=5)
        wp = tmp_path / "w.json"
        rp = tmp_path / "r.json"
        save_fixtures(workouts, reddit, workouts_path=wp, reddit_path=rp)

        loaded_w, loaded_r = load_fixtures(workouts_path=wp, reddit_path=rp)
        results = replay_into_db(db, loaded_w, loaded_r)

        assert results["workouts"] == 10
        assert results["reddit"] == 5

        # Verify stats work on demo data
        stats = db.execute("""
            SELECT AVG(splat_points) as avg_splat, AVG(calories_burned) as avg_cal
            FROM workouts
        """).fetchone()
        assert stats["avg_splat"] > 0
        assert stats["avg_cal"] > 0
