import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { db } from "../store/db";
import type { Workout } from "../store/db";

type SortField = "workout_date" | "calories_burned" | "splat_points" | "coach_name" | "studio_name";

export default function WorkoutList() {
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [sortField, setSortField] = useState<SortField>("workout_date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [filterCoach, setFilterCoach] = useState("");
  const [filterStudio, setFilterStudio] = useState("");
  const [coaches, setCoaches] = useState<string[]>([]);
  const [studios, setStudios] = useState<string[]>([]);

  useEffect(() => {
    db.workouts.toArray().then((ws) => {
      setWorkouts(ws);
      setCoaches([...new Set(ws.map((w) => w.coach_name).filter(Boolean) as string[])].sort());
      setStudios([...new Set(ws.map((w) => w.studio_name).filter(Boolean) as string[])].sort());
    });
  }, []);

  const sorted = [...workouts]
    .filter((w) => {
      if (filterCoach && w.coach_name !== filterCoach) return false;
      if (filterStudio && w.studio_name !== filterStudio) return false;
      return true;
    })
    .sort((a, b) => {
      const av = a[sortField] ?? "";
      const bv = b[sortField] ?? "";
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  };

  const sortIcon = (field: SortField) =>
    sortField === field ? (sortDir === "asc" ? " ▲" : " ▼") : "";

  return (
    <div className="workout-list">
      <div className="filters">
        <select value={filterCoach} onChange={(e) => setFilterCoach(e.target.value)}>
          <option value="">All Coaches</option>
          {coaches.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select value={filterStudio} onChange={(e) => setFilterStudio(e.target.value)}>
          <option value="">All Studios</option>
          {studios.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <span className="result-count">{sorted.length} workouts</span>
      </div>

      <table>
        <thead>
          <tr>
            <th onClick={() => toggleSort("workout_date")} className="sortable">
              Date{sortIcon("workout_date")}
            </th>
            <th>Class</th>
            <th onClick={() => toggleSort("coach_name")} className="sortable">
              Coach{sortIcon("coach_name")}
            </th>
            <th onClick={() => toggleSort("studio_name")} className="sortable">
              Studio{sortIcon("studio_name")}
            </th>
            <th onClick={() => toggleSort("calories_burned")} className="sortable">
              Cals{sortIcon("calories_burned")}
            </th>
            <th onClick={() => toggleSort("splat_points")} className="sortable">
              Splats{sortIcon("splat_points")}
            </th>
            <th>Avg HR</th>
            <th>Max HR</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((w) => (
            <tr key={w.performance_summary_id}>
              <td>
                <Link to={`/workouts/${encodeURIComponent(w.performance_summary_id)}`}>
                  {w.workout_date}
                </Link>
              </td>
              <td>{w.class_name || "—"}</td>
              <td>{w.coach_name || "—"}</td>
              <td>{w.studio_name || "—"}</td>
              <td>{w.calories_burned ?? "—"}</td>
              <td>{w.splat_points ?? "—"}</td>
              <td>{w.avg_hr ?? "—"}</td>
              <td>{w.max_hr ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
