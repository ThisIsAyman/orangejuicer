"""Generate Strava-compatible TCX files from stored OTF workouts.

OrangeTheory classes have no GPS but do have per-second heart-rate plus
treadmill/rower telemetry. TCX (Training Center XML) carries time, heart rate,
distance, cadence and power without GPS, and Strava imports it as an indoor
activity.

Two outputs per workout:

* :func:`build_tcx` — the ``.tcx`` file. Activity ``Sport="Other"`` (Strava maps
  this to a generic *Workout*), with an embedded ``<Notes>`` metadata block and a
  ``<Creator>`` source tag.
* :func:`build_description` — a short human-readable description. Strava ignores
  the TCX ``<Notes>`` element on upload, so this string is meant to be pasted
  into the activity's description box after uploading (and is written as a
  ``.txt`` sidecar by the ``export --format tcx`` command).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any
from xml.sax.saxutils import escape

MILES_TO_METERS = 1609.34
MPH_TO_MPS = 0.44704
CREATOR_NAME = "OrangeTheory (orangejuicer)"

TCX_NS = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
AX_NS = "http://www.garmin.com/xmlschemas/ActivityExtension/v2"


def _get(row: Any, key: str) -> Any:
    """Read a column/attr from a sqlite3.Row, dict, or object."""
    if row is None:
        return None
    if isinstance(row, Mapping):
        return row.get(key)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return getattr(row, key, None)


def _parse_start(workout: Any) -> datetime:
    """Resolve the workout start as a timezone-aware UTC datetime."""
    starts_at = _get(workout, "starts_at")
    if starts_at:
        try:
            dt = datetime.fromisoformat(str(starts_at).replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    workout_date = _get(workout, "workout_date")
    if workout_date:
        try:
            d = datetime.fromisoformat(str(workout_date)[:10])
            return d.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_description(workout: Any, studio_name: str | None = None) -> str:
    """Human-readable description for pasting into Strava after upload."""
    start = _parse_start(workout)
    class_name = _get(workout, "class_name") or _get(workout, "class_type") or "OrangeTheory"
    coach = _get(workout, "coach_name")
    studio = studio_name if studio_name is not None else _get(workout, "studio_name")
    splats = _get(workout, "splat_points")
    calories = _get(workout, "calories_burned")
    avg_hr = _get(workout, "avg_hr")
    max_hr = _get(workout, "max_hr")

    line1 = f"OrangeTheory — {class_name}"
    parts2 = [start.strftime("%Y-%m-%d %H:%M")]
    if studio:
        parts2.append(f"Studio: {studio}")
    if coach:
        parts2.append(f"Coach: {coach}")
    line2 = "  ·  ".join(parts2)

    parts3 = []
    if splats is not None:
        parts3.append(f"Splats: {splats}")
    if calories is not None:
        parts3.append(f"Calories: {calories}")
    if avg_hr is not None and max_hr is not None:
        parts3.append(f"HR avg/max: {avg_hr}/{max_hr}")

    lines = [line1, line2]
    if parts3:
        lines.append("  ·  ".join(parts3))
    return "\n".join(lines)


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v: Any) -> int | None:
    f = _to_float(v)
    return int(round(f)) if f is not None else None


def _trackpoints(start: datetime, telemetry: Sequence[Any]) -> tuple[list[str], float, int]:
    """Build <Trackpoint> XML, returning (xml_chunks, final_distance_m, last_rel_ts)."""
    chunks: list[str] = []
    tread_m = 0.0  # carry-forward cumulative treadmill metres
    row_m = 0.0  # carry-forward cumulative rower metres
    last_total = 0.0
    last_rel = 0

    for point in telemetry:
        rel = _to_int(_get(point, "relative_timestamp")) or 0
        last_rel = rel
        tp_time = _iso(start + timedelta(seconds=rel))

        tread_d = _to_float(_get(point, "tread_distance"))
        if tread_d is not None:
            tread_m = tread_d * MILES_TO_METERS
        row_d = _to_float(_get(point, "row_distance"))
        if row_d is not None:
            row_m = row_d

        total = tread_m + row_m
        if total < last_total:  # keep DistanceMeters monotonic
            total = last_total
        last_total = total

        body = [f"<Time>{tp_time}</Time>"]
        hr = _to_int(_get(point, "hr"))
        if hr is not None:
            body.append(f"<HeartRateBpm><Value>{hr}</Value></HeartRateBpm>")
        body.append(f"<DistanceMeters>{total:.2f}</DistanceMeters>")

        cadence = _to_int(_get(point, "row_spm"))
        if cadence is not None:
            body.append(f"<Cadence>{cadence}</Cadence>")

        # Per-point speed (m/s): treadmill from mph, rower from pace (sec/500m).
        speed_mps = None
        tread_speed = _to_float(_get(point, "tread_speed"))
        if tread_speed:
            speed_mps = tread_speed * MPH_TO_MPS
        else:
            row_pace = _to_float(_get(point, "row_pace"))
            if row_pace and row_pace > 0:
                speed_mps = 500.0 / row_pace
        if speed_mps is not None:
            body.append(
                f'<Extensions><TPX xmlns="{AX_NS}">'
                f"<Speed>{speed_mps:.3f}</Speed></TPX></Extensions>"
            )

        chunks.append("<Trackpoint>" + "".join(body) + "</Trackpoint>")

    return chunks, last_total, last_rel


def build_tcx(
    workout: Any,
    telemetry: Sequence[Any] | None = None,
    studio_name: str | None = None,
) -> str:
    """Return a complete TCX document (XML string) for one OTF workout."""
    telemetry = list(telemetry or [])
    start = _parse_start(workout)
    start_iso = _iso(start)

    avg_hr = _to_int(_get(workout, "avg_hr"))
    max_hr = _to_int(_get(workout, "max_hr"))
    calories = _to_int(_get(workout, "calories_burned")) or 0
    active_seconds = _to_int(_get(workout, "active_time_seconds"))

    track_chunks, final_distance, last_rel = _trackpoints(start, telemetry)

    if not track_chunks:
        # HR-only fallback: synthesise start/end trackpoints so Strava accepts it.
        total_seconds = active_seconds or 0
        for offset in (0, total_seconds):
            body = [f"<Time>{_iso(start + timedelta(seconds=offset))}</Time>"]
            if avg_hr is not None:
                body.append(f"<HeartRateBpm><Value>{avg_hr}</Value></HeartRateBpm>")
            body.append("<DistanceMeters>0.00</DistanceMeters>")
            track_chunks.append("<Trackpoint>" + "".join(body) + "</Trackpoint>")

    total_time = float(active_seconds if active_seconds else last_rel)

    lap_parts = [
        f"<TotalTimeSeconds>{total_time:.1f}</TotalTimeSeconds>",
        f"<DistanceMeters>{final_distance:.2f}</DistanceMeters>",
        f"<Calories>{calories}</Calories>",
    ]
    if avg_hr is not None:
        lap_parts.append(f"<AverageHeartRateBpm><Value>{avg_hr}</Value></AverageHeartRateBpm>")
    if max_hr is not None:
        lap_parts.append(f"<MaximumHeartRateBpm><Value>{max_hr}</Value></MaximumHeartRateBpm>")
    lap_parts.append("<Intensity>Active</Intensity>")
    lap_parts.append("<TriggerMethod>Manual</TriggerMethod>")
    lap_parts.append("<Track>" + "".join(track_chunks) + "</Track>")

    notes = escape(build_description(workout, studio_name))
    creator = (
        f'<Creator xsi:type="Device_t"><Name>{escape(CREATOR_NAME)}</Name>'
        "<UnitId>0</UnitId><ProductID>0</ProductID></Creator>"
    )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<TrainingCenterDatabase xmlns="{TCX_NS}" '
        f'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<Activities>"
        f'<Activity Sport="Other">'
        f"<Id>{start_iso}</Id>"
        f'<Lap StartTime="{start_iso}">' + "".join(lap_parts) + "</Lap>"
        f"<Notes>{notes}</Notes>"
        f"{creator}"
        "</Activity>"
        "</Activities>"
        "</TrainingCenterDatabase>\n"
    )
