"""Compare personal OTF data against workout stats scraped from Reddit.

This module provides helper functions to:

* Aggregate personal workout statistics.
* Aggregate community statistics from Reddit posts.
* Generate comparison charts (percentile ranking, overlaid histograms).
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orangejuicer.client import WorkoutRecord
    from orangejuicer.reddit import RedditWorkoutPost

logger = logging.getLogger(__name__)


@dataclass
class PersonalStats:
    """Aggregated statistics for the authenticated member."""

    total_workouts: int
    avg_splat_points: float
    avg_calories: float
    avg_heart_rate: float | None
    median_splat_points: float
    median_calories: float


@dataclass
class CommunityStats:
    """Aggregated statistics derived from Reddit posts."""

    total_posts: int
    avg_splat_points: float | None
    avg_calories: float | None
    median_splat_points: float | None
    median_calories: float | None
    splat_percentiles: dict[int, float]  # e.g. {25: 10, 50: 14, 75: 18}
    calorie_percentiles: dict[int, float]


def _percentile(data: list[float], pct: int) -> float:
    """Return the *pct*-th percentile of *data* (0-100)."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = (pct / 100) * (len(sorted_data) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(sorted_data) - 1)
    return sorted_data[lo] + (sorted_data[hi] - sorted_data[lo]) * (idx - lo)


def aggregate_personal(workouts: list["WorkoutRecord"]) -> PersonalStats:
    """Return :class:`PersonalStats` for the given workout list."""
    if not workouts:
        return PersonalStats(0, 0.0, 0.0, None, 0.0, 0.0)

    splats = [w.splat_points for w in workouts]
    cals = [w.calories_burned for w in workouts]
    hrs = [w.avg_heart_rate for w in workouts if w.avg_heart_rate is not None]

    return PersonalStats(
        total_workouts=len(workouts),
        avg_splat_points=statistics.mean(splats),
        avg_calories=statistics.mean(cals),
        avg_heart_rate=statistics.mean(hrs) if hrs else None,
        median_splat_points=statistics.median(splats),
        median_calories=statistics.median(cals),
    )


def aggregate_community(posts: list["RedditWorkoutPost"]) -> CommunityStats:
    """Return :class:`CommunityStats` for the given Reddit post list."""
    splats = [p.splat_points for p in posts if p.splat_points is not None]
    cals = [p.calories for p in posts if p.calories is not None]

    splat_pcts = {p: _percentile([float(s) for s in splats], p) for p in (25, 50, 75, 90)} if splats else {}
    cal_pcts = {p: _percentile([float(c) for c in cals], p) for p in (25, 50, 75, 90)} if cals else {}

    return CommunityStats(
        total_posts=len(posts),
        avg_splat_points=statistics.mean(splats) if splats else None,
        avg_calories=statistics.mean(cals) if cals else None,
        median_splat_points=statistics.median(splats) if splats else None,
        median_calories=statistics.median(cals) if cals else None,
        splat_percentiles=splat_pcts,
        calorie_percentiles=cal_pcts,
    )


