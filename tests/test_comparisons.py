"""Tests for orangejuicer.comparisons"""

from datetime import date

import pytest

from orangejuicer.client import WorkoutRecord
from orangejuicer.comparisons import (
    CommunityStats,
    PersonalStats,
    _estimate_percentile_rank,
    _percentile,
    aggregate_community,
    aggregate_personal,
)
from orangejuicer.reddit import RedditWorkoutPost


def _make_workout(
    splat_points: int = 14,
    calories_burned: int = 450,
    avg_heart_rate: int | None = 145,
    workout_date: date = date(2024, 3, 15),
) -> WorkoutRecord:
    return WorkoutRecord(
        workout_id="test-id",
        workout_date=workout_date,
        coach="Coach A",
        studio_name="Studio X",
        calories_burned=calories_burned,
        splat_points=splat_points,
        step_count=7000,
        active_time_seconds=3600,
        avg_heart_rate=avg_heart_rate,
        max_heart_rate=180,
        zone_time_minutes={"gray": 5, "blue": 10, "green": 20, "orange": 15, "red": 5},
    )


def _make_post(splat_points=None, calories=None, avg_heart_rate=None) -> RedditWorkoutPost:
    return RedditWorkoutPost(
        post_id="p1",
        title="",
        created_utc=0.0,
        score=0,
        url="",
        splat_points=splat_points,
        calories=calories,
        avg_heart_rate=avg_heart_rate,
    )


class TestPercentile:
    def test_empty_list(self):
        assert _percentile([], 50) == 0.0

    def test_median(self):
        assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50) == pytest.approx(3.0)

    def test_100th_percentile(self):
        assert _percentile([1.0, 2.0, 3.0], 100) == 3.0

    def test_0th_percentile(self):
        assert _percentile([1.0, 2.0, 3.0], 0) == 1.0


class TestAggregatePersonal:
    def test_empty_workouts(self):
        stats = aggregate_personal([])
        assert stats.total_workouts == 0
        assert stats.avg_splat_points == 0.0

    def test_single_workout(self):
        stats = aggregate_personal([_make_workout(splat_points=18, calories_burned=500)])
        assert stats.total_workouts == 1
        assert stats.avg_splat_points == 18.0
        assert stats.avg_calories == 500.0

    def test_multiple_workouts_average(self):
        workouts = [
            _make_workout(splat_points=10, calories_burned=400),
            _make_workout(splat_points=20, calories_burned=600),
        ]
        stats = aggregate_personal(workouts)
        assert stats.avg_splat_points == pytest.approx(15.0)
        assert stats.avg_calories == pytest.approx(500.0)

    def test_no_heart_rate_data(self):
        stats = aggregate_personal([_make_workout(avg_heart_rate=None)])
        assert stats.avg_heart_rate is None


class TestAggregateCommunity:
    def test_empty_posts(self):
        stats = aggregate_community([])
        assert stats.total_posts == 0
        assert stats.avg_splat_points is None

    def test_with_splat_data(self):
        posts = [
            _make_post(splat_points=10),
            _make_post(splat_points=20),
            _make_post(splat_points=15),
        ]
        stats = aggregate_community(posts)
        assert stats.avg_splat_points == pytest.approx(15.0)
        assert stats.median_splat_points == pytest.approx(15.0)
        assert 50 in stats.splat_percentiles

    def test_posts_without_stats_ignored(self):
        posts = [_make_post(), _make_post(splat_points=12)]
        stats = aggregate_community(posts)
        assert stats.total_posts == 2
        assert stats.avg_splat_points == 12.0


class TestEstimatePercentileRank:
    def test_empty_percentiles(self):
        rank = _estimate_percentile_rank(15.0, {})
        assert rank == 50.0

    def test_below_lowest_bracket(self):
        pcts = {25: 10.0, 50: 14.0, 75: 18.0}
        rank = _estimate_percentile_rank(5.0, pcts)
        assert rank < 25

    def test_above_highest_bracket(self):
        pcts = {25: 10.0, 50: 14.0, 75: 18.0, 90: 22.0}
        rank = _estimate_percentile_rank(30.0, pcts)
        assert rank >= 90

    def test_at_median_bracket(self):
        pcts = {25: 10.0, 50: 14.0, 75: 18.0}
        rank = _estimate_percentile_rank(14.0, pcts)
        assert rank == pytest.approx(50.0)
