"""Demo data generator and fixture loader for orangejuicer.

Provides two modes:
1. **Generate** — create realistic synthetic OTF workout data for development
   and testing without needing API credentials.
2. **Load** — read previously captured or generated JSON fixture files and
   replay them through the normal sync pipeline.

The generated data models realistic OrangeTheory patterns:
- Progressive fitness improvement over time
- Day-of-week workout preferences
- Multiple coaches and studios
- Realistic HR zones, treadmill speeds, rower metrics, and telemetry
- Occasional rest weeks and seasonal variation

All generation is deterministic given the same seed for reproducibility.
"""

from __future__ import annotations

import json
import logging
import math
import random
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from orangejuicer.db import (
    upsert_reddit_post,
    upsert_rower_summary,
    upsert_studio,
    upsert_telemetry_batch,
    upsert_treadmill_summary,
    upsert_workout,
    update_sync_cursor,
)

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
DEMO_WORKOUTS_FILE = FIXTURES_DIR / "demo_workouts.json"
DEMO_REDDIT_FILE = FIXTURES_DIR / "demo_reddit.json"

# ---------------------------------------------------------------------------
# Studios and coaches
# ---------------------------------------------------------------------------

STUDIOS = [
    {
        "studio_uuid": "studio-demo-001",
        "name": "OTF Downtown",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "time_zone": "America/New_York",
        "city": "New York",
        "state": "NY",
        "postal_code": "10001",
        "country": "US",
    },
    {
        "studio_uuid": "studio-demo-002",
        "name": "OTF Midtown",
        "latitude": 40.7549,
        "longitude": -73.9840,
        "time_zone": "America/New_York",
        "city": "New York",
        "state": "NY",
        "postal_code": "10018",
        "country": "US",
    },
    {
        "studio_uuid": "studio-demo-003",
        "name": "OTF Brooklyn Heights",
        "latitude": 40.6960,
        "longitude": -73.9936,
        "time_zone": "America/New_York",
        "city": "Brooklyn",
        "state": "NY",
        "postal_code": "11201",
        "country": "US",
    },
]

COACHES = ["Coach Mike", "Coach Sarah", "Coach Alex", "Coach Jordan", "Coach Taylor"]

CLASS_TYPES = [
    ("Orange 60", "ORANGE_60", 60),
    ("Orange 3G", "ORANGE_3G", 60),
    ("Orange 45", "ORANGE_45", 45),
    ("Lift 45", "LIFT_45", 45),
    ("Orange 90", "ORANGE_90", 90),
]

# Weekday preferences (0=Mon, 6=Sun): higher weight = more likely
_DAY_WEIGHTS = [0.18, 0.12, 0.16, 0.10, 0.14, 0.20, 0.10]

# Class start times (hour, minute)
_START_TIMES = [(6, 0), (7, 15), (9, 0), (12, 0), (16, 30), (17, 45)]


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------


