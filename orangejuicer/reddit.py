"""Fetch and parse OrangeTheory workout posts from r/orangetheory on Reddit.

Requires Reddit API credentials in environment variables:

* ``REDDIT_CLIENT_ID``
* ``REDDIT_CLIENT_SECRET``
* ``REDDIT_USER_AGENT``

Create a Reddit API application at https://www.reddit.com/prefs/apps (choose
the *script* type for personal-use bots).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for extracting stats from post titles / bodies
# ---------------------------------------------------------------------------

_RE_SPLAT = re.compile(
    r"(\d+)\s*(?:splat\s*points?|splats?|sp\b)",
    re.IGNORECASE,
)
_RE_CALORIES = re.compile(
    r"(\d+)\s*(?:cal(?:ories?)?)\b",
    re.IGNORECASE,
)
_RE_HR = re.compile(
    r"(?:avg(?:erage)?\s*(?:hr|heart\s*rate)[:\s]+(\d+))|(\d+)\s*(?:bpm|avg\s*hr)",
    re.IGNORECASE,
)
_RE_MAX_HR = re.compile(
    r"(?:max(?:imum)?\s*(?:hr|heart\s*rate)[:\s]+(\d+))|(\d+)\s*(?:max\s*hr)",
    re.IGNORECASE,
)


@dataclass
class RedditWorkoutPost:
    """A parsed Reddit post containing OTF workout stats."""

    post_id: str
    title: str
    created_utc: float
    score: int
    url: str
    splat_points: int | None = None
    calories: int | None = None
    avg_heart_rate: int | None = None
    max_heart_rate: int | None = None
    raw_text: str = field(default="", repr=False)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_int(pattern: re.Pattern[str], text: str) -> int | None:
        m = pattern.search(text)
        if not m:
            return None
        for group in m.groups():
            if group is not None:
                try:
                    return int(group)
                except ValueError:
                    pass
        return None

    @classmethod
    def from_submission(cls, submission: object) -> "RedditWorkoutPost":
        """Build a :class:`RedditWorkoutPost` from a PRAW *Submission* object."""
        title: str = getattr(submission, "title", "")
        body: str = getattr(submission, "selftext", "")
        combined = f"{title}\n{body}"

        return cls(
            post_id=str(getattr(submission, "id", "")),
            title=title,
            created_utc=float(getattr(submission, "created_utc", 0)),
            score=int(getattr(submission, "score", 0)),
            url=str(getattr(submission, "url", "")),
            splat_points=cls._extract_int(_RE_SPLAT, combined),
            calories=cls._extract_int(_RE_CALORIES, combined),
            avg_heart_rate=cls._extract_int(_RE_HR, combined),
            max_heart_rate=cls._extract_int(_RE_MAX_HR, combined),
            raw_text=combined,
        )


class RedditClient:
    """Fetches OTF workout posts from r/orangetheory.

    Parameters
    ----------
    client_id / client_secret / user_agent:
        Reddit API credentials.  When *None* the values are taken from the
        environment variables ``REDDIT_CLIENT_ID``, ``REDDIT_CLIENT_SECRET``,
        and ``REDDIT_USER_AGENT``.
    """

    SUBREDDIT = "orangetheory"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.client_id = client_id or os.environ.get("REDDIT_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("REDDIT_CLIENT_SECRET", "")
        self.user_agent = user_agent or os.environ.get(
            "REDDIT_USER_AGENT", "orangejuicer/0.1.0"
        )
        self._reddit = None

    def _ensure_connected(self) -> None:
        if self._reddit is not None:
            return
        try:
            import praw  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "The 'praw' package is required. Install it with: pip install praw"
            ) from exc

        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "Reddit API credentials are required.  Set REDDIT_CLIENT_ID and "
                "REDDIT_CLIENT_SECRET in your .env file."
            )

        self._reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_agent=self.user_agent,
        )
        logger.info("Connected to Reddit API (read-only).")

    def fetch_workout_posts(
        self,
        limit: int = 200,
        search_query: str = "splat points workout",
    ) -> list[RedditWorkoutPost]:
        """Return a list of parsed workout posts from r/orangetheory.

        Parameters
        ----------
        limit:
            Maximum number of posts to fetch from Reddit.
        search_query:
            Search query used to find relevant posts within the subreddit.
        """
        self._ensure_connected()
        subreddit = self._reddit.subreddit(self.SUBREDDIT)  # type: ignore[union-attr]
        posts: list[RedditWorkoutPost] = []

        logger.info(
            "Searching r/%s for '%s' (limit=%d) …", self.SUBREDDIT, search_query, limit
        )
        try:
            for submission in subreddit.search(search_query, limit=limit, sort="new"):
                post = RedditWorkoutPost.from_submission(submission)
                # Only keep posts that have at least one numeric stat
                if any(
                    v is not None
                    for v in (
                        post.splat_points,
                        post.calories,
                        post.avg_heart_rate,
                    )
                ):
                    posts.append(post)
        except Exception as exc:
            logger.error("Error fetching Reddit posts: %s", exc)
            raise

        logger.info("Found %d posts with parseable stats.", len(posts))
        return posts
