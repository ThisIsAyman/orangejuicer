"""Sync engine — fetches data from OTF API and Reddit, persists to local SQLite.

Supports full history sync (first run) and incremental sync with a lookback
window to catch late updates.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from orangejuicer.auth import OTFAuth
from orangejuicer.db import (
    get_connection,
    get_sync_cursor,
    update_sync_cursor,
    upsert_reddit_post,
    upsert_rower_summary,
    upsert_studio,
    upsert_telemetry_batch,
    upsert_treadmill_summary,
    upsert_workout,
)

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 7


class SyncEngine:
    """Orchestrates syncing OTF and Reddit data into the local database.

    Parameters
    ----------
    conn:
        An open SQLite connection (from :func:`orangejuicer.db.get_connection`).
    auth:
        OTF authentication helper. When *None*, a new instance is created from
        environment variables.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        auth: OTFAuth | None = None,
    ) -> None:
        self.conn = conn
        self._auth = auth or OTFAuth()
        self._otf = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_otf(self) -> None:
        if self._otf is None:
            logger.info("Authenticating with OrangeTheory Fitness API …")
            self._otf = self._auth.get_client()
            logger.info("Authentication successful.")

    # ------------------------------------------------------------------
    # Workout sync
    # ------------------------------------------------------------------

    def sync_workouts(self, force_full: bool = False, capture: bool = False) -> int:
        """Sync workouts from the OTF API into the local database.

        Returns the number of workouts synced.
        """
        self._ensure_otf()

        cursor_info = get_sync_cursor(self.conn, "workouts")
        is_full = force_full or cursor_info is None or not cursor_info["full_sync_done"]

        if is_full:
            start_date = self._get_member_start_date()
            logger.info("Full sync: fetching workouts from %s …", start_date)
        else:
            last_cursor = cursor_info["cursor"]  # type: ignore[index]
            start_date = date.fromisoformat(last_cursor) - timedelta(days=LOOKBACK_DAYS)
            logger.info("Incremental sync: fetching workouts from %s (with %d-day lookback) …",
                        start_date, LOOKBACK_DAYS)

        end_date = date.today()

        # Fetch in 90-day chunks to avoid API pagination limits
        raw_workouts = self._fetch_workouts_chunked(start_date, end_date)

        # Capture raw API responses to JSON fixtures for offline replay
        if capture:
            self._capture_workouts(raw_workouts)

        count = 0
        for raw in raw_workouts:
            try:
                self._persist_workout(raw)
                count += 1
            except Exception:
                psid = getattr(raw, "performance_summary_id", "unknown")
                logger.exception("Failed to persist workout %s", psid)

        update_sync_cursor(
            self.conn,
            "workouts",
            cursor=end_date.isoformat(),
            full_sync_done=is_full,
        )
        self.conn.commit()
        logger.info("Synced %d workouts.", count)
        return count

    def _capture_workouts(self, raw_workouts: list) -> None:
        """Save raw API workout responses as JSON fixtures for offline replay."""
        from orangejuicer.demo import FIXTURES_DIR

        capture_path = FIXTURES_DIR / "captured_workouts.json"
        capture_path.parent.mkdir(parents=True, exist_ok=True)

        captured = []
        for raw in raw_workouts:
            try:
                if hasattr(raw, "model_dump"):
                    captured.append(raw.model_dump())
                else:
                    captured.append({"performance_summary_id": getattr(raw, "performance_summary_id", "unknown")})
            except Exception:
                logger.warning("Could not serialize workout for capture")

        with open(capture_path, "w") as f:
            json.dump(captured, f, indent=2, default=str)
        logger.info("Captured %d workouts to %s", len(captured), capture_path)

    def _get_member_start_date(self) -> date:
        """Get the member's account creation date for full sync."""
        try:
            member = self._otf.member  # type: ignore[union-attr]
            created = getattr(member, "created_date", None)
            if created:
                if isinstance(created, datetime):
                    return created.date()
                if isinstance(created, date):
                    return created
        except Exception:
            logger.warning("Could not determine member start date, using 1 year ago.")
        return date.today() - timedelta(days=365)

    def _fetch_workouts_chunked(
        self,
        start_date: date,
        end_date: date,
        chunk_days: int = 90,
    ) -> list:
        """Fetch workouts in date-range chunks to avoid API pagination limits.

        The OTF bookings API can silently truncate large result sets.  By
        requesting 90-day windows we ensure all workouts are returned even
        for accounts with years of history.
        """
        all_workouts: list = []
        seen_ids: set[str] = set()

        chunk_start = start_date
        while chunk_start <= end_date:
            chunk_end = min(chunk_start + timedelta(days=chunk_days), end_date)
            logger.info("  Fetching %s → %s …", chunk_start, chunk_end)

            try:
                batch = self._otf.workouts.get_workouts(  # type: ignore[union-attr]
                    start_date=chunk_start,
                    end_date=chunk_end,
                )
                for w in batch:
                    psid = getattr(w, "performance_summary_id", None)
                    if psid and psid not in seen_ids:
                        seen_ids.add(psid)
                        all_workouts.append(w)
            except Exception:
                logger.exception("Failed to fetch chunk %s → %s", chunk_start, chunk_end)

            chunk_start = chunk_end + timedelta(days=1)

        logger.info("Fetched %d total workouts across all chunks.", len(all_workouts))
        return all_workouts

    def _persist_workout(self, raw: Any) -> None:
        """Extract all data from a raw OTF Workout and upsert into the database."""
        # Studio
        studio = getattr(raw, "studio", None)
        studio_uuid = None
        if studio and getattr(studio, "studio_uuid", None):
            studio_uuid = studio.studio_uuid
            addr = getattr(studio, "address", None)
            upsert_studio(self.conn, {
                "studio_uuid": studio_uuid,
                "name": getattr(studio, "name", None),
                "phone_number": getattr(studio, "phone_number", None),
                "email": getattr(studio, "email", None),
                "latitude": getattr(studio, "latitude", None),
                "longitude": getattr(studio, "longitude", None),
                "time_zone": getattr(studio, "time_zone", None),
                "address_line1": getattr(addr, "address_line1", None) if addr else None,
                "city": getattr(addr, "city", None) if addr else None,
                "state": getattr(addr, "state", None) if addr else None,
                "postal_code": getattr(addr, "postal_code", None) if addr else None,
                "country": getattr(addr, "country", None) if addr else None,
                "mbo_studio_id": getattr(studio, "mbo_studio_id", None),
            })

        # Workout date from class start time
        otf_class = getattr(raw, "otf_class", None)
        starts_at = getattr(otf_class, "starts_at", None) if otf_class else None
        if isinstance(starts_at, datetime):
            workout_date = starts_at.date().isoformat()
            starts_at_str = starts_at.isoformat()
        else:
            workout_date = date.today().isoformat()
            starts_at_str = None

        # Heart rate
        hr = getattr(raw, "heart_rate", None)

        # Zone time
        ztm = getattr(raw, "zone_time_minutes", None)
        zone_dump = ztm.model_dump() if ztm and hasattr(ztm, "model_dump") else {}

        # Ratings
        class_rating_obj = getattr(raw, "class_rating", None)
        coach_rating_obj = getattr(raw, "coach_rating", None)

        # Coach
        coach_name = getattr(raw, "coach", None)
        if not coach_name and otf_class:
            coach_name = getattr(otf_class, "coach", None)

        # Raw JSON
        raw_json = None
        try:
            if hasattr(raw, "model_dump"):
                raw_json = json.dumps(raw.model_dump(), default=str)
        except Exception:
            pass

        psid = raw.performance_summary_id

        upsert_workout(self.conn, {
            "performance_summary_id": psid,
            "class_history_uuid": getattr(raw, "class_history_uuid", None),
            "booking_id": getattr(raw, "booking_id", None),
            "class_uuid": getattr(raw, "class_uuid", None),
            "workout_date": workout_date,
            "starts_at": starts_at_str,
            "class_name": getattr(otf_class, "name", None) if otf_class else None,
            "class_type": str(getattr(otf_class, "class_type", None)) if otf_class else None,
            "coach_name": coach_name,
            "studio_uuid": studio_uuid,
            "calories_burned": getattr(raw, "calories_burned", None),
            "splat_points": getattr(raw, "splat_points", None),
            "step_count": getattr(raw, "step_count", None),
            "active_time_seconds": getattr(raw, "active_time_seconds", None),
            "avg_hr": getattr(hr, "avg_hr", None) if hr else None,
            "max_hr": getattr(hr, "max_hr", None) if hr else None,
            "peak_hr": getattr(hr, "peak_hr", None) if hr else None,
            "peak_hr_percent": getattr(hr, "peak_hr_percent", None) if hr else None,
            "avg_hr_percent": getattr(hr, "avg_hr_percent", None) if hr else None,
            "zone_gray_min": zone_dump.get("gray"),
            "zone_blue_min": zone_dump.get("blue"),
            "zone_green_min": zone_dump.get("green"),
            "zone_orange_min": zone_dump.get("orange"),
            "zone_red_min": zone_dump.get("red"),
            "class_rating": getattr(class_rating_obj, "value", None) if class_rating_obj else None,
            "coach_rating": getattr(coach_rating_obj, "value", None) if coach_rating_obj else None,
            "raw_json": raw_json,
        })

        # Treadmill summary
        tread = getattr(raw, "treadmill_data", None)
        if tread:
            upsert_treadmill_summary(self.conn, {
                "performance_summary_id": psid,
                "avg_pace": _metric_val(tread, "avg_pace"),
                "avg_speed": _metric_val(tread, "avg_speed"),
                "max_pace": _metric_val(tread, "max_pace"),
                "max_speed": _metric_val(tread, "max_speed"),
                "moving_time": _metric_val(tread, "moving_time"),
                "total_distance": _metric_val(tread, "total_distance"),
                "avg_incline": _metric_val(tread, "avg_incline"),
                "max_incline": _metric_val(tread, "max_incline"),
                "elevation_gained": _metric_val(tread, "elevation_gained"),
            })

        # Rower summary
        rower = getattr(raw, "rower_data", None)
        if rower:
            upsert_rower_summary(self.conn, {
                "performance_summary_id": psid,
                "avg_pace": _metric_val(rower, "avg_pace"),
                "avg_speed": _metric_val(rower, "avg_speed"),
                "max_pace": _metric_val(rower, "max_pace"),
                "max_speed": _metric_val(rower, "max_speed"),
                "moving_time": _metric_val(rower, "moving_time"),
                "total_distance": _metric_val(rower, "total_distance"),
                "avg_cadence": _metric_val(rower, "avg_cadence"),
                "avg_power": _metric_val(rower, "avg_power"),
                "max_cadence": _metric_val(rower, "max_cadence"),
            })

        # Telemetry
        telemetry = getattr(raw, "telemetry", None)
        if telemetry:
            items = getattr(telemetry, "telemetry", None) or []
            if items:
                telem_rows = []
                for item in items:
                    td = getattr(item, "tread_data", None)
                    rd = getattr(item, "row_data", None)
                    ts = getattr(item, "timestamp", None)
                    telem_rows.append({
                        "performance_summary_id": psid,
                        "relative_timestamp": getattr(item, "relative_timestamp", 0),
                        "hr": getattr(item, "hr", None),
                        "agg_splats": getattr(item, "agg_splats", 0),
                        "agg_calories": getattr(item, "agg_calories", 0),
                        "timestamp": ts.isoformat() if isinstance(ts, datetime) else None,
                        "tread_speed": getattr(td, "tread_speed", None) if td else None,
                        "tread_incline": getattr(td, "tread_incline", None) if td else None,
                        "tread_distance": getattr(td, "agg_tread_distance", None) if td else None,
                        "row_speed": getattr(rd, "row_speed", None) if rd else None,
                        "row_spm": getattr(rd, "row_spm", None) if rd else None,
                        "row_distance": getattr(rd, "agg_row_distance", None) if rd else None,
                        "row_pace": getattr(rd, "row_pace", None) if rd else None,
                    })
                upsert_telemetry_batch(self.conn, psid, telem_rows)

    # ------------------------------------------------------------------
    # Reddit sync
    # ------------------------------------------------------------------

    def sync_reddit(self, limit: int = 200) -> int:
        """Sync Reddit posts into the local database.

        Returns the number of posts synced.
        """
        from orangejuicer.reddit import RedditClient, RedditWorkoutPost

        reddit = RedditClient()
        posts = reddit.fetch_workout_posts(limit=limit)

        count = 0
        for post in posts:
            upsert_reddit_post(self.conn, {
                "post_id": post.post_id,
                "title": post.title,
                "raw_text": post.raw_text,
                "created_utc": post.created_utc,
                "score": post.score,
                "url": post.url,
                "splat_points": post.splat_points,
                "calories": post.calories,
                "avg_heart_rate": post.avg_heart_rate,
                "max_heart_rate": post.max_heart_rate,
            })
            count += 1

        update_sync_cursor(
            self.conn,
            "reddit",
            cursor=str(max((p.created_utc for p in posts), default=0)),
            full_sync_done=True,
        )
        self.conn.commit()
        logger.info("Synced %d Reddit posts.", count)
        return count

    # ------------------------------------------------------------------
    # Extras: benchmarks, body composition
    # ------------------------------------------------------------------

    def sync_benchmarks(self) -> int:
        """Sync benchmark/challenge data from the OTF API."""
        from orangejuicer.db import upsert_benchmark

        self._ensure_otf()
        count = 0
        try:
            benchmarks = self._otf.workouts.get_benchmarks()  # type: ignore[union-attr]
            for bm in benchmarks:
                results = getattr(bm, "results", []) or []
                for result in results:
                    upsert_benchmark(self.conn, {
                        "performance_summary_id": getattr(result, "performance_summary_id", None),
                        "challenge_category_id": getattr(bm, "challenge_category_id", None),
                        "challenge_name": getattr(bm, "challenge_name", None),
                        "equipment_id": getattr(bm, "equipment_id", None),
                        "equipment_name": getattr(bm, "equipment_name", None),
                        "result_value": getattr(result, "result", None),
                        "result_unit": getattr(result, "unit", None),
                        "recorded_at": str(getattr(result, "date_created", "")),
                    })
                    count += 1
        except Exception:
            logger.exception("Failed to sync benchmarks")

        if count:
            update_sync_cursor(self.conn, "benchmarks", cursor=date.today().isoformat(), full_sync_done=True)
            self.conn.commit()
        logger.info("Synced %d benchmark results.", count)
        return count

    def sync_body_composition(self) -> int:
        """Sync body composition data from the OTF API."""
        from orangejuicer.db import upsert_body_composition

        self._ensure_otf()
        count = 0
        try:
            records = self._otf.workouts.get_body_composition_list()  # type: ignore[union-attr]
            if not records:
                logger.info("No body composition data available for this account.")
                return 0
            for rec in records:
                raw = None
                try:
                    raw = json.dumps(rec.model_dump(), default=str) if hasattr(rec, "model_dump") else None
                except Exception:
                    pass
                upsert_body_composition(self.conn, {
                    "recorded_at": str(getattr(rec, "scanned_date", getattr(rec, "created_date", ""))),
                    "weight": getattr(rec, "weight", None),
                    "body_fat_pct": getattr(rec, "body_fat_percentage", None),
                    "muscle_mass": getattr(rec, "muscle_mass", None),
                    "bmi": getattr(rec, "bmi", None),
                    "raw_json": raw,
                })
                count += 1
        except AttributeError:
            logger.info("Body composition API not available for this account.")
        except Exception:
            logger.warning("Body composition sync skipped (endpoint unavailable or empty).")

        if count:
            update_sync_cursor(self.conn, "body_composition", cursor=date.today().isoformat(), full_sync_done=True)
            self.conn.commit()
        logger.info("Synced %d body composition records.", count)
        return count

    # ------------------------------------------------------------------
    # Full sync orchestrator
    # ------------------------------------------------------------------

    def sync_all(self, force_full: bool = False, reddit_limit: int = 200, capture: bool = False) -> dict[str, int]:
        """Run all sync operations and return counts per entity."""
        results: dict[str, int] = {}

        results["workouts"] = self.sync_workouts(force_full=force_full, capture=capture)
        results["benchmarks"] = self.sync_benchmarks()
        results["body_composition"] = self.sync_body_composition()

        try:
            results["reddit"] = self.sync_reddit(limit=reddit_limit)
        except Exception:
            logger.exception("Reddit sync failed (non-fatal)")
            results["reddit"] = 0

        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metric_val(parent: Any, attr: str) -> float | None:
    """Extract ``metric_value`` from a nested PerformanceMetric field."""
    metric = getattr(parent, attr, None)
    if metric is None:
        return None
    return getattr(metric, "metric_value", None)
