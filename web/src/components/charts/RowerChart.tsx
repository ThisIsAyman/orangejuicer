import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import type { TelemetryPoint } from "../../store/db";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

interface RowerChartProps {
  telemetry: TelemetryPoint[];
  aligned?: boolean;
}

export default function RowerChart({ telemetry, aligned = false }: RowerChartProps) {
  const pts = aligned ? telemetry : telemetry.filter((t) => t.row_speed != null);
  if (pts.length === 0) return <p className="no-data">No rower data</p>;

  const hasSPM = pts.some((t) => t.row_spm != null && t.row_spm > 0);
  const hasHR = aligned && pts.some((t) => t.hr != null);

  return (
    <Line
      data={{
        labels: pts.map((t) => formatTime(t.relative_timestamp)),
        datasets: [
          ...(hasHR
            ? [
                {
                  label: "Heart Rate",
                  data: pts.map((t) => t.hr ?? null),
                  borderColor: "rgba(239,68,68,0.4)",
                  backgroundColor: "rgba(239,68,68,0.05)",
                  fill: true,
                  tension: 0.2,
                  pointRadius: 0,
                  borderWidth: 1.5,
                  yAxisID: "yHR",
                  spanGaps: true,
                },
              ]
            : []),
          {
            label: "Speed",
            data: pts.map((t) => t.row_speed ?? null),
            borderColor: "#3b82f6",
            tension: 0.2,
            pointRadius: 0,
            borderWidth: 2,
            yAxisID: "y",
            spanGaps: false,
          },
          ...(hasSPM
            ? [
                {
                  label: "SPM",
                  data: pts.map((t) => t.row_spm ?? null),
                  borderColor: "#eab308",
                  tension: 0.2,
                  pointRadius: 0,
                  borderWidth: 2,
                  yAxisID: "y1",
                  spanGaps: false,
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
          ...(hasHR
            ? {
                yHR: {
                  type: "linear" as const,
                  position: "right" as const,
                  min: 60,
                  ticks: { color: "rgba(239,68,68,0.5)" },
                  grid: { drawOnChartArea: false },
                  title: { display: true, text: "HR", color: "rgba(239,68,68,0.5)" },
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
