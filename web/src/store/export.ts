/**
 * Browser-side export of the local store to JSON or CSV, matching the Python
 * CLI's `export` format so the output round-trips through importJSON and is
 * interchangeable with `python main.py export`.
 */

import JSZip from "jszip";

import { db, type Workout } from "./db";
import { buildDescription, buildTcx, tcxStem } from "./tcx";

/** Build the `export --full` JSON structure (flat workout + _treadmill/_rower/_telemetry). */
export async function exportJSON(): Promise<string> {
  const workouts = await db.workouts.orderBy("workout_date").toArray();
  const data: Record<string, unknown>[] = [];

  for (const w of workouts) {
    const d: Record<string, unknown> = { ...w };
    const psid = w.performance_summary_id;

    const tread = await db.treadmill.get(psid);
    if (tread) {
      const { performance_summary_id: _omit, ...rest } = tread;
      void _omit;
      d._treadmill = rest;
    }
    const rower = await db.rower.get(psid);
    if (rower) {
      const { performance_summary_id: _omit, ...rest } = rower;
      void _omit;
      d._rower = rest;
    }
    const telem = await db.telemetry
      .where("performance_summary_id")
      .equals(psid)
      .sortBy("relative_timestamp");
    if (telem.length > 0) {
      d._telemetry = telem.map(({ id: _id, ...rest }) => {
        void _id;
        return rest;
      });
    }
    data.push(d);
  }

  return JSON.stringify(data, null, 2);
}

const CSV_COLUMNS: (keyof Workout)[] = [
  "performance_summary_id",
  "workout_date",
  "starts_at",
  "class_name",
  "class_type",
  "coach_name",
  "studio_name",
  "calories_burned",
  "splat_points",
  "step_count",
  "active_time_seconds",
  "avg_hr",
  "max_hr",
  "peak_hr",
  "avg_hr_percent",
  "peak_hr_percent",
  "zone_gray_min",
  "zone_blue_min",
  "zone_green_min",
  "zone_orange_min",
  "zone_red_min",
  "class_rating",
  "coach_rating",
];

function csvCell(v: unknown): string {
  if (v === undefined || v === null) return "";
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** One-row-per-workout CSV (summary fields only), matching the CLI's CSV export. */
export async function exportCSV(): Promise<string> {
  const workouts = await db.workouts.orderBy("workout_date").toArray();
  const header = CSV_COLUMNS.join(",");
  const lines = workouts.map((w) => CSV_COLUMNS.map((c) => csvCell(w[c])).join(","));
  return [header, ...lines].join("\n");
}

/** Trigger a browser download of the given text content. */
export function downloadText(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function downloadExport(format: "json" | "csv"): Promise<void> {
  if (format === "json") {
    downloadText("workouts.json", await exportJSON(), "application/json");
  } else {
    downloadText("workouts.csv", await exportCSV(), "text/csv");
  }
}

/** Trigger a browser download of binary blob content. */
function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * Build a `.tcx` + `.txt` description sidecar for every workout and download
 * them as a single zip, ready to drag onto strava.com/upload. Returns the
 * number of workouts exported.
 */
export async function downloadTcxZip(): Promise<number> {
  const workouts = await db.workouts.orderBy("workout_date").toArray();
  const zip = new JSZip();

  for (const w of workouts) {
    const telem = await db.telemetry
      .where("performance_summary_id")
      .equals(w.performance_summary_id)
      .sortBy("relative_timestamp");
    const stem = tcxStem(w);
    zip.file(`${stem}.tcx`, buildTcx(w, telem, w.studio_name));
    zip.file(`${stem}.txt`, buildDescription(w, w.studio_name));
  }

  const blob = await zip.generateAsync({ type: "blob" });
  downloadBlob("orangejuicer-tcx.zip", blob);
  return workouts.length;
}
