import { useEffect, useState } from "react";
import { db } from "../store/db";
import type { Workout } from "../store/db";
import CalorieTrend from "./charts/CalorieTrend";
import SplatTrend from "./charts/SplatTrend";
import ZoneChart from "./charts/ZoneChart";
import WeeklyChart from "./charts/WeeklyChart";

interface Stats {
  total: number;
  avgCalories: number;
  avgSplats: number;
  totalCalories: number;
  totalSplats: number;
  coaches: number;
  studios: number;
}

function computeStats(workouts: Workout[]): Stats {
  const total = workouts.length;
  const totalCalories = workouts.reduce((s, w) => s + (w.calories_burned ?? 0), 0);
  const totalSplats = workouts.reduce((s, w) => s + (w.splat_points ?? 0), 0);
  const coaches = new Set(workouts.map((w) => w.coach_name).filter(Boolean)).size;
  const studios = new Set(workouts.map((w) => w.studio_name).filter(Boolean)).size;
  return {
    total,
    avgCalories: total ? Math.round(totalCalories / total) : 0,
    avgSplats: total ? Math.round((totalSplats / total) * 10) / 10 : 0,
    totalCalories,
    totalSplats,
    coaches,
    studios,
  };
}

export default function Dashboard() {
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    db.workouts
      .orderBy("workout_date")
      .toArray()
      .then((ws) => {
        setWorkouts(ws);
        setStats(computeStats(ws));
      });
  }, []);

  if (!stats) return <div className="loading">Loading…</div>;

  return (
    <div className="dashboard">
      <div className="stat-cards">
        <div className="stat-card">
          <div className="stat-value">{stats.total}</div>
          <div className="stat-label">Workouts</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.avgCalories}</div>
          <div className="stat-label">Avg Calories</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.avgSplats}</div>
          <div className="stat-label">Avg Splats</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.totalCalories.toLocaleString()}</div>
          <div className="stat-label">Total Calories</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.totalSplats.toLocaleString()}</div>
          <div className="stat-label">Total Splats</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.coaches}</div>
          <div className="stat-label">Coaches</div>
        </div>
      </div>

      <div className="chart-grid">
        <div className="chart-container">
          <h3>Workouts per Week</h3>
          <WeeklyChart workouts={workouts} />
        </div>
        <div className="chart-container">
          <h3>Calorie Trend</h3>
          <CalorieTrend workouts={workouts} />
        </div>
        <div className="chart-container">
          <h3>Splat Point Trend</h3>
          <SplatTrend workouts={workouts} />
        </div>
        <div className="chart-container">
          <h3>Zone Distribution</h3>
          <ZoneChart workouts={workouts} />
        </div>
      </div>
    </div>
  );
}
