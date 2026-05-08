import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { db } from "../store/db";
import type { Workout, TelemetryPoint, TreadmillSummary, RowerSummary } from "../store/db";
import HRTimeSeries from "./charts/HRTimeSeries";
import TreadChart from "./charts/TreadChart";
import RowerChart from "./charts/RowerChart";
import ZoneDonut from "./charts/ZoneDonut";

export default function WorkoutDetail() {
  const { id } = useParams<{ id: string }>();
  const [workout, setWorkout] = useState<Workout | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetryPoint[]>([]);
  const [tread, setTread] = useState<TreadmillSummary | null>(null);
  const [rower, setRower] = useState<RowerSummary | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!id) return;
    const psid = decodeURIComponent(id);

    Promise.all([
      db.workouts.get(psid),
      db.telemetry.where("performance_summary_id").equals(psid).sortBy("relative_timestamp"),
      db.treadmill.get(psid),
      db.rower.get(psid),
    ]).then(([w, t, tr, ro]) => {
      if (!w) {
        setNotFound(true);
        return;
      }
      setWorkout(w);
      setTelemetry(t);
      setTread(tr ?? null);
      setRower(ro ?? null);
    });
  }, [id]);

  if (notFound) {
    return (
      <div className="workout-detail">
        <Link to="/workouts">← Back</Link>
        <h2>Workout not found</h2>
      </div>
    );
  }

  if (!workout) return <div className="loading">Loading…</div>;

  const mins = workout.active_time_seconds
    ? Math.round(workout.active_time_seconds / 60)
    : null;

  const hasTread = telemetry.some((t) => t.tread_speed != null);
  const hasRower = telemetry.some((t) => t.row_speed != null);

  return (
    <div className="workout-detail">
      <Link to="/workouts" className="back-link">← All Workouts</Link>

      <div className="detail-header">
        <h2>
          {workout.class_name || "Workout"} — {workout.workout_date}
        </h2>
        <p className="detail-meta">
          {workout.coach_name && <span>Coach: {workout.coach_name}</span>}
          {workout.studio_name && <span>Studio: {workout.studio_name}</span>}
          {mins && <span>{mins} min</span>}
        </p>
      </div>

      <div className="stat-cards">
        <div className="stat-card accent-orange">
          <div className="stat-value">{workout.calories_burned ?? "—"}</div>
          <div className="stat-label">Calories</div>
        </div>
        <div className="stat-card accent-orange">
          <div className="stat-value">{workout.splat_points ?? "—"}</div>
          <div className="stat-label">Splat Points</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{workout.avg_hr ?? "—"}</div>
          <div className="stat-label">Avg HR</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{workout.max_hr ?? "—"}</div>
          <div className="stat-label">Max HR</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{workout.step_count?.toLocaleString() ?? "—"}</div>
          <div className="stat-label">Steps</div>
        </div>
      </div>

      <div className="chart-grid">
        <div className="chart-container">
          <h3>Heart Rate Zones</h3>
          <ZoneDonut workout={workout} />
        </div>

        {telemetry.length > 0 && (
          <div className="chart-container wide">
            <h3>Heart Rate</h3>
            <HRTimeSeries telemetry={telemetry} />
          </div>
        )}

        {hasTread && (
          <div className="chart-container wide">
            <h3>Treadmill</h3>
            <TreadChart telemetry={telemetry} />
          </div>
        )}

        {hasRower && (
          <div className="chart-container wide">
            <h3>Rower</h3>
            <RowerChart telemetry={telemetry} />
          </div>
        )}
      </div>

      {(tread || rower) && (
        <div className="equipment-summary">
          {tread && (
            <div className="equip-card">
              <h3>🏃 Treadmill Summary</h3>
              <table>
                <tbody>
                  {tread.total_distance != null && (
                    <tr><td>Distance</td><td>{tread.total_distance.toFixed(2)} mi</td></tr>
                  )}
                  {tread.avg_speed != null && (
                    <tr><td>Avg Speed</td><td>{tread.avg_speed.toFixed(1)} mph</td></tr>
                  )}
                  {tread.max_speed != null && (
                    <tr><td>Max Speed</td><td>{tread.max_speed.toFixed(1)} mph</td></tr>
                  )}
                  {tread.avg_incline != null && (
                    <tr><td>Avg Incline</td><td>{tread.avg_incline.toFixed(1)}%</td></tr>
                  )}
                  {tread.elevation_gained != null && (
                    <tr><td>Elevation</td><td>{tread.elevation_gained.toFixed(0)} ft</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
          {rower && (
            <div className="equip-card">
              <h3>🚣 Rower Summary</h3>
              <table>
                <tbody>
                  {rower.total_distance != null && (
                    <tr><td>Distance</td><td>{rower.total_distance.toFixed(0)} m</td></tr>
                  )}
                  {rower.avg_speed != null && (
                    <tr><td>Avg Speed</td><td>{rower.avg_speed.toFixed(1)}</td></tr>
                  )}
                  {rower.avg_cadence != null && (
                    <tr><td>Avg SPM</td><td>{rower.avg_cadence.toFixed(0)}</td></tr>
                  )}
                  {rower.avg_power != null && (
                    <tr><td>Avg Power</td><td>{rower.avg_power.toFixed(0)} W</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
