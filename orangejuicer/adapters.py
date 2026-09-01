"""Adapters to convert SQLite rows into domain dataclasses.

These allow the visualisation and comparison modules to consume data from
the local database without changing their interfaces.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from orangejuicer.client import WorkoutRecord
from orangejuicer.reddit import RedditWorkoutPost


def db_to_workout_records(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
    last_days: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    coach: str | None = None,
    studio: str | None = None,
) -> list[WorkoutRecord]:
    """Query workouts from the local database and return WorkoutRecord objects.

    Parameters
    ----------
    conn:
        Open SQLite connection.
    limit:
        Max rows to return (most recent first).
    last_days:
        Only include workouts from the last N days.
    date_from / date_to:
        ISO date range filter (inclusive).
    coach:
        Filter by coach name (case-insensitive substring match).
    studio:
        Filter by studio name (case-insensitive substring match).
    """
    clauses: list[str] = []
    params: list[str | int] = []

    if last_days is not None:
        clauses.append("workout_date >= date('now', ?)")
        params.append(f"-{last_days} days")
    if date_from:
        clauses.append("workout_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("workout_date <= ?")
        params.append(date_to)
    if coach:
        clauses.append("coach_name LIKE ?")
        params.append(f"%{coach}%")
    if studio:
        clauses.append("w.studio_uuid IN (SELECT studio_uuid FROM studios WHERE name LIKE ?)")
        params.append(f"%{studio}%")

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    sql = f"""
        SELECT
            w.performance_summary_id,
            w.workout_date,
            w.coach_name,
            COALESCE(s.name, '') AS studio_name,
            w.calories_burned,
            w.splat_points,
            w.step_count,
            w.active_time_seconds,
            w.avg_hr,
            w.max_hr,
            w.zone_gray_min,
            w.zone_blue_min,
            w.zone_green_min,
            w.zone_orange_min,
            w.zone_red_min
        FROM workouts w
        LEFT JOIN studios s ON w.studio_uuid = s.studio_uuid
        {where}
        ORDER BY w.workout_date DESC
    """

    if limit:
        sql += " LIMIT ?"
        params.append(limit)

    rows = conn.execute(sql, params).fetchall()

    records: list[WorkoutRecord] = []
    for row in rows:
        zone_time: dict[str, float] = {}
        for zone in ("gray", "blue", "green", "orange", "red"):
            val = row[f"zone_{zone}_min"]
            if val is not None:
                zone_time[zone] = float(val)

        records.append(WorkoutRecord(
            workout_id=row["performance_summary_id"],
            workout_date=date.fromisoformat(row["workout_date"]),
            coach=row["coach_name"] or "",
            studio_name=row["studio_name"] or "",
            calories_burned=row["calories_burned"] or 0,
            splat_points=row["splat_points"] or 0,
            step_count=row["step_count"] or 0,
            active_time_seconds=row["active_time_seconds"] or 0,
            avg_heart_rate=row["avg_hr"],
            max_heart_rate=row["max_hr"],
            zone_time_minutes=zone_time,
        ))

    return records


def db_to_reddit_posts(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
) -> list[RedditWorkoutPost]:
    """Query Reddit posts from the local database and return RedditWorkoutPost objects."""
    sql = "SELECT * FROM reddit_posts ORDER BY created_utc DESC"
    params: list[int] = []
    if limit:
        sql += " LIMIT ?"
        params.append(limit)

    rows = conn.execute(sql, params).fetchall()

    return [
        RedditWorkoutPost(
            post_id=row["post_id"],
            title=row["title"] or "",
            created_utc=float(row["created_utc"] or 0),
            score=row["score"] or 0,
            url=row["url"] or "",
            splat_points=row["splat_points"],
            calories=row["calories"],
            avg_heart_rate=row["avg_heart_rate"],
            max_heart_rate=row["max_heart_rate"],
            raw_text=row["raw_text"] or "",
        )
        for row in rows
    ]
