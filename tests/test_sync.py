"""Tests for orangejuicer.sync — SyncEngine with mocked API responses."""

from datetime import date, datetime
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from orangejuicer.db import get_connection, get_sync_cursor
from orangejuicer.sync import SyncEngine


@pytest.fixture()
def db(tmp_path):
    conn = get_connection(tmp_path / "test.db")
    yield conn
    conn.close()


def _make_mock_otf_class(starts_at=None, coach="Coach Mike", name="Orange 60"):
    cls = MagicMock()
    cls.starts_at = starts_at or datetime(2024, 3, 15, 9, 0, 0)
    cls.coach = coach
    cls.name = name
    cls.class_type = "ORANGE_60"
    return cls


def _make_mock_studio(uuid="studio-1", name="Downtown"):
    studio = MagicMock()
    studio.studio_uuid = uuid
    studio.name = name
    studio.phone_number = None
    studio.email = None
    studio.latitude = 40.7
    studio.longitude = -74.0
    studio.time_zone = "America/New_York"
    studio.mbo_studio_id = None
    studio.address = None
    return studio


def _make_mock_hr(avg=142, max_hr=170, peak=175, peak_pct=92, avg_pct=75):
    hr = MagicMock()
    hr.avg_hr = avg
    hr.max_hr = max_hr
    hr.peak_hr = peak
    hr.peak_hr_percent = peak_pct
    hr.avg_hr_percent = avg_pct
    return hr


def _make_mock_zone_time():
    ztm = MagicMock()
    ztm.model_dump.return_value = {"gray": 5, "blue": 10, "green": 15, "orange": 20, "red": 5}
    return ztm


def _make_mock_telemetry_item(rel_ts=0, hr_val=140):
    item = MagicMock()
    item.relative_timestamp = rel_ts
    item.hr = hr_val
    item.agg_splats = 1
    item.agg_calories = 10
    item.timestamp = datetime(2024, 3, 15, 9, 0, rel_ts)
    item.tread_data = None
    item.row_data = None
    return item


def _make_mock_telemetry(items=None):
    t = MagicMock()
    t.telemetry = items or [_make_mock_telemetry_item(i * 10, 130 + i) for i in range(5)]
    return t


def _make_mock_workout(**overrides):
    w = MagicMock()
    w.performance_summary_id = overrides.get("psid", "ps-1")
    w.class_history_uuid = "ch-1"
    w.booking_id = "bk-1"
    w.class_uuid = "cl-1"
    w.otf_class = overrides.get("otf_class", _make_mock_otf_class())
    w.studio = overrides.get("studio", _make_mock_studio())
    w.coach = None
    w.calories_burned = overrides.get("calories", 500)
    w.splat_points = overrides.get("splats", 18)
    w.step_count = 8000
    w.active_time_seconds = 3600
    w.heart_rate = overrides.get("heart_rate", _make_mock_hr())
    w.zone_time_minutes = overrides.get("zone_time", _make_mock_zone_time())
    w.class_rating = None
    w.coach_rating = None
    w.treadmill_data = overrides.get("treadmill_data", None)
    w.rower_data = overrides.get("rower_data", None)
    w.telemetry = overrides.get("telemetry", _make_mock_telemetry())
    w.model_dump.return_value = {"performance_summary_id": w.performance_summary_id}
    return w


def _make_engine(db, workouts=None, member_created=None):
    """Create a SyncEngine with a mocked OTF client."""
    mock_otf = MagicMock()
    mock_otf.workouts.get_workouts.return_value = workouts or []
    mock_otf.workouts.get_benchmarks.return_value = []
    mock_otf.workouts.get_body_composition_list.return_value = []

    member = MagicMock()
    member.created_date = member_created or datetime(2023, 1, 1)
    type(mock_otf).member = PropertyMock(return_value=member)

    auth = MagicMock()
    auth.get_client.return_value = mock_otf

    engine = SyncEngine(conn=db, auth=auth)
    return engine