def generate_demo_data(
    num_workouts: int = 200,
    num_reddit_posts: int = 150,
    months_span: int = 18,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate realistic synthetic workout and Reddit data.

    Returns (workouts, reddit_posts) as lists of dicts ready for JSON
    serialization or direct upsert into the database.
    """
    rng = random.Random(seed)
    end_date = date.today()
    start_date = end_date - timedelta(days=months_span * 30)

    workouts = _generate_workouts(rng, start_date, end_date, num_workouts)
    reddit_posts = _generate_reddit_posts(rng, start_date, end_date, num_reddit_posts)

    return workouts, reddit_posts


def _generate_workouts(
    rng: random.Random,
    start_date: date,
    end_date: date,
    target_count: int,
) -> list[dict[str, Any]]:
    """Generate workout records distributed across the date range."""
    total_days = (end_date - start_date).days
    if total_days <= 0:
        return []

    # Generate workout dates with realistic distribution
    workout_dates = _pick_workout_dates(rng, start_date, end_date, target_count)
    workout_dates.sort()

    workouts: list[dict[str, Any]] = []
    for i, wd in enumerate(workout_dates):
        progress = i / max(len(workout_dates) - 1, 1)  # 0→1 over time
        workouts.append(_generate_single_workout(rng, wd, progress, i))

    return workouts


def _pick_workout_dates(
    rng: random.Random,
    start_date: date,
    end_date: date,
    target_count: int,
) -> list[date]:
    """Pick workout dates respecting day-of-week preferences and rest weeks."""
    dates: list[date] = []
    current = start_date

    while current <= end_date and len(dates) < target_count:
        week_start = current
        week_end = min(current + timedelta(days=6), end_date)

        # Occasional rest week (~5% chance)
        if rng.random() < 0.05:
            current = week_end + timedelta(days=1)
            continue

        # Pick 3-5 days this week
        days_this_week = rng.randint(3, 5)
        available = []
        d = week_start
        while d <= week_end:
            available.append(d)
            d += timedelta(days=1)

        weights = [_DAY_WEIGHTS[d.weekday()] for d in available]
        chosen = min(days_this_week, len(available), target_count - len(dates))
        if chosen > 0:
            picked = _weighted_sample(rng, available, weights, chosen)
            dates.extend(picked)

        current = week_end + timedelta(days=1)

    return dates[:target_count]


def _weighted_sample(
    rng: random.Random,
    population: list,
    weights: list[float],
    k: int,
) -> list:
    """Weighted sampling without replacement."""
    pool = list(zip(population, weights))
    result = []
    for _ in range(min(k, len(pool))):
        total = sum(w for _, w in pool)
        if total <= 0:
            break
        r = rng.uniform(0, total)
        cumulative = 0.0
        for idx, (item, w) in enumerate(pool):
            cumulative += w
            if cumulative >= r:
                result.append(item)
                pool.pop(idx)
                break
    return result


def _generate_single_workout(
    rng: random.Random,
    workout_date: date,
    progress: float,
    index: int,
) -> dict[str, Any]:
    """Generate one workout with all associated data."""
    psid = f"demo-ps-{uuid.UUID(int=rng.getrandbits(128))}"

    # Pick class, coach, studio
    class_name, class_type, duration_min = rng.choice(CLASS_TYPES)
    coach = rng.choice(COACHES)
    studio = rng.choice(STUDIOS)
    hour, minute = rng.choice(_START_TIMES)
    starts_at = datetime(workout_date.year, workout_date.month, workout_date.day, hour, minute)

    # Progressive improvement: base stats improve 15-25% over the span
    fitness_factor = 1.0 + progress * 0.20
    # Daily variation ±15%
    daily_var = rng.gauss(1.0, 0.08)

    # HR stats (improve = lower avg relative to max, more time in orange/red)
    max_hr = rng.randint(178, 195)
    avg_hr = int(max_hr * (0.78 - progress * 0.03) * daily_var)
    avg_hr = max(120, min(avg_hr, max_hr - 5))
    peak_hr = min(max_hr, avg_hr + rng.randint(15, 30))

    # Splat points: improve over time (12→22 range)
    base_splats = 12 + progress * 8
    splats = max(0, int(base_splats * daily_var + rng.gauss(0, 2)))

    # Calories: scale with duration and fitness
    cal_per_min = (8.0 + progress * 1.5) * daily_var
    calories = max(200, int(cal_per_min * duration_min + rng.gauss(0, 30)))

    # Zone times (in minutes, should roughly sum to duration)
    zone_times = _generate_zone_times(rng, duration_min, progress, daily_var)

    # Build workout dict
    workout: dict[str, Any] = {
        "performance_summary_id": psid,
        "class_history_uuid": f"demo-ch-{index:04d}",
        "booking_id": f"demo-bk-{index:04d}",
        "class_uuid": f"demo-cl-{class_type.lower()}-{rng.randint(1,50):02d}",
        "workout_date": workout_date.isoformat(),
        "starts_at": starts_at.isoformat(),
        "class_name": class_name,
        "class_type": class_type,
        "coach_name": coach,
        "studio_uuid": studio["studio_uuid"],
        "calories_burned": calories,
        "splat_points": splats,
        "step_count": rng.randint(4000, 12000),
        "active_time_seconds": duration_min * 60 - rng.randint(0, 120),
        "avg_hr": avg_hr,
        "max_hr": max_hr,
        "peak_hr": peak_hr,
        "peak_hr_percent": int(peak_hr / max_hr * 100),
        "avg_hr_percent": int(avg_hr / max_hr * 100),
        **zone_times,
        "class_rating": rng.choice([None, 1, 2, 3, 3]),
        "coach_rating": rng.choice([None, 2, 3, 3, 3]),
        "raw_json": None,  # synthetic — no raw API payload
    }

    # Studio metadata (embedded for fixture portability)
    workout["_studio"] = studio

    # Treadmill summary (~85% of workouts have tread data)
    if rng.random() < 0.85:
        workout["_treadmill"] = _generate_treadmill(rng, progress, daily_var, duration_min)

    # Rower summary (~70% of workouts have rower data)
    if rng.random() < 0.70:
        workout["_rower"] = _generate_rower(rng, progress, daily_var, duration_min)

    # Telemetry (~150 points per workout)
    workout["_telemetry"] = _generate_telemetry(
        rng, psid, starts_at, duration_min, avg_hr, max_hr, progress,
        has_tread="_treadmill" in workout,
        has_rower="_rower" in workout,
    )

    return workout


def _generate_zone_times(
    rng: random.Random,
    duration_min: int,
    progress: float,
    daily_var: float,
) -> dict[str, int]:
    """Generate HR zone times that roughly sum to the class duration."""
    # As fitness improves: less gray/blue, more orange/red
    gray_pct = max(0.03, 0.10 - progress * 0.05)
    blue_pct = max(0.08, 0.18 - progress * 0.06)
    green_pct = 0.28 + rng.gauss(0, 0.03)
    orange_pct = 0.30 + progress * 0.06 + rng.gauss(0, 0.03)
    red_pct = max(0.02, 0.08 + progress * 0.04 + rng.gauss(0, 0.02))

    total = gray_pct + blue_pct + green_pct + orange_pct + red_pct
    return {
        "zone_gray_min": max(0, int(duration_min * gray_pct / total)),
        "zone_blue_min": max(0, int(duration_min * blue_pct / total)),
        "zone_green_min": max(0, int(duration_min * green_pct / total)),
        "zone_orange_min": max(0, int(duration_min * orange_pct / total)),
        "zone_red_min": max(0, int(duration_min * red_pct / total)),
    }


def _generate_treadmill(
    rng: random.Random,
    progress: float,
    daily_var: float,
    duration_min: int,
) -> dict[str, float | None]:
    """Generate treadmill summary metrics."""
    # Speed improves: 5.0 mph base → ~6.5 mph with progress
    base_speed = (5.0 + progress * 1.5) * daily_var
    return {
        "avg_pace": round(60.0 / max(base_speed, 3.0), 2),
        "avg_speed": round(base_speed, 1),
        "max_pace": round(60.0 / max(base_speed + 2.0, 3.0), 2),
        "max_speed": round(base_speed + rng.uniform(1.5, 3.0), 1),
        "moving_time": round(duration_min * 0.4 * 60, 0),  # ~40% of class on tread
        "total_distance": round(base_speed * duration_min * 0.4 / 60, 2),
        "avg_incline": round(rng.uniform(1.0, 4.0), 1),
        "max_incline": round(rng.uniform(6.0, 15.0), 1),
        "elevation_gained": round(rng.uniform(20, 120), 1),
    }


def _generate_rower(
    rng: random.Random,
    progress: float,
    daily_var: float,
    duration_min: int,
) -> dict[str, float | None]:
    """Generate rower summary metrics."""
    base_speed = (2.5 + progress * 0.5) * daily_var
    watts = (120 + progress * 60) * daily_var
    return {
        "avg_pace": round(500 / max(base_speed, 1.0), 1),
        "avg_speed": round(base_speed, 2),
        "max_pace": round(500 / max(base_speed + 0.5, 1.0), 1),
        "max_speed": round(base_speed + rng.uniform(0.3, 1.0), 2),
        "moving_time": round(duration_min * 0.25 * 60, 0),  # ~25% of class on rower
        "total_distance": round(base_speed * duration_min * 0.25 * 60, 0),
        "avg_cadence": round(rng.uniform(24, 32), 1),
        "avg_power": round(watts, 1),
        "max_cadence": round(rng.uniform(32, 42), 1),
    }


def _generate_telemetry(
    rng: random.Random,
    psid: str,
    starts_at: datetime,
    duration_min: int,
    avg_hr: int,
    max_hr: int,
    progress: float,
    has_tread: bool = True,
    has_rower: bool = True,
) -> list[dict[str, Any]]:
    """Generate per-second telemetry data points (~150 per workout)."""
    total_seconds = duration_min * 60
    # Sample every ~24 seconds to get ~150 points for a 60-min class
    interval = max(10, total_seconds // 150)
    points: list[dict[str, Any]] = []

    cumulative_splats = 0
    cumulative_cal = 0
    cumulative_tread_dist = 0.0
    cumulative_row_dist = 0.0

    for t in range(0, total_seconds, interval):
        # Simulate HR curve: warmup → peak → cooldown
        fraction = t / total_seconds
        # Bell-ish curve peaking around 60% through
        hr_curve = math.sin(fraction * math.pi * 0.9) ** 0.6
        hr = int(avg_hr - 20 + (max_hr - avg_hr + 20) * hr_curve + rng.gauss(0, 3))
        hr = max(80, min(hr, max_hr + 5))

        # Accumulate splats (HR > ~84% of max)
        if hr > max_hr * 0.84:
            cumulative_splats += interval / 60
        cumulative_cal += int(hr * 0.05 * interval / 60)

        point: dict[str, Any] = {
            "performance_summary_id": psid,
            "relative_timestamp": t,
            "hr": hr,
            "agg_splats": int(cumulative_splats),
            "agg_calories": cumulative_cal,
            "timestamp": (starts_at + timedelta(seconds=t)).isoformat(),
            "tread_speed": None,
            "tread_incline": None,
            "tread_distance": None,
            "row_speed": None,
            "row_spm": None,
            "row_distance": None,
            "row_pace": None,
        }

        # Tread data for first ~40% of class
        if has_tread and fraction < 0.45:
            speed = (5.0 + progress * 1.5) * (0.6 + fraction * 2.0) + rng.gauss(0, 0.3)
            speed = max(3.0, min(speed, 12.0))
            incline = rng.uniform(0.5, 6.0)
            cumulative_tread_dist += speed * interval / 3600
            point["tread_speed"] = round(speed, 1)
            point["tread_incline"] = round(incline, 1)
            point["tread_distance"] = round(cumulative_tread_dist, 3)

        # Rower data for 45-70% of class
        if has_rower and 0.40 <= fraction <= 0.75:
            row_speed = (2.5 + progress * 0.5) + rng.gauss(0, 0.2)
            spm = rng.uniform(24, 34)
            cumulative_row_dist += row_speed * interval
            point["row_speed"] = round(row_speed, 2)
            point["row_spm"] = round(spm, 1)
            point["row_distance"] = round(cumulative_row_dist, 1)
            point["row_pace"] = int(500 / max(row_speed, 0.5))

        points.append(point)

    return points


# ---------------------------------------------------------------------------
# Reddit post generation
# ---------------------------------------------------------------------------


def _generate_reddit_posts(
    rng: random.Random,
    start_date: date,
    end_date: date,
    count: int,
) -> list[dict[str, Any]]:
    """Generate synthetic Reddit r/orangetheory posts."""
    total_days = (end_date - start_date).days
    posts: list[dict[str, Any]] = []

    templates = [
        "First time hitting {splats} splats! 🎉",
        "Burned {cals} calories today - new PR!",
        "{splats} splats and {cals} calories on a Monday morning 💪",
        "Finally broke {cals} calories in Orange 60!",
        "Is {splats} splat points good for a beginner?",
        "Heart rate maxed at {max_hr} today, feeling accomplished",
        "6 months in and averaging {splats} splats per class",
        "Orange 3G was brutal today: {cals} cals, {splats} splats",
        "Anyone else averaging around {avg_hr} bpm?",
        "New to OTF - got {splats} splats on my 3rd class!",
        "1 year anniversary: went from 8 to {splats} average splats",
        "Today's benchmark: {cals} calories in 60 min",
    ]

    for i in range(count):
        days_offset = rng.randint(0, total_days)
        post_date = start_date + timedelta(days=days_offset)
        created_utc = datetime(
            post_date.year, post_date.month, post_date.day,
            rng.randint(6, 22), rng.randint(0, 59),
        ).timestamp()

        splats = max(0, int(rng.gauss(18, 8)))
        cals = max(200, int(rng.gauss(500, 120)))
        avg_hr = rng.randint(130, 170)
        max_hr = avg_hr + rng.randint(10, 30)

        template = rng.choice(templates)
        title = template.format(splats=splats, cals=cals, avg_hr=avg_hr, max_hr=max_hr)

        posts.append({
            "post_id": f"demo-reddit-{i:04d}",
            "title": title,
            "raw_text": title,
            "created_utc": created_utc,
            "score": max(0, int(rng.gauss(25, 30))),
            "url": f"https://reddit.com/r/orangetheory/comments/demo{i:04d}",
            "splat_points": splats if rng.random() > 0.3 else None,
            "calories": cals if rng.random() > 0.2 else None,
            "avg_heart_rate": avg_hr if rng.random() > 0.5 else None,
            "max_heart_rate": max_hr if rng.random() > 0.6 else None,
        })

    posts.sort(key=lambda p: p["created_utc"])
    return posts


# ---------------------------------------------------------------------------
# Fixture I/O
# ---------------------------------------------------------------------------


def save_fixtures(
    workouts: list[dict[str, Any]],
    reddit_posts: list[dict[str, Any]],
    workouts_path: Path | None = None,
    reddit_path: Path | None = None,
) -> tuple[Path, Path]:
    """Write workout and Reddit data to JSON fixture files."""
    wp = workouts_path or DEMO_WORKOUTS_FILE
    rp = reddit_path or DEMO_REDDIT_FILE
    wp.parent.mkdir(parents=True, exist_ok=True)

    with open(wp, "w") as f:
        json.dump(workouts, f, indent=2, default=str)
    logger.info("Wrote %d workouts to %s", len(workouts), wp)

    with open(rp, "w") as f:
        json.dump(reddit_posts, f, indent=2, default=str)
    logger.info("Wrote %d Reddit posts to %s", len(reddit_posts), rp)

    return wp, rp


def load_fixtures(
    workouts_path: Path | None = None,
    reddit_path: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load workout and Reddit data from JSON fixture files.

    Returns (workouts, reddit_posts). Either list may be empty if
    the corresponding file doesn't exist.
    """
    wp = workouts_path or DEMO_WORKOUTS_FILE
    rp = reddit_path or DEMO_REDDIT_FILE

    workouts: list[dict[str, Any]] = []
    reddit_posts: list[dict[str, Any]] = []

    if wp.exists():
        with open(wp) as f:
            workouts = json.load(f)
        logger.info("Loaded %d workouts from %s", len(workouts), wp)
    else:
        logger.warning("Workout fixtures not found at %s", wp)

    if rp.exists():
        with open(rp) as f:
            reddit_posts = json.load(f)
        logger.info("Loaded %d Reddit posts from %s", len(reddit_posts), rp)
    else:
        logger.warning("Reddit fixtures not found at %s", rp)

    return workouts, reddit_posts


# ---------------------------------------------------------------------------
# Replay into database (same code path as live sync)
# ---------------------------------------------------------------------------


def replay_into_db(
    conn: sqlite3.Connection,
    workouts: list[dict[str, Any]],
    reddit_posts: list[dict[str, Any]],
) -> dict[str, int]:
    """Upsert fixture data into the database using the same functions as live sync.

    Returns counts per entity.
    """
    workout_count = 0
    for w in workouts:
        try:
            _replay_workout(conn, w)
            workout_count += 1
        except Exception:
            psid = w.get("performance_summary_id", "unknown")
            logger.exception("Failed to replay workout %s", psid)

    reddit_count = 0
    for post in reddit_posts:
        try:
            upsert_reddit_post(conn, post)
            reddit_count += 1
        except Exception:
            logger.exception("Failed to replay Reddit post %s", post.get("post_id"))

    # Update sync cursors
    if workout_count:
        update_sync_cursor(conn, "workouts", cursor=date.today().isoformat(), full_sync_done=True)
    if reddit_count:
        cursor_val = str(max((p.get("created_utc", 0) for p in reddit_posts), default=0))
        update_sync_cursor(conn, "reddit", cursor=cursor_val, full_sync_done=True)

    conn.commit()
    return {"workouts": workout_count, "reddit": reddit_count}


def _replay_workout(conn: sqlite3.Connection, w: dict[str, Any]) -> None:
    """Replay a single workout dict (from fixtures) into the database."""
    # Studio
    studio_data = w.get("_studio")
    if studio_data:
        upsert_studio(conn, {
            "studio_uuid": studio_data.get("studio_uuid"),
            "name": studio_data.get("name"),
            "phone_number": studio_data.get("phone_number"),
            "email": studio_data.get("email"),
            "latitude": studio_data.get("latitude"),
            "longitude": studio_data.get("longitude"),
            "time_zone": studio_data.get("time_zone"),
            "address_line1": studio_data.get("address_line1"),
            "city": studio_data.get("city"),
            "state": studio_data.get("state"),
            "postal_code": studio_data.get("postal_code"),
            "country": studio_data.get("country"),
            "mbo_studio_id": studio_data.get("mbo_studio_id"),
        })

    # Workout (extract the DB columns, skip internal keys prefixed with _)
    workout_row = {k: v for k, v in w.items() if not k.startswith("_")}
    upsert_workout(conn, workout_row)

    psid = w["performance_summary_id"]

    # Treadmill
    tread = w.get("_treadmill")
    if tread:
        upsert_treadmill_summary(conn, {"performance_summary_id": psid, **tread})

    # Rower
    rower = w.get("_rower")
    if rower:
        upsert_rower_summary(conn, {"performance_summary_id": psid, **rower})

    # Telemetry
    telemetry = w.get("_telemetry")
    if telemetry:
        upsert_telemetry_batch(conn, psid, telemetry)
