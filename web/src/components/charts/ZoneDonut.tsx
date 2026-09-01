import { Doughnut } from "react-chartjs-2";
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from "chart.js";
import type { Workout } from "../../store/db";

ChartJS.register(ArcElement, Tooltip, Legend);

export default function ZoneDonut({ workout }: { workout: Workout }) {
  const data = [
    workout.zone_gray_min ?? 0,
    workout.zone_blue_min ?? 0,
    workout.zone_green_min ?? 0,
    workout.zone_orange_min ?? 0,
    workout.zone_red_min ?? 0,
  ];

  if (data.every((v) => v === 0)) {
    return <p className="no-data">No zone data available</p>;
  }

  return (
    <Doughnut
      data={{
        labels: ["Gray", "Blue", "Green", "Orange", "Red"],
        datasets: [
          {
            data,
            backgroundColor: ["#9ca3af", "#3b82f6", "#22c55e", "#f97316", "#ef4444"],
            borderWidth: 0,
          },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: { color: "#ccc", padding: 12 },
          },
        },
      }}
    />
  );
}
