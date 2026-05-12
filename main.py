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


def cmd_stats(args: argparse.Namespace) -> None:
    """Print a summary of your OTF statistics to the console."""
    from orangejuicer.auth import OTFAuth
    from orangejuicer.client import OTFClient
    from orangejuicer.comparisons import aggregate_personal

    auth = OTFAuth()
    client = OTFClient(auth)

    print("\n📊 Fetching your OrangeTheory Fitness data …\n")
    workouts = client.get_workouts(limit=args.limit)

    if not workouts:
        print("No workout data found.")
        return

    stats = aggregate_personal(workouts)
    print(f"  Total workouts      : {stats.total_workouts}")
    print(f"  Avg splat points    : {stats.avg_splat_points:.1f}")
    print(f"  Median splat points : {stats.median_splat_points:.1f}")
    print(f"  Avg calories        : {stats.avg_calories:.0f}")
    print(f"  Median calories     : {stats.median_calories:.0f}")
    if stats.avg_heart_rate:
        print(f"  Avg heart rate      : {stats.avg_heart_rate:.0f} bpm")
    print()

    # Member-level stats from the API
    member_stats = client.get_member_stats()
    if member_stats:
        print("  Member stats from API:")
        for key, val in member_stats.items():
            if val is not None:
                print(f"    {key}: {val}")
    print()


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
    subparsers.add_parser("stats", help="Print summary statistics to the console")
    subparsers.add_parser("visualize", help="Generate workout visualisation charts")
    subparsers.add_parser("compare", help="Compare personal data against Reddit community data")
    subparsers.add_parser("all", help="Run stats + visualize + compare")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    commands = {
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
