"""Visualisations for OTF workout data and Reddit community comparisons.

All charts are built with *matplotlib* and optionally exported to a
directory defined by the ``OUTPUT_DIR`` environment variable (default:
``./output``).  Interactive HTML charts are also generated with *plotly*.
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv

load_dotenv()

if TYPE_CHECKING:
    from orangejuicer.client import WorkoutRecord
    from orangejuicer.reddit import RedditWorkoutPost

logger = logging.getLogger(__name__)


def _output_dir() -> Path:
    path = Path(os.environ.get("OUTPUT_DIR", "output"))
    path.mkdir(parents=True, exist_ok=True)
    return path


class Visualizer:
    """Create and save visualisations for OTF workout data.

    Parameters
    ----------
    output_dir:
        Directory where chart files are saved.  Defaults to the value of the
        ``OUTPUT_DIR`` environment variable (or ``./output``).
    """

    def __init__(self, output_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else _output_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save(self, fig, filename: str) -> Path:
        """Save a matplotlib figure and return the saved path."""
        import matplotlib.pyplot as plt  # noqa: PLC0415

        path = self.output_dir / filename
        fig.savefig(path, bbox_inches="tight", dpi=150)
        plt.close(fig)
        logger.info("Saved chart → %s", path)
        return path

    def _save_plotly(self, fig, filename: str) -> Path:
        """Save a Plotly figure as an interactive HTML file."""
        path = self.output_dir / filename
        fig.write_html(str(path))
        logger.info("Saved interactive chart → %s", path)
        return path

    # ------------------------------------------------------------------
    # Individual charts
    # ------------------------------------------------------------------

    def splat_points_over_time(
        self, workouts: list["WorkoutRecord"], filename: str = "splat_points_over_time.png"
    ) -> Path:
        """Line chart of splat points per workout over time."""
        import matplotlib.pyplot as plt  # noqa: PLC0415
        import matplotlib.dates as mdates  # noqa: PLC0415

        sorted_wk = sorted(workouts, key=lambda w: w.workout_date)
        dates = [w.workout_date for w in sorted_wk]
        splats = [w.splat_points for w in sorted_wk]

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(dates, splats, marker="o", linewidth=1.5, markersize=4, color="#FF6B35")
        ax.axhline(y=12, color="gray", linestyle="--", linewidth=1, label="OTF goal (12 splats)")
        if splats:
            avg = sum(splats) / len(splats)
            ax.axhline(y=avg, color="#4A90D9", linestyle=":", linewidth=1.5, label=f"Your avg ({avg:.1f})")
        ax.set_title("Splat Points Over Time", fontsize=14, fontweight="bold")
        ax.set_xlabel("Date")
        ax.set_ylabel("Splat Points")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        fig.autofmt_xdate()
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        return self._save(fig, filename)

    def calories_over_time(
        self, workouts: list["WorkoutRecord"], filename: str = "calories_over_time.png"
    ) -> Path:
        """Bar chart of calories burned per workout."""
        import matplotlib.pyplot as plt  # noqa: PLC0415
        import matplotlib.dates as mdates  # noqa: PLC0415

        sorted_wk = sorted(workouts, key=lambda w: w.workout_date)
        dates = [w.workout_date for w in sorted_wk]
        calories = [w.calories_burned for w in sorted_wk]

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.bar(dates, calories, color="#FF6B35", alpha=0.8, width=1.5)
        if calories:
            avg = sum(calories) / len(calories)
            ax.axhline(y=avg, color="#4A90D9", linestyle="--", linewidth=1.5, label=f"Avg ({avg:.0f} cal)")
        ax.set_title("Calories Burned per Workout", fontsize=14, fontweight="bold")
        ax.set_xlabel("Date")
        ax.set_ylabel("Calories")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        fig.autofmt_xdate()
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        return self._save(fig, filename)

    def heart_rate_zones_distribution(
        self,
        workouts: list["WorkoutRecord"],
        filename: str = "hr_zones_distribution.png",
    ) -> Path:
        """Stacked bar chart showing cumulative time in each HR zone."""
        import matplotlib.pyplot as plt  # noqa: PLC0415

        zone_labels = ["gray", "blue", "green", "orange", "red"]
        zone_colors = ["#9E9E9E", "#2196F3", "#4CAF50", "#FF9800", "#F44336"]
        zone_totals = {z: 0.0 for z in zone_labels}

        for wk in workouts:
            for zone, minutes in wk.zone_time_minutes.items():
                key = zone.lower()
                if key in zone_totals:
                    zone_totals[key] += minutes

        totals = [zone_totals[z] for z in zone_labels]
        total_minutes = sum(totals)

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # Pie / donut chart
        non_zero = [(lbl, t, c) for lbl, t, c in zip(zone_labels, totals, zone_colors) if t > 0]
        if non_zero:
            labels, vals, colors = zip(*non_zero)
            wedge_props = {"width": 0.5}
            axes[0].pie(vals, labels=labels, colors=colors, autopct="%1.1f%%", wedgeprops=wedge_props)
            axes[0].set_title("HR Zone Distribution (all workouts)", fontsize=12, fontweight="bold")
        else:
            axes[0].text(0.5, 0.5, "No zone data available", ha="center", va="center")
            axes[0].set_title("HR Zone Distribution", fontsize=12, fontweight="bold")

        # Bar chart of total minutes
        axes[1].bar(zone_labels, totals, color=zone_colors)
        axes[1].set_title(f"Total Minutes per Zone ({total_minutes:.0f} min total)", fontsize=12, fontweight="bold")
        axes[1].set_xlabel("Zone")
        axes[1].set_ylabel("Minutes")
        axes[1].grid(axis="y", alpha=0.3)

        fig.tight_layout()
        return self._save(fig, filename)

    def workout_frequency_heatmap(
        self,
        workouts: list["WorkoutRecord"],
        filename: str = "workout_frequency_heatmap.png",
    ) -> Path:
        """Calendar-style heatmap of workout frequency by day of week and month."""
        import matplotlib.pyplot as plt  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415

        if not workouts:
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.text(0.5, 0.5, "No workout data", ha="center", va="center")
            return self._save(fig, filename)

        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_counts: Counter[int] = Counter()
        month_counts: Counter[tuple[int, int]] = Counter()

        for wk in workouts:
            day_counts[wk.workout_date.weekday()] += 1
            month_counts[(wk.workout_date.year, wk.workout_date.month)] += 1

        fig, axes = plt.subplots(1, 2, figsize=(14, 4))

        # Day-of-week bar chart
        counts_by_day = [day_counts.get(i, 0) for i in range(7)]
        bars = axes[0].bar(day_names, counts_by_day, color="#FF6B35", alpha=0.85)
        axes[0].set_title("Workouts by Day of Week", fontsize=12, fontweight="bold")
        axes[0].set_ylabel("Number of Workouts")
        axes[0].grid(axis="y", alpha=0.3)
        for bar, count in zip(bars, counts_by_day):
            if count:
                axes[0].text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.1,
                    str(count),
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )

        # Monthly trend
        if month_counts:
            sorted_months = sorted(month_counts.keys())
            labels = [f"{y}-{m:02d}" for y, m in sorted_months]
            values = [month_counts[k] for k in sorted_months]
            axes[1].plot(
                range(len(labels)), values, marker="o", color="#FF6B35", linewidth=2
            )
            step = max(1, len(labels) // 10)
            axes[1].set_xticks(range(0, len(labels), step))
            axes[1].set_xticklabels(labels[::step], rotation=45, ha="right", fontsize=8)
            axes[1].set_title("Workouts per Month", fontsize=12, fontweight="bold")
            axes[1].set_ylabel("Number of Workouts")
            axes[1].grid(alpha=0.3)

        fig.tight_layout()
        return self._save(fig, filename)

    def interactive_dashboard(
        self, workouts: list["WorkoutRecord"], filename: str = "dashboard.html"
    ) -> Path:
        """Generate an interactive Plotly HTML dashboard."""
        import plotly.graph_objects as go  # noqa: PLC0415
        from plotly.subplots import make_subplots  # noqa: PLC0415

        sorted_wk = sorted(workouts, key=lambda w: w.workout_date)
        dates = [w.workout_date for w in sorted_wk]
        splats = [w.splat_points for w in sorted_wk]
        calories = [w.calories_burned for w in sorted_wk]
        avg_hr = [w.avg_heart_rate for w in sorted_wk]

        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            subplot_titles=("Splat Points", "Calories Burned", "Avg Heart Rate"),
            vertical_spacing=0.08,
        )

        otf_orange = "#FF6B35"
        otf_blue = "#4A90D9"

        fig.add_trace(
            go.Scatter(x=dates, y=splats, mode="lines+markers", name="Splat Points", line={"color": otf_orange}),
            row=1, col=1,
        )
        fig.add_trace(
            go.Bar(x=dates, y=calories, name="Calories", marker_color=otf_orange, opacity=0.8),
            row=2, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=avg_hr,
                mode="lines+markers",
                name="Avg HR",
                line={"color": otf_blue},
                connectgaps=False,
            ),
            row=3, col=1,
        )

        fig.update_layout(
            height=750,
            title_text="OrangeTheory Fitness — Personal Dashboard",
            title_font_size=18,
            showlegend=False,
        )
        return self._save_plotly(fig, filename)

    def generate_all(self, workouts: list["WorkoutRecord"]) -> list[Path]:
        """Generate all static charts and the interactive dashboard.

        Returns a list of saved file paths.
        """
        paths: list[Path] = []
        if not workouts:
            logger.warning("No workout data — skipping chart generation.")
            return paths

        paths.append(self.splat_points_over_time(workouts))
        paths.append(self.calories_over_time(workouts))
        paths.append(self.heart_rate_zones_distribution(workouts))
        paths.append(self.workout_frequency_heatmap(workouts))
        paths.append(self.interactive_dashboard(workouts))
        return paths
