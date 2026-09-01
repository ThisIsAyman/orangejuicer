import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
} from "chart.js";
import type { Workout } from "../../store/db";

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip);

function getWeekLabel(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  const day = d.getDay();
  const monday = new Date(d);
  monday.setDate(d.getDate() - ((day + 6) % 7));
  return monday.toISOString().slice(0, 10);
}

export default function WeeklyChart({ workouts }: { workouts: Workout[] }) {
  const weekMap = new Map<string, number>();
  for (const w of workouts) {
    const week = getWeekLabel(w.workout_date);
    weekMap.set(week, (weekMap.get(week) ?? 0) + 1);
  }

  const weeks = [...weekMap.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .slice(-16);

  return (
    <Bar
      data={{
        labels: weeks.map(([w]) => w),
        datasets: [
          {
            label: "Workouts",
            data: weeks.map(([, c]) => c),
            backgroundColor: "#f97316",
            borderRadius: 4,
          },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            ticks: { color: "#999", maxRotation: 45 },
            grid: { display: false },
          },
          y: {
            ticks: { color: "#999", stepSize: 1 },
            grid: { color: "rgba(255,255,255,0.05)" },
          },
        },
        plugins: { legend: { display: false } },
      }}
    />
  );
}
