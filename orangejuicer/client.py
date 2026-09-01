"""Fetch workout and performance data from the OrangeTheory Fitness API.

All network calls are delegated to the ``otf-api`` library (v0.15.x).  The
methods in this class normalise the API's Pydantic models into plain
:class:`WorkoutRecord` dataclasses so the rest of the codebase does not
depend on ``otf-api`` internals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from orangejuicer.auth import OTFAuth

logger = logging.getLogger(__name__)


@dataclass
class WorkoutRecord:
    """A single OTF workout, normalised from the API response."""

    workout_id: str
    workout_date: date
    coach: str
    studio_name: str
    calories_burned: int
    splat_points: int
    step_count: int
    active_time_seconds: int
    avg_heart_rate: int | None
    max_heart_rate: int | None
    zone_time_minutes: dict[str, float] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, data: Any) -> "WorkoutRecord":
        """Build a :class:`WorkoutRecord` from an ``otf-api`` Workout model."""
        raw_dict: dict[str, Any] = {}
        try:
            raw_dict = data.model_dump() if hasattr(data, "model_dump") else {}
        except Exception:
            pass

        # Date comes from the booking's class start time
        otf_class = getattr(data, "otf_class", None)
        starts_at = getattr(otf_class, "starts_at", None) if otf_class else None
        if isinstance(starts_at, datetime):
            workout_date = starts_at.date()
        elif isinstance(starts_at, date):
            workout_date = starts_at
        else:
            workout_date = date.today()

        # Coach from the class, fallback to workout-level
        coach = ""
        if otf_class and getattr(otf_class, "coach", None):
            coach = otf_class.coach
        elif getattr(data, "coach", None):
            coach = data.coach

        # Studio name
        studio = getattr(data, "studio", None)
        studio_name = getattr(studio, "name", None) or ""

        # Heart-rate zone breakdown
        zone_time: dict[str, float] = {}
        ztm = getattr(data, "zone_time_minutes", None)
        if ztm and hasattr(ztm, "model_dump"):
            zone_time = {k: float(v or 0) for k, v in ztm.model_dump().items()}

        # Heart rate
        hr = getattr(data, "heart_rate", None)
        avg_hr = getattr(hr, "avg_hr", None) if hr else None
        max_hr = getattr(hr, "max_hr", None) if hr else None

        return cls(
            workout_id=str(getattr(data, "performance_summary_id", "") or ""),
            workout_date=workout_date,
            coach=str(coach),
            studio_name=str(studio_name),
            calories_burned=int(getattr(data, "calories_burned", 0) or 0),
            splat_points=int(getattr(data, "splat_points", 0) or 0),
            step_count=int(getattr(data, "step_count", 0) or 0),
            active_time_seconds=int(getattr(data, "active_time_seconds", 0) or 0),
            avg_heart_rate=avg_hr,
            max_heart_rate=max_hr,
            zone_time_minutes=zone_time,
            raw=raw_dict,
        )


class OTFClient:
    """High-level client for fetching OTF data.

    Parameters
    ----------
    auth:
        An :class:`~orangejuicer.auth.OTFAuth` instance.  When *None* a new
        instance is created using environment variables.
    """

    def __init__(self, auth: OTFAuth | None = None) -> None:
        self._auth = auth or OTFAuth()
        self._otf = None  # lazy initialisation

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> None:
        if self._otf is None:
            logger.info("Authenticating with OrangeTheory Fitness API …")
            self._otf = self._auth.get_client()
            logger.info("Authentication successful.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_workouts(
        self,
        limit: int = 100,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[WorkoutRecord]:
        """Return a list of :class:`WorkoutRecord` for the authenticated member.

        Parameters
        ----------
        limit:
            Maximum number of workouts to retrieve (most recent first).
        start_date / end_date:
            Optional date range filter.  When *start_date* is not provided the
            API defaults to 30 days ago; pass an earlier date for more history.
        """
        self._ensure_connected()
        logger.info("Fetching workouts …")

        try:
            raw_workouts = self._otf.workouts.get_workouts(  # type: ignore[union-attr]
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:
            logger.error("Failed to fetch workouts: %s", exc)
            raise

        records = [WorkoutRecord.from_api(w) for w in raw_workouts]

        # Sort most-recent first and honour the limit
        records.sort(key=lambda r: r.workout_date, reverse=True)
        if limit and len(records) > limit:
            records = records[:limit]

        logger.info("Retrieved %d workout records.", len(records))
        return records

    def get_member_stats(self) -> dict[str, Any]:
        """Return lifetime in-studio statistics for the member."""
        self._ensure_connected()
        try:
            stats = self._otf.workouts.get_member_lifetime_stats_in_studio()  # type: ignore[union-attr]
            if hasattr(stats, "model_dump"):
                return stats.model_dump()
            return dict(stats) if stats else {}
        except Exception as exc:
            logger.warning("Could not fetch member stats: %s", exc)
            return {}