def compare_with_reddit(
    workouts: list["WorkoutRecord"],
    reddit_posts: list["RedditWorkoutPost"],
    output_dir: str | Path | None = None,
) -> list[Path]:
    """Generate comparison charts between personal data and Reddit community data.

    Parameters
    ----------
    workouts:
        Personal OTF workout records.
    reddit_posts:
        Parsed Reddit workout posts.
    output_dir:
        Directory to write chart files.  Defaults to ``./output``.

    Returns
    -------
    list[Path]
        Paths of the generated chart files.
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415

    out = Path(output_dir) if output_dir else Path("output")
    out.mkdir(parents=True, exist_ok=True)

    personal = aggregate_personal(workouts)
    community = aggregate_community(reddit_posts)

    saved: list[Path] = []
    saved.append(_splat_comparison_chart(personal, community, out, plt))
    saved.append(_calorie_comparison_chart(personal, community, out, plt))
    if workouts and reddit_posts:
        saved.append(_percentile_ranking_chart(personal, community, out, plt))

    return saved


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------


def _splat_comparison_chart(
    personal: PersonalStats,
    community: CommunityStats,
    out: Path,
    plt,
) -> Path:
    """Overlaid histogram + personal avg line for splat points."""
    # We approximate a community distribution using the known percentiles.
    # For a proper histogram we'd need the raw data — which we include if
    # the caller passes the original Reddit posts.
    fig, ax = plt.subplots(figsize=(10, 5))

    pcts = community.splat_percentiles
    if pcts:
        # Build representative x-ticks from percentiles
        ptile_vals = list(pcts.values())
        ax.barh(
            [f"p{k}" for k in pcts],
            ptile_vals,
            color="#FF6B35",
            alpha=0.7,
            label="Reddit community",
        )
        if personal.avg_splat_points:
            ax.axvline(
                x=personal.avg_splat_points,
                color="#4A90D9",
                linewidth=2,
                linestyle="--",
                label=f"Your avg ({personal.avg_splat_points:.1f})",
            )
        ax.set_xlabel("Splat Points")
        ax.set_title("Splat Points — You vs. Reddit Community Percentiles", fontsize=13, fontweight="bold")
        ax.legend()
        ax.grid(axis="x", alpha=0.3)
    else:
        ax.text(0.5, 0.5, "No Reddit splat data available", ha="center", va="center")

    path = out / "comparison_splat_points.png"
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    logger.info("Saved comparison chart → %s", path)
    return path


def _calorie_comparison_chart(
    personal: PersonalStats,
    community: CommunityStats,
    out: Path,
    plt,
) -> Path:
    """Bar chart: personal calorie avg vs community percentiles."""
    fig, ax = plt.subplots(figsize=(10, 5))

    pcts = community.calorie_percentiles
    if pcts:
        ptile_vals = list(pcts.values())
        ax.barh(
            [f"p{k}" for k in pcts],
            ptile_vals,
            color="#FF6B35",
            alpha=0.7,
            label="Reddit community",
        )
        if personal.avg_calories:
            ax.axvline(
                x=personal.avg_calories,
                color="#4A90D9",
                linewidth=2,
                linestyle="--",
                label=f"Your avg ({personal.avg_calories:.0f} cal)",
            )
        ax.set_xlabel("Calories")
        ax.set_title("Calories — You vs. Reddit Community Percentiles", fontsize=13, fontweight="bold")
        ax.legend()
        ax.grid(axis="x", alpha=0.3)
    else:
        ax.text(0.5, 0.5, "No Reddit calorie data available", ha="center", va="center")

    path = out / "comparison_calories.png"
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    logger.info("Saved comparison chart → %s", path)
    return path


def _percentile_ranking_chart(
    personal: PersonalStats,
    community: CommunityStats,
    out: Path,
    plt,
) -> Path:
    """Radar / bar chart showing personal percentile ranking in the community."""
    fig, ax = plt.subplots(figsize=(8, 5))

    metrics: list[tuple[str, float, dict[int, float]]] = []
    if personal.avg_splat_points and community.splat_percentiles:
        metrics.append(("Splat Points", personal.avg_splat_points, community.splat_percentiles))
    if personal.avg_calories and community.calorie_percentiles:
        metrics.append(("Calories", personal.avg_calories, community.calorie_percentiles))

    if not metrics:
        ax.text(0.5, 0.5, "Insufficient data for ranking", ha="center", va="center")
    else:
        labels = []
        rankings = []
        for name, personal_val, pcts in metrics:
            # Estimate percentile rank from the community distribution
            rank = _estimate_percentile_rank(personal_val, pcts)
            labels.append(name)
            rankings.append(rank)

        bars = ax.bar(labels, rankings, color="#FF6B35", alpha=0.85)
        ax.set_ylim(0, 100)
        ax.set_ylabel("Estimated Percentile Rank")
        ax.set_title("Your Percentile Rank vs. Reddit Community", fontsize=13, fontweight="bold")
        ax.axhline(y=50, color="gray", linestyle="--", linewidth=1, label="50th percentile")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)

        for bar, rank in zip(bars, rankings):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{rank:.0f}%",
                ha="center",
                va="bottom",
                fontweight="bold",
            )

    path = out / "comparison_percentile_rank.png"
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    logger.info("Saved percentile ranking chart → %s", path)
    return path


def _estimate_percentile_rank(value: float, percentiles: dict[int, float]) -> float:
    """Linearly interpolate *value*'s percentile rank from known percentiles."""
    sorted_pcts = sorted(percentiles.items())  # [(pct, val), ...]
    if not sorted_pcts:
        return 50.0

    # Below lowest known percentile
    if value <= sorted_pcts[0][1]:
        return float(sorted_pcts[0][0]) * value / max(sorted_pcts[0][1], 1)

    # Above highest known percentile
    if value >= sorted_pcts[-1][1]:
        return min(99.0, float(sorted_pcts[-1][0]))

    # Linear interpolation between neighbouring percentile brackets
    for i in range(len(sorted_pcts) - 1):
        lo_pct, lo_val = sorted_pcts[i]
        hi_pct, hi_val = sorted_pcts[i + 1]
        if lo_val <= value <= hi_val:
            if hi_val == lo_val:
                return float(lo_pct)
            t = (value - lo_val) / (hi_val - lo_val)
            return lo_pct + t * (hi_pct - lo_pct)

    return 50.0
