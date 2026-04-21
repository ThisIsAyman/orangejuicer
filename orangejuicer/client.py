"""Fetch workout and performance data from the OrangeTheory Fitness API.

All network calls are delegated to the ``otf-api`` library.  The methods in
this class normalise the raw API responses into plain Python
:class:`dict` / :class:`list` structures so the rest of the codebase does not
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
        """Build a :class:`WorkoutRecord` from an ``otf-api`` workout object."""
        # ``otf-api`` returns Pydantic models; access attributes defensively.
        def _get(obj: Any, *attrs: str, default: Any = None) -> Any:
            """Try each attribute name in *attrs* on *obj*, returning the first non-None value."""
            for attr in attrs:
                try:
                    val = getattr(obj, attr)
                    if val is not None:
                        return val
                except AttributeError:
                    pass
            return default

        raw_dict: dict[str, Any] = {}
        try:
            raw_dict = data.model_dump() if hasattr(data, "model_dump") else {}
        except Exception:
            pass

        workout_date = _get(data, "class_date")
        if isinstance(workout_date, datetime):
            workout_date = workout_date.date()
        elif not isinstance(workout_date, date):
            workout_date = date.today()

        # Heart-rate zone breakdown (keys: gray, blue, green, orange, red)
        zone_time: dict[str, float] = {}
        hr_zones = _get(data, "heart_rate_zones") or _get(data, "hr_zones")
        if hr_zones and isinstance(hr_zones, dict):
            zone_time = {k: float(v or 0) for k, v in hr_zones.items()}

        return cls(
            workout_id=str(_get(data, "workout_id", "id", default="")),
            workout_date=workout_date,
            coach=str(_get(data, "coach", default="")),
            studio_name=str(getattr(getattr(data, "studio", None), "name", None) or ""),
            calories_burned=int(_get(data, "calories_burned", default=0) or 0),
            splat_points=int(_get(data, "splat_points", default=0) or 0),
            step_count=int(_get(data, "step_count", default=0) or 0),
            active_time_seconds=int(_get(data, "active_time", default=0) or 0),
            avg_heart_rate=_get(data, "avg_heart_rate"),
            max_heart_rate=_get(data, "max_heart_rate"),
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
            Optional date range filter.
        """
        self._ensure_connected()
        logger.info("Fetching up to %d workouts …", limit)

        raw_workouts: list[Any] = []
        try:
            result = self._otf.get_workout_history(limit=limit)  # type: ignore[union-attr]
            if isinstance(result, list):
                raw_workouts = result
            elif hasattr(result, "items"):
                raw_workouts = list(result.items)
            else:
                raw_workouts = list(result)
        except Exception as exc:
            logger.error("Failed to fetch workouts: %s", exc)
            raise

        records = [WorkoutRecord.from_api(w) for w in raw_workouts]

        if start_date:
            records = [r for r in records if r.workout_date >= start_date]
        if end_date:
            records = [r for r in records if r.workout_date <= end_date]

        logger.info("Retrieved %d workout records.", len(records))
        return records

    def get_member_stats(self) -> dict[str, Any]:
        """Return a summary dict with aggregate member statistics."""
        self._ensure_connected()
        try:
            stats = self._otf.get_member_stats()  # type: ignore[union-attr]
            if hasattr(stats, "model_dump"):
                return stats.model_dump()
            return dict(stats) if stats else {}
        except Exception as exc:
            logger.warning("Could not fetch member stats: %s", exc)
            return {}

    def get_performance_summary(self) -> dict[str, Any]:
        """Return lifetime / recent performance summary."""
        self._ensure_connected()
        try:
            summary = self._otf.get_performance_summary()  # type: ignore[union-attr]
            if hasattr(summary, "model_dump"):
                return summary.model_dump()
            return dict(summary) if summary else {}
        except Exception as exc:
            logger.warning("Could not fetch performance summary: %s", exc)
            return {}