class TestSyncWorkouts:
    def test_full_sync_inserts_workout(self, db):
        workout = _make_mock_workout()
        engine = _make_engine(db, workouts=[workout])

        count = engine.sync_workouts(force_full=True)

        assert count == 1
        row = db.execute("SELECT * FROM workouts WHERE performance_summary_id = 'ps-1'").fetchone()
        assert row is not None
        assert row["calories_burned"] == 500
        assert row["splat_points"] == 18
        assert row["coach_name"] == "Coach Mike"

    def test_full_sync_inserts_studio(self, db):
        workout = _make_mock_workout()
        engine = _make_engine(db, workouts=[workout])
        engine.sync_workouts(force_full=True)

        row = db.execute("SELECT * FROM studios WHERE studio_uuid = 'studio-1'").fetchone()
        assert row is not None
        assert row["name"] == "Downtown"

    def test_full_sync_inserts_telemetry(self, db):
        workout = _make_mock_workout()
        engine = _make_engine(db, workouts=[workout])
        engine.sync_workouts(force_full=True)

        rows = db.execute("SELECT * FROM telemetry WHERE performance_summary_id = 'ps-1'").fetchall()
        assert len(rows) == 5

    def test_sync_sets_cursor(self, db):
        engine = _make_engine(db, workouts=[])
        engine.sync_workouts(force_full=True)

        cursor = get_sync_cursor(db, "workouts")
        assert cursor is not None
        assert cursor["full_sync_done"] == 1
        assert cursor["cursor"] == date.today().isoformat()

    def test_incremental_sync_after_full(self, db):
        workout1 = _make_mock_workout(psid="ps-1")
        engine = _make_engine(db, workouts=[workout1])
        engine.sync_workouts(force_full=True)

        workout2 = _make_mock_workout(psid="ps-2", calories=600)
        engine._otf.workouts.get_workouts.return_value = [workout2]
        count = engine.sync_workouts(force_full=False)

        assert count == 1
        assert db.execute("SELECT COUNT(*) as c FROM workouts").fetchone()["c"] == 2

    def test_upsert_updates_existing(self, db):
        workout = _make_mock_workout()
        engine = _make_engine(db, workouts=[workout])
        engine.sync_workouts(force_full=True)

        workout.calories_burned = 700
        engine._otf.workouts.get_workouts.return_value = [workout]
        engine.sync_workouts(force_full=False)

        row = db.execute("SELECT calories_burned FROM workouts WHERE performance_summary_id = 'ps-1'").fetchone()
        assert row["calories_burned"] == 700

    def test_error_in_one_workout_does_not_stop_others(self, db):
        good = _make_mock_workout(psid="ps-good")
        bad = _make_mock_workout(psid="ps-bad")
        bad.performance_summary_id = None  # will cause an error

        engine = _make_engine(db, workouts=[good, bad])
        count = engine.sync_workouts(force_full=True)

        assert count >= 1  # at least the good one


class TestSyncAll:
    def test_sync_all_returns_counts(self, db):
        workout = _make_mock_workout()
        engine = _make_engine(db, workouts=[workout])

        with patch("orangejuicer.sync.SyncEngine.sync_reddit", return_value=5):
            results = engine.sync_all(force_full=True)

        assert results["workouts"] == 1
        assert results["reddit"] == 5

    def test_reddit_failure_is_nonfatal(self, db):
        engine = _make_engine(db, workouts=[])

        with patch("orangejuicer.sync.SyncEngine.sync_reddit", side_effect=Exception("API down")):
            results = engine.sync_all(force_full=True)

        assert results["reddit"] == 0
        assert "workouts" in results


class TestSyncWithTreadmillRower:
    def test_treadmill_data_persisted(self, db):
        tread = MagicMock()
        for attr in ("avg_pace", "avg_speed", "max_pace", "max_speed",
                      "moving_time", "total_distance", "avg_incline", "max_incline",
                      "elevation_gained"):
            metric = MagicMock()
            metric.metric_value = 5.0
            setattr(tread, attr, metric)

        workout = _make_mock_workout(treadmill_data=tread)
        engine = _make_engine(db, workouts=[workout])
        engine.sync_workouts(force_full=True)

        row = db.execute("SELECT * FROM treadmill_summary WHERE performance_summary_id = 'ps-1'").fetchone()
        assert row is not None
        assert row["total_distance"] == 5.0

    def test_rower_data_persisted(self, db):
        rower = MagicMock()
        for attr in ("avg_pace", "avg_speed", "max_pace", "max_speed",
                      "moving_time", "total_distance", "avg_cadence", "avg_power",
                      "max_cadence"):
            metric = MagicMock()
            metric.metric_value = 3.0
            setattr(rower, attr, metric)

        workout = _make_mock_workout(rower_data=rower)
        engine = _make_engine(db, workouts=[workout])
        engine.sync_workouts(force_full=True)

        row = db.execute("SELECT * FROM rower_summary WHERE performance_summary_id = 'ps-1'").fetchone()
        assert row is not None
        assert row["avg_power"] == 3.0
