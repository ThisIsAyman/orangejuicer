"""Tests for orangejuicer.reddit"""

import re
from unittest.mock import MagicMock, patch

import pytest

from orangejuicer.reddit import RedditClient, RedditWorkoutPost


def _make_submission(**kwargs):
    defaults = {
        "id": "post123",
        "title": "Today's workout — 18 splat points, 520 calories burned!",
        "selftext": "Avg HR: 148 bpm, Max HR 172",
        "created_utc": 1710000000.0,
        "score": 42,
        "url": "https://reddit.com/r/orangetheory/post123",
    }
    defaults.update(kwargs)
    mock = MagicMock()
    for key, val in defaults.items():
        setattr(mock, key, val)
    return mock


class TestRedditWorkoutPostParsing:
    def test_parses_splat_points(self):
        sub = _make_submission(title="18 splat points today!")
        post = RedditWorkoutPost.from_submission(sub)
        assert post.splat_points == 18

    def test_parses_calories(self):
        sub = _make_submission(title="Burned 540 calories, feeling great")
        post = RedditWorkoutPost.from_submission(sub)
        assert post.calories == 540

    def test_parses_avg_heart_rate_from_body(self):
        sub = _make_submission(
            title="New PR!",
            selftext="Avg heart rate: 155 today, max HR: 178",
        )
        post = RedditWorkoutPost.from_submission(sub)
        assert post.avg_heart_rate == 155

    def test_parses_max_heart_rate(self):
        sub = _make_submission(
            title="Splats: 22",
            selftext="Max heart rate: 182 bpm",
        )
        post = RedditWorkoutPost.from_submission(sub)
        assert post.max_heart_rate == 182

    def test_returns_none_when_no_stats(self):
        sub = _make_submission(title="Just joined OTF!", selftext="So excited to start!")
        post = RedditWorkoutPost.from_submission(sub)
        assert post.splat_points is None
        assert post.calories is None
        assert post.avg_heart_rate is None

    def test_post_metadata(self):
        sub = _make_submission()
        post = RedditWorkoutPost.from_submission(sub)
        assert post.post_id == "post123"
        assert post.score == 42


class TestRedditClient:
    def test_raises_if_no_credentials(self, monkeypatch):
        monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
        monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)

        client = RedditClient(client_id="", client_secret="")
        with pytest.raises(RuntimeError, match="REDDIT_CLIENT_ID"):
            client._ensure_connected()

    def test_raises_import_error_without_praw(self, monkeypatch):
        client = RedditClient(client_id="id", client_secret="secret")
        with patch.dict("sys.modules", {"praw": None}):
            with pytest.raises(ImportError, match="praw"):
                client._ensure_connected()

    def test_fetch_workout_posts_filters_no_stats(self):
        no_stats_sub = _make_submission(
            id="noop",
            title="What do you eat before class?",
            selftext="Just curious.",
        )
        stats_sub = _make_submission(
            id="wk1",
            title="20 splat points, amazing class!",
            selftext="",
        )
        mock_subreddit = MagicMock()
        mock_subreddit.search.return_value = [no_stats_sub, stats_sub]

        mock_reddit = MagicMock()
        mock_reddit.subreddit.return_value = mock_subreddit

        client = RedditClient(client_id="x", client_secret="y")
        client._reddit = mock_reddit  # bypass connection

        posts = client.fetch_workout_posts(limit=10)
        assert len(posts) == 1
        assert posts[0].splat_points == 20
