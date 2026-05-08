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

export default function RowerChart({ telemetry }: { telemetry: TelemetryPoint[] }) {
  const pts = telemetry.filter((t) => t.row_speed != null);
  if (pts.length === 0) return <p className="no-data">No rower data</p>;

  const hasSPM = pts.some((t) => t.row_spm != null && t.row_spm > 0);

  return (
    <Line
      data={{
        labels: pts.map((t) => formatTime(t.relative_timestamp)),
        datasets: [
          {
            label: "Speed",
            data: pts.map((t) => t.row_speed!),
            borderColor: "#3b82f6",
            tension: 0.2,
            pointRadius: 0,
            borderWidth: 2,
            yAxisID: "y",
          },
          ...(hasSPM
            ? [
                {
                  label: "SPM",
                  data: pts.map((t) => t.row_spm ?? 0),
                  borderColor: "#eab308",
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
            ticks: { color: "#3b82f6" },
            grid: { color: "rgba(255,255,255,0.05)" },
            title: { display: true, text: "Speed", color: "#3b82f6" },
          },
          ...(hasSPM
            ? {
                y1: {
                  type: "linear" as const,
                  position: "right" as const,
                  ticks: { color: "#eab308" },
                  grid: { drawOnChartArea: false },
                  title: { display: true, text: "SPM", color: "#eab308" },
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
