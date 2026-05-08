import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from "chart.js";
import type { TelemetryPoint } from "../../store/db";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function TreadChart({ telemetry }: { telemetry: TelemetryPoint[] }) {
  const pts = telemetry.filter((t) => t.tread_speed != null);
  if (pts.length === 0) return <p className="no-data">No treadmill data</p>;

  const hasIncline = pts.some((t) => t.tread_incline != null && t.tread_incline > 0);

  return (
    <Line
      data={{
        labels: pts.map((t) => formatTime(t.relative_timestamp)),
        datasets: [
          {
            label: "Speed (mph)",
            data: pts.map((t) => t.tread_speed!),
            borderColor: "#22c55e",
            backgroundColor: "rgba(34,197,94,0.1)",
            tension: 0.2,
            pointRadius: 0,
            borderWidth: 2,
            yAxisID: "y",
          },
          ...(hasIncline
            ? [
                {
                  label: "Incline (%)",
                  data: pts.map((t) => t.tread_incline ?? 0),
                  borderColor: "#a855f7",
                  backgroundColor: "rgba(168,85,247,0.1)",
                  tension: 0.2,
                  pointRadius: 0,
                  borderWidth: 2,
                  yAxisID: "y1",
                },
              ]
            : []),
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          x: {
            ticks: { color: "#999", maxTicksLimit: 12 },
            grid: { color: "rgba(255,255,255,0.05)" },
          },
          y: {
            type: "linear",
            position: "left",
            ticks: { color: "#22c55e" },
            grid: { color: "rgba(255,255,255,0.05)" },
            title: { display: true, text: "Speed", color: "#22c55e" },
          },
          ...(hasIncline
            ? {
                y1: {
                  type: "linear" as const,
                  position: "right" as const,
                  ticks: { color: "#a855f7" },
                  grid: { drawOnChartArea: false },
                  title: { display: true, text: "Incline", color: "#a855f7" },
                },
              }
            : {}),
        },
        plugins: {
          legend: { labels: { color: "#ccc" } },
        },
      }}
    />
  );
}
