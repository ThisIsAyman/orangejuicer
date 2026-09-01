"""Tests for orangejuicer.client"""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from orangejuicer.client import OTFClient, WorkoutRecord


def _make_zone_time_mock(gray=5, blue=10, green=15, orange=20, red=5):
    """Return a mock that mimics a ZoneTimeMinutes Pydantic model."""
    ztm = MagicMock()
    ztm.model_dump.return_value = {
        "gray": gray, "blue": blue, "green": green, "orange": orange, "red": red,
    }
    return ztm


def _make_heart_rate_mock(avg_hr=142, max_hr=170):
    hr = MagicMock()
    hr.avg_hr = avg_hr
    hr.max_hr = max_hr
    return hr


def _make_workout_mock(**kwargs):
    """Return a MagicMock that mimics an otf-api v0.15+ Workout model."""
    otf_class = MagicMock()
    otf_class.starts_at = kwargs.pop("starts_at", datetime(2024, 3, 15, 9, 0))
    otf_class.coach = kwargs.pop("coach", "Coach Mike")

    studio = MagicMock()
    studio.name = kwargs.pop("studio_name", "Test Studio")

    defaults = {
        "performance_summary_id": "abc-123",
        "calories_burned": 500,
        "splat_points": 18,
        "step_count": 8000,
        "active_time_seconds": 3600,
        "heart_rate": _make_heart_rate_mock(),
        "zone_time_minutes": _make_zone_time_mock(),
        "otf_class": otf_class,
        "studio": studio,
    }
    defaults.update(kwargs)

    mock = MagicMock()
    for key, val in defaults.items():
        setattr(mock, key, val)
    mock.model_dump.return_value = {k: str(v) for k, v in defaults.items()
                                     if k not in ("studio", "otf_class", "heart_rate", "zone_time_minutes")}
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
        for attr in ("performance_summary_id", "calories_burned", "splat_points",
                     "step_count", "active_time_seconds", "heart_rate",
                     "zone_time_minutes", "otf_class", "studio", "coach"):
            setattr(mock, attr, None)
        mock.model_dump.return_value = {}

        record = WorkoutRecord.from_api(mock)
        assert record.calories_burned == 0
        assert record.splat_points == 0
        assert record.zone_time_minutes == {}


class TestOTFClient:
    def _make_client_with_mock_otf(self, workouts):
        mock_otf = MagicMock()
        mock_otf.workouts.get_workouts.return_value = workouts

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
        early = _make_workout_mock(starts_at=datetime(2024, 1, 1, 9, 0))
        late = _make_workout_mock(starts_at=datetime(2024, 6, 1, 9, 0))
        client = self._make_client_with_mock_otf([early, late])

        records = client.get_workouts(start_date=date(2024, 3, 1))
        # Verify the date filter was passed to the API
        mock_otf = client._otf
        mock_otf.workouts.get_workouts.assert_called_once_with(
            start_date=date(2024, 3, 1), end_date=None,
        )

    def test_get_workouts_end_date_filter(self):
        early = _make_workout_mock(starts_at=datetime(2024, 1, 1, 9, 0))
        late = _make_workout_mock(starts_at=datetime(2024, 6, 1, 9, 0))
        client = self._make_client_with_mock_otf([early, late])

        records = client.get_workouts(end_date=date(2024, 2, 28))
        mock_otf = client._otf
        mock_otf.workouts.get_workouts.assert_called_once_with(
            start_date=None, end_date=date(2024, 2, 28),
        )

    def test_get_member_stats_handles_error(self):
        mock_otf = MagicMock()
        mock_otf.workouts.get_member_lifetime_stats_in_studio.side_effect = Exception("API error")

        auth = MagicMock()
        auth.get_client.return_value = mock_otf

        client = OTFClient(auth=auth)
        result = client.get_member_stats()
        assert result == {}
