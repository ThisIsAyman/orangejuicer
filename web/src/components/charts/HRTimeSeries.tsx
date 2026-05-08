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
import type { TelemetryPoint } from "../../store/db";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler);

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function HRTimeSeries({ telemetry }: { telemetry: TelemetryPoint[] }) {
  const pts = telemetry.filter((t) => t.hr != null);
  if (pts.length === 0) return <p className="no-data">No HR data</p>;

  return (
    <Line
      data={{
        labels: pts.map((t) => formatTime(t.relative_timestamp)),
        datasets: [
          {
            label: "Heart Rate",
            data: pts.map((t) => t.hr!),
            borderColor: "#ef4444",
            backgroundColor: "rgba(239,68,68,0.1)",
            fill: true,
            tension: 0.2,
            pointRadius: 0,
            borderWidth: 2,
          },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            ticks: { color: "#999", maxTicksLimit: 12 },
            grid: { color: "rgba(255,255,255,0.05)" },
          },
          y: {
            min: 60,
            ticks: { color: "#999" },
            grid: { color: "rgba(255,255,255,0.05)" },
          },
        },
        plugins: { tooltip: { mode: "index", intersect: false } },
      }}
    />
  );
}
