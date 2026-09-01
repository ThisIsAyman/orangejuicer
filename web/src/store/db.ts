import Dexie, { type EntityTable } from "dexie";

export interface Workout {
  performance_summary_id: string;
  workout_date: string;
  starts_at?: string;
  class_name?: string;
  class_type?: string;
  coach_name?: string;
  studio_name?: string;
  studio_uuid?: string;
  calories_burned?: number;
  splat_points?: number;
  step_count?: number;
  active_time_seconds?: number;
  avg_hr?: number;
  max_hr?: number;
  peak_hr?: number;
  peak_hr_percent?: number;
  avg_hr_percent?: number;
  zone_gray_min?: number;
  zone_blue_min?: number;
  zone_green_min?: number;
  zone_orange_min?: number;
  zone_red_min?: number;
  class_rating?: number;
  coach_rating?: number;
}

export interface TelemetryPoint {
  id?: number;
  performance_summary_id: string;
  relative_timestamp: number;
  hr?: number;
  tread_speed?: number;
  tread_incline?: number;
  tread_distance?: number;
  row_speed?: number;
  row_spm?: number;
  row_distance?: number;
  row_pace?: number;
}

export interface TreadmillSummary {
  performance_summary_id: string;
  avg_pace?: number;
  avg_speed?: number;
  max_pace?: number;
  max_speed?: number;
  moving_time?: number;
  total_distance?: number;
  avg_incline?: number;
  max_incline?: number;
  elevation_gained?: number;
}

export interface RowerSummary {
  performance_summary_id: string;
  avg_pace?: number;
  avg_speed?: number;
  max_pace?: number;
  max_speed?: number;
  moving_time?: number;
  total_distance?: number;
  avg_cadence?: number;
  avg_power?: number;
  max_cadence?: number;
}

const database = new Dexie("orangejuicer") as Dexie & {
  workouts: EntityTable<Workout, "performance_summary_id">;
  telemetry: EntityTable<TelemetryPoint, "id">;
  treadmill: EntityTable<TreadmillSummary, "performance_summary_id">;
  rower: EntityTable<RowerSummary, "performance_summary_id">;
};

database.version(1).stores({
  workouts: "performance_summary_id, workout_date, coach_name, studio_name",
  telemetry: "++id, performance_summary_id, relative_timestamp",
  treadmill: "performance_summary_id",
  rower: "performance_summary_id",
});

export const db = database;
