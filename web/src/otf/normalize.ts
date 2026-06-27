/**
 * Normalize raw OTF API responses into the export-record shape consumed by
 * store/import.ts (`importJSON`). Using the same shape means:
 *  - live-synced data and paste-imported JSON travel the identical persistence path;
 *  - browser export (store/export.ts) round-trips with the Python CLI's
 *    `export --full` format.
 *
 * NOTE: OTF's raw HTTP JSON is undocumented and may use camelCase keys, whereas
 * the Python `otf-api` models expose snake_case. We therefore read every field
 * through `pick()`, which tolerates snake_case, camelCase, and a couple of
 * common aliases. If a future OTF change moves a field, adjust it here only —
 * the rest of the pipeline is unaffected.
 */

type Obj = Record<string, unknown>;

function isObj(v: unknown): v is Obj {
  return typeof v === "object" && v !== null;
}

const snakeToCamel = (k: string): string => k.replace(/_([a-z])/g, (_, c) => c.toUpperCase());

/** Read a value by snake_case name, also trying camelCase and provided aliases. */
function pick(obj: unknown, name: string, ...aliases: string[]): unknown {
  if (!isObj(obj)) return undefined;
  const candidates = [name, snakeToCamel(name), ...aliases];
  for (const c of candidates) {
    if (obj[c] !== undefined && obj[c] !== null) return obj[c];
  }
  return undefined;
}

function num(v: unknown): number | undefined {
  if (v === undefined || v === null || v === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

function str(v: unknown): string | undefined {
  return v === undefined || v === null ? undefined : String(v);
}

/** Export record shape (matches store/import.ts RawWorkout + Python export). */
export interface ExportWorkout {
  performance_summary_id: string;
  workout_date?: string;
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
  _treadmill?: Obj;
  _rower?: Obj;
  _telemetry?: Obj[];
}

function ratingValue(v: unknown): number | undefined {
  // OTF ratings may be a scalar or an object like { value: 3 }.
  if (isObj(v)) return num(pick(v, "value"));
  return num(v);
}

function normalizeTreadmill(tread: unknown): Obj | undefined {
  if (!isObj(tread)) return undefined;
  return {
    avg_pace: num(pick(tread, "avg_pace")),
    avg_speed: num(pick(tread, "avg_speed")),
    max_pace: num(pick(tread, "max_pace")),
    max_speed: num(pick(tread, "max_speed")),
    moving_time: num(pick(tread, "moving_time")),
    total_distance: num(pick(tread, "total_distance")),
    avg_incline: num(pick(tread, "avg_incline")),
    max_incline: num(pick(tread, "max_incline")),
    elevation_gained: num(pick(tread, "elevation_gained")),
  };
}

function normalizeRower(rower: unknown): Obj | undefined {
  if (!isObj(rower)) return undefined;
  return {
    avg_pace: num(pick(rower, "avg_pace")),
    avg_speed: num(pick(rower, "avg_speed")),
    max_pace: num(pick(rower, "max_pace")),
    max_speed: num(pick(rower, "max_speed")),
    moving_time: num(pick(rower, "moving_time")),
    total_distance: num(pick(rower, "total_distance")),
    avg_cadence: num(pick(rower, "avg_cadence")),
    avg_power: num(pick(rower, "avg_power")),
    max_cadence: num(pick(rower, "max_cadence")),
  };
}

/** Normalize the telemetry endpoint response into per-sample export rows. */
export function normalizeTelemetry(telemetryResponse: unknown): Obj[] {
  // Response wraps the samples under a `telemetry` array (mirrors the model).
  const samples = pick(telemetryResponse, "telemetry");
  const items = Array.isArray(samples)
    ? samples
    : Array.isArray(telemetryResponse)
      ? (telemetryResponse as unknown[])
      : [];
  const rows: Obj[] = [];
  for (const item of items) {
    if (!isObj(item)) continue;
    const td = pick(item, "tread_data");
    const rd = pick(item, "row_data");
    rows.push({
      relative_timestamp: num(pick(item, "relative_timestamp")) ?? 0,
      hr: num(pick(item, "hr")),
      agg_splats: num(pick(item, "agg_splats")),
      agg_calories: num(pick(item, "agg_calories")),
      tread_speed: num(pick(td, "tread_speed")),
      tread_incline: num(pick(td, "tread_incline")),
      tread_distance: num(pick(td, "agg_tread_distance", "tread_distance")),
      row_speed: num(pick(rd, "row_speed")),
      row_spm: num(pick(rd, "row_spm")),
      row_distance: num(pick(rd, "agg_row_distance", "row_distance")),
      row_pace: num(pick(rd, "row_pace")),
    });
  }
  return rows;
}

/**
 * Build a single export record from a performance-summary detail plus its
 * (separately fetched) telemetry response.
 */
export function normalizeWorkout(detail: unknown, telemetryResponse?: unknown): ExportWorkout {
  const otfClass = pick(detail, "otf_class", "class");
  const startsAt = str(pick(otfClass, "starts_at", "startsAtLocal", "startsAt"));
  const hr = pick(detail, "heart_rate");
  const zones = pick(detail, "zone_time_minutes") ?? {};
  const studio = pick(detail, "studio");

  const psid = str(pick(detail, "performance_summary_id", "id")) ?? "";

  const record: ExportWorkout = {
    performance_summary_id: psid,
    workout_date: startsAt ? startsAt.slice(0, 10) : undefined,
    starts_at: startsAt,
    class_name: str(pick(otfClass, "name")),
    class_type: str(pick(otfClass, "class_type")),
    coach_name: str(pick(detail, "coach") ?? pick(otfClass, "coach")),
    studio_name: str(pick(studio, "name")),
    studio_uuid: str(pick(studio, "studio_uuid", "id")),
    calories_burned: num(pick(detail, "calories_burned")),
    splat_points: num(pick(detail, "splat_points")),
    step_count: num(pick(detail, "step_count")),
    active_time_seconds: num(pick(detail, "active_time_seconds")),
    avg_hr: num(pick(hr, "avg_hr")),
    max_hr: num(pick(hr, "max_hr")),
    peak_hr: num(pick(hr, "peak_hr")),
    peak_hr_percent: num(pick(hr, "peak_hr_percent")),
    avg_hr_percent: num(pick(hr, "avg_hr_percent")),
    zone_gray_min: num(pick(zones, "gray")),
    zone_blue_min: num(pick(zones, "blue")),
    zone_green_min: num(pick(zones, "green")),
    zone_orange_min: num(pick(zones, "orange")),
    zone_red_min: num(pick(zones, "red")),
    class_rating: ratingValue(pick(detail, "class_rating")),
    coach_rating: ratingValue(pick(detail, "coach_rating")),
  };

  const tread = normalizeTreadmill(pick(detail, "treadmill_data"));
  if (tread) record._treadmill = tread;
  const rower = normalizeRower(pick(detail, "rower_data"));
  if (rower) record._rower = rower;
  if (telemetryResponse !== undefined) {
    const telem = normalizeTelemetry(telemetryResponse);
    if (telem.length > 0) record._telemetry = telem;
  }

  return record;
}

/** The summary-list id for a perf-summary list item. */
export function perfSummaryId(item: unknown): string | undefined {
  return str(pick(item, "performance_summary_id", "id"));
}
