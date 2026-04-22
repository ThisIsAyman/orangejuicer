#!/usr/bin/env python3
"""orangejuicer — command-line entry point.

Usage examples
--------------
# Fetch workouts and generate all visualisations
python main.py visualize

# Fetch workouts and compare against Reddit data
python main.py compare

# Show summary statistics for your account
python main.py stats

# All-in-one
python main.py all
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("orangejuicer")


def cmd_sync(args: argparse.Namespace) -> None:
    """Sync OTF and Reddit data into the local database."""
    from orangejuicer.db import get_connection

    conn = get_connection()

    if args.demo:
        from orangejuicer.demo import (
            generate_demo_data,
            load_fixtures,
            replay_into_db,
            save_fixtures,
            DEMO_WORKOUTS_FILE,
        )

        if DEMO_WORKOUTS_FILE.exists():
            print("\n🎭 Loading demo data from fixtures …\n")
            workouts, reddit_posts = load_fixtures()
        else:
            print("\n🎭 Generating synthetic demo data …\n")
            workouts, reddit_posts = generate_demo_data()
            save_fixtures(workouts, reddit_posts)

        results = replay_into_db(conn, workouts, reddit_posts)
    else:
        from orangejuicer.auth import OTFAuth
        from orangejuicer.sync import SyncEngine

        auth = OTFAuth()
        engine = SyncEngine(conn=conn, auth=auth)

        print("\n🔄 Syncing data to local database …\n")
        results = engine.sync_all(
            force_full=args.full,
            reddit_limit=args.reddit_limit,
            capture=getattr(args, "capture", False),
        )

    for entity, count in results.items():
        print(f"  {entity}: {count} records synced")
    print(f"\n  Database: {conn.execute('PRAGMA database_list').fetchone()[2]}\n")
    conn.close()


def cmd_stats(args: argparse.Namespace) -> None:
    """Print a summary of your OTF statistics from the local database.

    Falls back to the live API if no local data exists.
    """
    from orangejuicer.db import get_connection

    conn = get_connection()
    row_count = conn.execute("SELECT COUNT(*) as c FROM workouts").fetchone()["c"]

    if row_count == 0:
        conn.close()
        print("\n  No local data found. Run 'python main.py sync' first.\n")
        return

    print(f"\n📊 Statistics from local database ({row_count} workouts)\n")

    stats = conn.execute("""
        SELECT
            COUNT(*)                     AS total_workouts,
            AVG(splat_points)            AS avg_splat,
            AVG(calories_burned)         AS avg_cal,
            AVG(avg_hr)                  AS avg_hr,
            MAX(calories_burned)         AS max_cal,
            MAX(splat_points)            AS max_splat,
            MIN(workout_date)            AS first_workout,
            MAX(workout_date)            AS last_workout,
            COUNT(DISTINCT coach_name)   AS unique_coaches,
            COUNT(DISTINCT studio_uuid)  AS unique_studios
        FROM workouts
    """).fetchone()

    print(f"  Total workouts      : {stats['total_workouts']}")
    print(f"  Date range          : {stats['first_workout']} → {stats['last_workout']}")
    print(f"  Avg splat points    : {stats['avg_splat']:.1f}")
    print(f"  Avg calories        : {stats['avg_cal']:.0f}")
    if stats["avg_hr"]:
        print(f"  Avg heart rate      : {stats['avg_hr']:.0f} bpm")
    print(f"  Best splat session  : {stats['max_splat']}")
    print(f"  Best calorie session: {stats['max_cal']}")
    print(f"  Unique coaches      : {stats['unique_coaches']}")
    print(f"  Unique studios      : {stats['unique_studios']}")

    # Top coaches
    coaches = conn.execute("""
        SELECT coach_name, COUNT(*) as cnt, AVG(splat_points) as avg_splat
        FROM workouts WHERE coach_name IS NOT NULL AND coach_name != ''
        GROUP BY coach_name ORDER BY cnt DESC LIMIT 5
    """).fetchall()
    if coaches:
        print("\n  Top coaches:")
        for c in coaches:
            print(f"    {c['coach_name']}: {c['cnt']} classes (avg {c['avg_splat']:.1f} splats)")

    print()
    conn.close()


def cmd_visualize(args: argparse.Namespace) -> None:
    """Generate all visualisation charts from the local database."""
    from orangejuicer.adapters import db_to_workout_records
    from orangejuicer.db import get_connection
    from orangejuicer.visualizations import Visualizer

    conn = get_connection()
    workouts = db_to_workout_records(conn, limit=args.limit)
    conn.close()

    if not workouts:
        print("\n  No local data found. Run 'python main.py sync' first.\n")
        return

    viz = Visualizer(output_dir=args.output_dir)
    print(f"\n📊 Generating charts from {len(workouts)} local workouts …\n")
    saved = viz.generate_all(workouts)
    for path in saved:
        print(f"  ✅  {path}")
    print()


def cmd_compare(args: argparse.Namespace) -> None:
    """Generate comparison charts from local database data."""
    from orangejuicer.adapters import db_to_reddit_posts, db_to_workout_records
    from orangejuicer.comparisons import compare_with_reddit
    from orangejuicer.db import get_connection

    conn = get_connection()
    workouts = db_to_workout_records(conn, limit=args.limit)
    posts = db_to_reddit_posts(conn, limit=args.reddit_limit)
    conn.close()

    if not workouts:
        print("\n  No local workout data. Run 'python main.py sync' first.\n")
        return
    if not posts:
        print("\n  No Reddit data. Run 'python main.py sync' to fetch Reddit posts.\n")
        return

    print(f"\n📈 Comparing {len(workouts)} workouts against {len(posts)} Reddit posts …\n")
    saved = compare_with_reddit(workouts, posts, output_dir=args.output_dir)
    for path in saved:
        print(f"  ✅  {path}")
    print()


def cmd_workout(args: argparse.Namespace) -> None:
    """Show detailed breakdown for a single workout."""
    from orangejuicer.db import get_connection

    conn = get_connection()

    # Find the workout
    row = conn.execute(
        """SELECT w.*, COALESCE(s.name, '') AS studio_name
           FROM workouts w LEFT JOIN studios s ON w.studio_uuid = s.studio_uuid
           WHERE w.performance_summary_id = ?""",
        (args.workout_id,),
    ).fetchone()

    if not row:
        # Try prefix match
        rows = conn.execute(
            """SELECT w.*, COALESCE(s.name, '') AS studio_name
               FROM workouts w LEFT JOIN studios s ON w.studio_uuid = s.studio_uuid
               WHERE w.performance_summary_id LIKE ?
               LIMIT 5""",
            (f"{args.workout_id}%",),
        ).fetchall()
        if len(rows) == 1:
            row = rows[0]
        elif rows:
            print(f"\n  Multiple matches for '{args.workout_id}':")
            for r in rows:
                print(f"    {r['performance_summary_id']}  {r['workout_date']}  {r['class_name']}")
            conn.close()
            return
        else:
            print(f"\n  Workout '{args.workout_id}' not found.\n")
            conn.close()
            return

    psid = row["performance_summary_id"]
    print(f"\n🏋️ Workout Detail: {psid}\n")
    print(f"  Date        : {row['workout_date']}  ({row['starts_at'] or 'N/A'})")
    print(f"  Class       : {row['class_name'] or 'N/A'} ({row['class_type'] or 'N/A'})")
    print(f"  Coach       : {row['coach_name'] or 'N/A'}")
    print(f"  Studio      : {row['studio_name'] or 'N/A'}")
    print(f"  Calories    : {row['calories_burned'] or 0}")
    print(f"  Splat Points: {row['splat_points'] or 0}")
    print(f"  Steps       : {row['step_count'] or 0}")

    if row["avg_hr"]:
        print(f"\n  Heart Rate:")
        print(f"    Avg: {row['avg_hr']} bpm  |  Max: {row['max_hr'] or 'N/A'} bpm  |  Peak: {row['peak_hr'] or 'N/A'} bpm")

    zones = []
    for zone, color in [("gray", "⬜"), ("blue", "🟦"), ("green", "🟩"), ("orange", "🟧"), ("red", "🟥")]:
        val = row[f"zone_{zone}_min"]
        if val is not None:
            zones.append((color, zone.capitalize(), int(val)))
    if zones:
        print(f"\n  HR Zones (minutes):")
        for color, name, mins in zones:
            bar = "█" * mins
            print(f"    {color} {name:7s}: {mins:3d} min  {bar}")

    # Treadmill
    tread = conn.execute(
        "SELECT * FROM treadmill_summary WHERE performance_summary_id = ?", (psid,)
    ).fetchone()
    if tread:
        print(f"\n  Treadmill:")
        print(f"    Distance: {tread['total_distance'] or 0:.2f} mi  |  Avg speed: {tread['avg_speed'] or 0:.1f} mph  |  Max speed: {tread['max_speed'] or 0:.1f} mph")
        print(f"    Avg incline: {tread['avg_incline'] or 0:.1f}%  |  Max incline: {tread['max_incline'] or 0:.1f}%  |  Elevation: {tread['elevation_gained'] or 0:.0f} ft")

    # Rower
    rower = conn.execute(
        "SELECT * FROM rower_summary WHERE performance_summary_id = ?", (psid,)
    ).fetchone()
    if rower:
        print(f"\n  Rower:")
        print(f"    Distance: {rower['total_distance'] or 0:.0f} m  |  Avg power: {rower['avg_power'] or 0:.0f} W  |  Avg cadence: {rower['avg_cadence'] or 0:.0f} spm")

    # Telemetry summary
    telem_count = conn.execute(
        "SELECT COUNT(*) as c FROM telemetry WHERE performance_summary_id = ?", (psid,)
    ).fetchone()["c"]
    if telem_count > 0:
        telem = conn.execute(
            """SELECT MIN(hr) as min_hr, MAX(hr) as max_hr, AVG(hr) as avg_hr,
                      MAX(agg_calories) as total_cal, MAX(agg_splats) as total_splats
               FROM telemetry WHERE performance_summary_id = ?""",
            (psid,),
        ).fetchone()

        # Mini HR sparkline from telemetry
        hr_rows = conn.execute(
            """SELECT hr FROM telemetry WHERE performance_summary_id = ? AND hr IS NOT NULL
               ORDER BY relative_timestamp""",
            (psid,),
        ).fetchall()
        if hr_rows:
            hrs = [r["hr"] for r in hr_rows]
            sparkline = _hr_sparkline(hrs)
            print(f"\n  Telemetry ({telem_count} data points):")
            print(f"    HR range: {telem['min_hr']}–{telem['max_hr']} bpm (avg {telem['avg_hr']:.0f})")
            print(f"    {sparkline}")

    if row["class_rating"]:
        print(f"\n  Ratings: class={row['class_rating']}/5  coach={row['coach_rating'] or 'N/A'}/5")

    print()
    conn.close()


def _hr_sparkline(values: list[int], width: int = 50) -> str:
    """Render a simple ASCII sparkline of HR values."""
    if not values:
        return ""
    blocks = " ▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = max(mx - mn, 1)

    # Downsample to fit width
    step = max(1, len(values) // width)
    sampled = [values[i] for i in range(0, len(values), step)][:width]

    chars = []
    for v in sampled:
        idx = int((v - mn) / rng * (len(blocks) - 1))
        chars.append(blocks[idx])
    return "    HR: " + "".join(chars)


def cmd_query(args: argparse.Namespace) -> None:
    """Query workouts from the local database with filters."""
    from orangejuicer.adapters import db_to_workout_records
    from orangejuicer.db import get_connection

    conn = get_connection()
    workouts = db_to_workout_records(
        conn,
        limit=args.limit,
        last_days=getattr(args, "last", None),
        date_from=getattr(args, "from_date", None),
        date_to=getattr(args, "to_date", None),
        coach=getattr(args, "coach", None),
        studio=getattr(args, "studio", None),
    )
    conn.close()

    if not workouts:
        print("\n  No workouts match your query.\n")
        return

    print(f"\n📋 {len(workouts)} workouts found\n")

    # Header
    print(f"  {'Date':<12} {'Class':<12} {'Coach':<16} {'Splats':>6} {'Cals':>6} {'Avg HR':>6}  {'Studio'}")
    print(f"  {'─'*12} {'─'*12} {'─'*16} {'─'*6} {'─'*6} {'─'*6}  {'─'*20}")

    for w in workouts:
        hr_str = f"{w.avg_heart_rate:>6}" if w.avg_heart_rate else "     -"
        coach = (w.coach[:14] + "…") if len(w.coach) > 15 else w.coach
        studio = (w.studio_name[:18] + "…") if len(w.studio_name) > 19 else w.studio_name
        print(
            f"  {w.workout_date!s:<12} {'':12} {coach:<16} {w.splat_points:>6} "
            f"{w.calories_burned:>6} {hr_str}  {studio}"
        )

    # Summary
    avg_splats = sum(w.splat_points for w in workouts) / len(workouts)
    avg_cals = sum(w.calories_burned for w in workouts) / len(workouts)
    hrs = [w.avg_heart_rate for w in workouts if w.avg_heart_rate]
    avg_hr = sum(hrs) / len(hrs) if hrs else 0

    print(f"\n  Averages: {avg_splats:.1f} splats  |  {avg_cals:.0f} cal", end="")
    if avg_hr:
        print(f"  |  {avg_hr:.0f} bpm", end="")
    print("\n")


def cmd_export(args: argparse.Namespace) -> None:
    """Export local database to JSON or CSV."""
    import csv
    import io
    import json

    from orangejuicer.db import get_connection

    conn = get_connection()

    # Fetch all workouts with studio names
    rows = conn.execute("""
        SELECT w.*, COALESCE(s.name, '') AS studio_name
        FROM workouts w LEFT JOIN studios s ON w.studio_uuid = s.studio_uuid
        ORDER BY w.workout_date
    """).fetchall()

    if not rows:
        print("\n  No data to export. Run 'python main.py sync' first.\n")
        conn.close()
        return

    if args.format == "json":
        data = []
        for row in rows:
            d = dict(row)
            # Include treadmill/rower/telemetry if requested
            if args.full:
                psid = d["performance_summary_id"]
                tread = conn.execute(
                    "SELECT * FROM treadmill_summary WHERE performance_summary_id = ?", (psid,)
                ).fetchone()
                if tread:
                    d["_treadmill"] = {k: tread[k] for k in tread.keys() if k != "performance_summary_id"}
                rower = conn.execute(
                    "SELECT * FROM rower_summary WHERE performance_summary_id = ?", (psid,)
                ).fetchone()
                if rower:
                    d["_rower"] = {k: rower[k] for k in rower.keys() if k != "performance_summary_id"}
                telem = conn.execute(
                    "SELECT * FROM telemetry WHERE performance_summary_id = ? ORDER BY relative_timestamp",
                    (psid,),
                ).fetchall()
                if telem:
                    d["_telemetry"] = [dict(t) for t in telem]
            data.append(d)

        output = json.dumps(data, indent=2, default=str)

    elif args.format == "csv":
        if not rows:
            conn.close()
            return
        columns = [k for k in rows[0].keys() if not k.startswith("raw_json")]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in columns})
        output = buf.getvalue()

    else:
        print(f"  Unknown format: {args.format}")
        conn.close()
        return

    conn.close()

    if args.output:
        Path(args.output).write_text(output)
        print(f"\n  Exported {len(rows)} workouts to {args.output}\n")
    else:
        print(output)


def cmd_all(args: argparse.Namespace) -> None:
    """Run stats, visualize, and compare all at once."""
    cmd_stats(args)
    cmd_visualize(args)
    cmd_compare(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orangejuicer",
        description="Fetch, visualise, and compare OrangeTheory Fitness data.",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        metavar="DIR",
        help="Directory where charts are saved (default: output/)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        metavar="N",
        help="Maximum number of OTF workouts to retrieve (default: 100)",
    )
    parser.add_argument(
        "--reddit-limit",
        type=int,
        default=200,
        metavar="N",
        help="Maximum number of Reddit posts to fetch (default: 200)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    sync_parser = subparsers.add_parser("sync", help="Sync OTF and Reddit data to local database")
    sync_parser.add_argument(
        "--full",
        action="store_true",
        help="Force a full re-sync (fetch all history, not just new data)",
    )
    sync_parser.add_argument(
        "--demo",
        action="store_true",
        help="Load demo/fixture data instead of hitting the real API",
    )
    sync_parser.add_argument(
        "--capture",
        action="store_true",
        help="Save raw API responses as JSON fixtures for offline replay",
    )
    subparsers.add_parser("stats", help="Print summary statistics to the console")
    subparsers.add_parser("visualize", help="Generate workout visualisation charts")
    subparsers.add_parser("compare", help="Compare personal data against Reddit community data")

    # workout detail
    workout_parser = subparsers.add_parser("workout", help="Show detailed breakdown for one workout")
    workout_parser.add_argument("workout_id", help="Performance summary ID (or prefix)")

    # query
    query_parser = subparsers.add_parser("query", help="Query workouts with filters")
    query_parser.add_argument("--last", type=int, metavar="N", help="Last N days")
    query_parser.add_argument("--from", dest="from_date", metavar="DATE", help="Start date (YYYY-MM-DD)")
    query_parser.add_argument("--to", dest="to_date", metavar="DATE", help="End date (YYYY-MM-DD)")
    query_parser.add_argument("--coach", metavar="NAME", help="Filter by coach name")
    query_parser.add_argument("--studio", metavar="NAME", help="Filter by studio name")
    query_parser.add_argument("--limit", type=int, default=100, metavar="N", help="Max results (default: 100)")

    # export
    export_parser = subparsers.add_parser("export", help="Export data to JSON or CSV")
    export_parser.add_argument("--format", choices=["json", "csv"], default="json", help="Output format (default: json)")
    export_parser.add_argument("--output", "-o", metavar="FILE", help="Write to file instead of stdout")
    export_parser.add_argument("--full", action="store_true", help="Include treadmill, rower, and telemetry data")

    subparsers.add_parser("all", help="Run stats + visualize + compare")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "sync": cmd_sync,
        "stats": cmd_stats,
        "visualize": cmd_visualize,
        "compare": cmd_compare,
        "workout": cmd_workout,
        "query": cmd_query,
        "export": cmd_export,
        "all": cmd_all,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    try:
        handler(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
    except Exception as exc:
        logger.error("Fatal error: %s", type(exc).__name__)
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
