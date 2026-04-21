"""Tests for orangejuicer.client"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from orangejuicer.client import OTFClient, WorkoutRecord


def _make_workout_mock(**kwargs):
    """Return a MagicMock that mimics an otf-api workout object."""
    defaults = {
        "workout_id": "abc-123",
        "class_date": date(2024, 3, 15),
        "coach": "Coach Mike",
        "calories_burned": 500,
        "splat_points": 18,
        "step_count": 8000,
        "active_time": 3600,
        "avg_heart_rate": 142,
        "max_heart_rate": 170,
        "heart_rate_zones": {"gray": 5, "blue": 10, "green": 15, "orange": 20, "red": 5},
        "studio": MagicMock(name="Test Studio"),
    }
    defaults.update(kwargs)
    mock = MagicMock()
    for key, val in defaults.items():
        setattr(mock, key, val)
    # model_dump returns a plain dict
    mock.model_dump.return_value = {k: str(v) for k, v in defaults.items() if k != "studio"}
    return mock


class TestWorkoutRecord:
    def test_from_api_basic(self):
        mock = _make_workout_mock()
        record = WorkoutRecord.from_api(mock)
        assert record.workout_id == "abc-123"
        assert record.workout_date == date(2024, 3, 15)
        assert record.calories_burned == 500
        assert record.splat_points == 18
        assert record.avg_heart_rate == 142

    def test_from_api_zone_time(self):
        mock = _make_workout_mock()
        record = WorkoutRecord.from_api(mock)
        assert record.zone_time_minutes == {
            "gray": 5.0,
            "blue": 10.0,
            "green": 15.0,
            "orange": 20.0,
            "red": 5.0,
        }

    def test_from_api_missing_fields_use_defaults(self):
        mock = MagicMock()
        # Simulate missing attributes
        for attr in ("workout_id", "class_date", "coach", "calories_burned", "splat_points",
                     "step_count", "active_time", "avg_heart_rate", "max_heart_rate",
                     "heart_rate_zones", "hr_zones", "studio"):
            setattr(mock, attr, None)
        mock.model_dump.return_value = {}

        record = WorkoutRecord.from_api(mock)
        assert record.calories_burned == 0
        assert record.splat_points == 0
        assert record.zone_time_minutes == {}


class TestOTFClient:
    def _make_client_with_mock_otf(self, workouts):
        mock_otf = MagicMock()
        mock_otf.get_workout_history.return_value = workouts

        auth = MagicMock()
        auth.get_client.return_value = mock_otf

        client = OTFClient(auth=auth)
        return client

    def test_get_workouts_returns_records(self):
        mock_workout = _make_workout_mock()
        client = self._make_client_with_mock_otf([mock_workout])
        records = client.get_workouts(limit=10)
        assert len(records) == 1
        assert isinstance(records[0], WorkoutRecord)

    def test_get_workouts_date_filter(self):
        early = _make_workout_mock(class_date=date(2024, 1, 1))
        late = _make_workout_mock(class_date=date(2024, 6, 1))
        client = self._make_client_with_mock_otf([early, late])

        records = client.get_workouts(start_date=date(2024, 3, 1))
        assert len(records) == 1
        assert records[0].workout_date == date(2024, 6, 1)

    def test_get_workouts_end_date_filter(self):
        early = _make_workout_mock(class_date=date(2024, 1, 1))
        late = _make_workout_mock(class_date=date(2024, 6, 1))
        client = self._make_client_with_mock_otf([early, late])

        records = client.get_workouts(end_date=date(2024, 2, 28))
        assert len(records) == 1
        assert records[0].workout_date == date(2024, 1, 1)

    def test_get_member_stats_handles_error(self):
        mock_otf = MagicMock()
        mock_otf.get_member_stats.side_effect = Exception("API error")

        auth = MagicMock()
        auth.get_client.return_value = mock_otf

        client = OTFClient(auth=auth)
        result = client.get_member_stats()
        assert result == {}
