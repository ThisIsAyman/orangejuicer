import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Filler,
} from "chart.js";
import type { Workout } from "../../store/db";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler);

export default function CalorieTrend({ workouts }: { workouts: Workout[] }) {
  const sorted = [...workouts].sort(
    (a, b) => a.workout_date.localeCompare(b.workout_date)
  );

  return (
    <Line
      data={{
        labels: sorted.map((w) => w.workout_date),
        datasets: [
          {
            label: "Calories",
            data: sorted.map((w) => w.calories_burned ?? 0),
            borderColor: "#f97316",
            backgroundColor: "rgba(249,115,22,0.1)",
            fill: true,
            tension: 0.3,
            pointRadius: sorted.length > 50 ? 0 : 3,
          },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            ticks: { color: "#999", maxTicksLimit: 10 },
            grid: { color: "rgba(255,255,255,0.05)" },
          },
          y: {
            ticks: { color: "#999" },
            grid: { color: "rgba(255,255,255,0.05)" },
          },
        },
        plugins: { tooltip: { mode: "index", intersect: false } },
      }}
    />
  );
}
