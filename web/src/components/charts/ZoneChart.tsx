import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from "chart.js";
import type { Workout } from "../../store/db";

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

export default function ZoneChart({ workouts }: { workouts: Workout[] }) {
  // Aggregate zone minutes across all workouts
  const zones = {
    gray: workouts.reduce((s, w) => s + (w.zone_gray_min ?? 0), 0),
    blue: workouts.reduce((s, w) => s + (w.zone_blue_min ?? 0), 0),
    green: workouts.reduce((s, w) => s + (w.zone_green_min ?? 0), 0),
    orange: workouts.reduce((s, w) => s + (w.zone_orange_min ?? 0), 0),
    red: workouts.reduce((s, w) => s + (w.zone_red_min ?? 0), 0),
  };

  return (
    <Bar
      data={{
        labels: ["Gray", "Blue", "Green", "Orange", "Red"],
        datasets: [
          {
            label: "Total Minutes",
            data: [zones.gray, zones.blue, zones.green, zones.orange, zones.red],
            backgroundColor: [
              "#9ca3af",
              "#3b82f6",
              "#22c55e",
              "#f97316",
              "#ef4444",
            ],
            borderRadius: 4,
          },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            ticks: { color: "#999" },
            grid: { display: false },
          },
          y: {
            ticks: { color: "#999" },
            grid: { color: "rgba(255,255,255,0.05)" },
          },
        },
        plugins: {
          legend: { display: false },
        },
      }}
    />
  );
}
