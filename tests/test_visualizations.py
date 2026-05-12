"""Tests for orangejuicer.visualizations"""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from orangejuicer.client import WorkoutRecord
from orangejuicer.visualizations import Visualizer


def _make_workout(
    splat_points: int = 14,
    calories_burned: int = 450,
    avg_heart_rate: int | None = 145,
    workout_date: date = date(2024, 3, 15),
    zone_time: dict | None = None,
) -> WorkoutRecord:
    return WorkoutRecord(
        workout_id="vis-test",
        workout_date=workout_date,
        coach="Coach B",
        studio_name="Studio Y",
        calories_burned=calories_burned,
        splat_points=splat_points,
        step_count=6000,
        active_time_seconds=3000,
        avg_heart_rate=avg_heart_rate,
        max_heart_rate=175,
        zone_time_minutes=zone_time or {"gray": 5, "blue": 10, "green": 20, "orange": 15, "red": 5},
    )


@pytest.fixture()
def viz_in_tmp():
    with tempfile.TemporaryDirectory() as tmp:
        yield Visualizer(output_dir=tmp)


@pytest.fixture()
def sample_workouts():
    return [
        _make_workout(splat_points=12, calories_burned=400, workout_date=date(2024, 1, 10)),
        _make_workout(splat_points=18, calories_burned=550, workout_date=date(2024, 2, 5)),
        _make_workout(splat_points=15, calories_burned=480, workout_date=date(2024, 3, 20)),
    ]


class TestVisualizer:
    def test_splat_points_over_time_creates_file(self, viz_in_tmp, sample_workouts):
        path = viz_in_tmp.splat_points_over_time(sample_workouts)
        assert path.exists()
        assert path.suffix == ".png"

    def test_calories_over_time_creates_file(self, viz_in_tmp, sample_workouts):
        path = viz_in_tmp.calories_over_time(sample_workouts)
        assert path.exists()

    def test_hr_zones_distribution_creates_file(self, viz_in_tmp, sample_workouts):
        path = viz_in_tmp.heart_rate_zones_distribution(sample_workouts)
        assert path.exists()

    def test_workout_frequency_heatmap_creates_file(self, viz_in_tmp, sample_workouts):
        path = viz_in_tmp.workout_frequency_heatmap(sample_workouts)
        assert path.exists()

    def test_interactive_dashboard_creates_html(self, viz_in_tmp, sample_workouts):
        path = viz_in_tmp.interactive_dashboard(sample_workouts)
        assert path.exists()
        assert path.suffix == ".html"

    def test_generate_all_returns_multiple_paths(self, viz_in_tmp, sample_workouts):
        paths = viz_in_tmp.generate_all(sample_workouts)
        assert len(paths) == 5  # 4 static + 1 interactive
        for p in paths:
            assert p.exists()

    def test_generate_all_empty_returns_empty(self, viz_in_tmp):
        paths = viz_in_tmp.generate_all([])
        assert paths == []

    def test_hr_zones_empty_zone_data(self, viz_in_tmp):
        workouts = [_make_workout(zone_time={})]
        path = viz_in_tmp.heart_rate_zones_distribution(workouts)
        assert path.exists()
