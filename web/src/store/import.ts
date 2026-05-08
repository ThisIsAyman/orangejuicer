import { db } from "./db";
import type { Workout, TelemetryPoint, TreadmillSummary, RowerSummary } from "./db";

interface RawWorkout {
  performance_summary_id: string;
  [key: string]: unknown;
  _telemetry?: Array<Record<string, unknown>>;
  _treadmill?: Record<string, unknown>;
  _rower?: Record<string, unknown>;
  _studio?: { name?: string; [key: string]: unknown };
}

export async function importJSON(jsonText: string): Promise<number> {
  const raw: RawWorkout[] = JSON.parse(jsonText);
  if (!Array.isArray(raw) || raw.length === 0) {
    throw new Error("Expected a non-empty JSON array of workouts");
  }

  const workouts: Workout[] = [];
  const telemetryPoints: TelemetryPoint[] = [];
  const treadmillSummaries: TreadmillSummary[] = [];
  const rowerSummaries: RowerSummary[] = [];

  for (const r of raw) {
    const studioName =
      (r.studio_name as string) || r._studio?.name || "";

    workouts.push({
      performance_summary_id: r.performance_summary_id,
      workout_date: r.workout_date as string,
      starts_at: r.starts_at as string | undefined,
      class_name: r.class_name as string | undefined,
      class_type: r.class_type as string | undefined,
      coach_name: r.coach_name as string | undefined,
      studio_name: studioName,
      studio_uuid: r.studio_uuid as string | undefined,
      calories_burned: r.calories_burned as number | undefined,
      splat_points: r.splat_points as number | undefined,
      step_count: r.step_count as number | undefined,
      active_time_seconds: r.active_time_seconds as number | undefined,
      avg_hr: r.avg_hr as number | undefined,
      max_hr: r.max_hr as number | undefined,
      peak_hr: r.peak_hr as number | undefined,
      peak_hr_percent: r.peak_hr_percent as number | undefined,
      avg_hr_percent: r.avg_hr_percent as number | undefined,
      zone_gray_min: r.zone_gray_min as number | undefined,
      zone_blue_min: r.zone_blue_min as number | undefined,
      zone_green_min: r.zone_green_min as number | undefined,
      zone_orange_min: r.zone_orange_min as number | undefined,
      zone_red_min: r.zone_red_min as number | undefined,
      class_rating: r.class_rating as number | undefined,
      coach_rating: r.coach_rating as number | undefined,
    });

    if (r._treadmill) {
      treadmillSummaries.push({
        performance_summary_id: r.performance_summary_id,
        ...r._treadmill,
      } as TreadmillSummary);
    }

    if (r._rower) {
      rowerSummaries.push({
        performance_summary_id: r.performance_summary_id,
        ...r._rower,
      } as RowerSummary);
    }

    if (r._telemetry) {
      for (const t of r._telemetry) {
        telemetryPoints.push({
          performance_summary_id: r.performance_summary_id,
          relative_timestamp: t.relative_timestamp as number,
          hr: t.hr as number | undefined,
          tread_speed: t.tread_speed as number | undefined,
          tread_incline: t.tread_incline as number | undefined,
          tread_distance: t.tread_distance as number | undefined,
          row_speed: t.row_speed as number | undefined,
          row_spm: t.row_spm as number | undefined,
          row_distance: t.row_distance as number | undefined,
          row_pace: t.row_pace as number | undefined,
        });
      }
    }
  }

  await db.transaction(
    "rw",
    [db.workouts, db.telemetry, db.treadmill, db.rower],
    async () => {
      await db.workouts.bulkPut(workouts);
      if (treadmillSummaries.length > 0) {
        await db.treadmill.bulkPut(treadmillSummaries);
      }
      if (rowerSummaries.length > 0) {
        await db.rower.bulkPut(rowerSummaries);
      }
      if (telemetryPoints.length > 0) {
        // Clear old telemetry for these workouts, then add new
        const psids = [...new Set(telemetryPoints.map((t) => t.performance_summary_id))];
        for (const psid of psids) {
          await db.telemetry.where("performance_summary_id").equals(psid).delete();
        }
        await db.telemetry.bulkAdd(telemetryPoints);
      }
    }
  );

  return workouts.length;
}
