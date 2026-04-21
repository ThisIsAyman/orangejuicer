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
    from orangejuicer.auth import OTFAuth
    from orangejuicer.db import get_connection
    from orangejuicer.sync import SyncEngine

    conn = get_connection()
    auth = OTFAuth()
    engine = SyncEngine(conn=conn, auth=auth)

    print("\n🔄 Syncing data to local database …\n")
    results = engine.sync_all(
        force_full=args.full,
        reddit_limit=args.reddit_limit,
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
    """Fetch workouts and generate all visualisation charts."""
    from orangejuicer.auth import OTFAuth
    from orangejuicer.client import OTFClient
    from orangejuicer.visualizations import Visualizer

    auth = OTFAuth()
    client = OTFClient(auth)
    viz = Visualizer(output_dir=args.output_dir)

    print("\n📊 Fetching your OrangeTheory Fitness data …\n")
    workouts = client.get_workouts(limit=args.limit)

    if not workouts:
        print("No workout data found.")
        return

    print(f"  Retrieved {len(workouts)} workouts. Generating charts …\n")
    saved = viz.generate_all(workouts)
    for path in saved:
        print(f"  ✅  {path}")
    print()


def cmd_compare(args: argparse.Namespace) -> None:
    """Fetch personal workouts + Reddit posts and generate comparison charts."""
    from orangejuicer.auth import OTFAuth
    from orangejuicer.client import OTFClient
    from orangejuicer.comparisons import compare_with_reddit
    from orangejuicer.reddit import RedditClient

    auth = OTFAuth()
    client = OTFClient(auth)
    reddit = RedditClient()

    print("\n📊 Fetching your OrangeTheory Fitness data …\n")
    workouts = client.get_workouts(limit=args.limit)
    print(f"  Retrieved {len(workouts)} personal workouts.")

    print("\n🔴 Fetching Reddit workout posts …\n")
    posts = reddit.fetch_workout_posts(limit=args.reddit_limit)
    print(f"  Retrieved {len(posts)} Reddit posts with stats.")

    print("\n📈 Generating comparison charts …\n")
    saved = compare_with_reddit(workouts, posts, output_dir=args.output_dir)
    for path in saved:
        print(f"  ✅  {path}")
    print()


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
    subparsers.add_parser("stats", help="Print summary statistics to the console")
    subparsers.add_parser("visualize", help="Generate workout visualisation charts")
    subparsers.add_parser("compare", help="Compare personal data against Reddit community data")
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
