/**
 * Browser-side Strava TCX generation, mirroring `orangejuicer/tcx.py` so the
 * web export produces byte-for-byte the same files as `python main.py export
 * --format tcx`.
 *
 * OrangeTheory classes have no GPS but do have per-second heart rate plus
 * treadmill/rower telemetry. TCX carries time, heart rate, distance, cadence and
 * speed without GPS, and Strava imports it as an indoor activity
 * (`Sport="Other"` → generic *Workout*).
 *
 * Strava ignores the embedded `<Notes>` element on upload, so `buildDescription`
 * also returns a short string meant to be pasted into the activity's description
 * (and written as a `.txt` sidecar in the batch zip).
 */

import type { TelemetryPoint, Workout } from "./db";

const MILES_TO_METERS = 1609.34;
const MPH_TO_MPS = 0.44704;
const CREATOR_NAME = "OrangeTheory (orangejuicer)";

const TCX_NS = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2";
const AX_NS = "http://www.garmin.com/xmlschemas/ActivityExtension/v2";

function xmlEscape(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** Resolve the workout start as a UTC datetime (Date). Mirrors `_parse_start`. */
function parseStart(workout: Workout): Date {
  if (workout.starts_at) {
    const raw = String(workout.starts_at);
    // Treat a bare timestamp (no offset) as UTC, matching the Python side.
    const hasTz = /[zZ]|[+-]\d{2}:?\d{2}$/.test(raw);
    const d = new Date(hasTz ? raw.replace(/Z$/, "Z") : raw + "Z");
    if (!Number.isNaN(d.getTime())) return d;
  }
  if (workout.workout_date) {
    const d = new Date(String(workout.workout_date).slice(0, 10) + "T00:00:00Z");
    if (!Number.isNaN(d.getTime())) return d;
  }
  return new Date();
}

function isoUTC(d: Date): string {
  return (
    `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}` +
    `T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}Z`
  );
}

function localStamp(d: Date): string {
  // "YYYY-MM-DD HH:MM" in UTC, matching the Python strftime on the UTC datetime.
  return (
    `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ` +
    `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`
  );
}

function addSeconds(d: Date, secs: number): Date {
  return new Date(d.getTime() + secs * 1000);
}

function toInt(v: number | undefined | null): number | null {
  if (v === undefined || v === null || Number.isNaN(v)) return null;
  // Match Python's round() (banker's rounding: ties go to the even integer).
  const floor = Math.floor(v);
  const diff = v - floor;
  if (diff < 0.5) return floor;
  if (diff > 0.5) return floor + 1;
  return floor % 2 === 0 ? floor : floor + 1;
}

/** Human-readable description for pasting into Strava. Mirrors `build_description`. */
export function buildDescription(workout: Workout, studioName?: string): string {
  const start = parseStart(workout);
  const className = workout.class_name || workout.class_type || "OrangeTheory";
  const coach = workout.coach_name;
  const studio = studioName !== undefined ? studioName : workout.studio_name;
  const splats = workout.splat_points;
  const calories = workout.calories_burned;
  const avgHr = workout.avg_hr;
  const maxHr = workout.max_hr;

  const line1 = `OrangeTheory — ${className}`;
  const parts2 = [localStamp(start)];
  if (studio) parts2.push(`Studio: ${studio}`);
  if (coach) parts2.push(`Coach: ${coach}`);
  const line2 = parts2.join("  ·  ");

  const parts3: string[] = [];
  if (splats !== undefined && splats !== null) parts3.push(`Splats: ${splats}`);
  if (calories !== undefined && calories !== null) parts3.push(`Calories: ${calories}`);
  if (avgHr !== undefined && avgHr !== null && maxHr !== undefined && maxHr !== null) {
    parts3.push(`HR avg/max: ${avgHr}/${maxHr}`);
  }

  const lines = [line1, line2];
  if (parts3.length > 0) lines.push(parts3.join("  ·  "));
  return lines.join("\n");
}

interface TrackResult {
  chunks: string[];
  finalDistance: number;
  lastRel: number;
}

function buildTrackpoints(start: Date, telemetry: TelemetryPoint[]): TrackResult {
  const chunks: string[] = [];
  let treadM = 0;
  let rowM = 0;
  let lastTotal = 0;
  let lastRel = 0;

  for (const point of telemetry) {
    const rel = toInt(point.relative_timestamp) ?? 0;
    lastRel = rel;
    const tpTime = isoUTC(addSeconds(start, rel));

    if (point.tread_distance !== undefined && point.tread_distance !== null) {
      treadM = point.tread_distance * MILES_TO_METERS;
    }
    if (point.row_distance !== undefined && point.row_distance !== null) {
      rowM = point.row_distance;
    }

    let total = treadM + rowM;
    if (total < lastTotal) total = lastTotal;
    lastTotal = total;

    const body = [`<Time>${tpTime}</Time>`];
    const hr = toInt(point.hr);
    if (hr !== null) body.push(`<HeartRateBpm><Value>${hr}</Value></HeartRateBpm>`);
    body.push(`<DistanceMeters>${total.toFixed(2)}</DistanceMeters>`);

    const cadence = toInt(point.row_spm);
    if (cadence !== null) body.push(`<Cadence>${cadence}</Cadence>`);

    let speedMps: number | null = null;
    if (point.tread_speed) {
      speedMps = point.tread_speed * MPH_TO_MPS;
    } else if (point.row_pace && point.row_pace > 0) {
      speedMps = 500 / point.row_pace;
    }
    if (speedMps !== null) {
      body.push(
        `<Extensions><TPX xmlns="${AX_NS}">` +
          `<Speed>${speedMps.toFixed(3)}</Speed></TPX></Extensions>`,
      );
    }

    chunks.push("<Trackpoint>" + body.join("") + "</Trackpoint>");
  }

  return { chunks, finalDistance: lastTotal, lastRel };
}

/** Return a complete TCX document (XML string) for one OTF workout. Mirrors `build_tcx`. */
export function buildTcx(
  workout: Workout,
  telemetry: TelemetryPoint[] = [],
  studioName?: string,
): string {
  const start = parseStart(workout);
  const startIso = isoUTC(start);

  const avgHr = toInt(workout.avg_hr);
  const maxHr = toInt(workout.max_hr);
  const calories = toInt(workout.calories_burned) ?? 0;
  const activeSeconds = toInt(workout.active_time_seconds);

  const { chunks, finalDistance, lastRel } = buildTrackpoints(start, telemetry);

  if (chunks.length === 0) {
    const totalSeconds = activeSeconds ?? 0;
    for (const offset of [0, totalSeconds]) {
      const body = [`<Time>${isoUTC(addSeconds(start, offset))}</Time>`];
      if (avgHr !== null) body.push(`<HeartRateBpm><Value>${avgHr}</Value></HeartRateBpm>`);
      body.push("<DistanceMeters>0.00</DistanceMeters>");
      chunks.push("<Trackpoint>" + body.join("") + "</Trackpoint>");
    }
  }

  const totalTime = activeSeconds ? activeSeconds : lastRel;

  const lapParts = [
    `<TotalTimeSeconds>${totalTime.toFixed(1)}</TotalTimeSeconds>`,
    `<DistanceMeters>${finalDistance.toFixed(2)}</DistanceMeters>`,
    `<Calories>${calories}</Calories>`,
  ];
  if (avgHr !== null) {
    lapParts.push(`<AverageHeartRateBpm><Value>${avgHr}</Value></AverageHeartRateBpm>`);
  }
  if (maxHr !== null) {
    lapParts.push(`<MaximumHeartRateBpm><Value>${maxHr}</Value></MaximumHeartRateBpm>`);
  }
  lapParts.push("<Intensity>Active</Intensity>");
  lapParts.push("<TriggerMethod>Manual</TriggerMethod>");
  lapParts.push("<Track>" + chunks.join("") + "</Track>");

  const notes = xmlEscape(buildDescription(workout, studioName));
  const creator =
    `<Creator xsi:type="Device_t"><Name>${xmlEscape(CREATOR_NAME)}</Name>` +
    "<UnitId>0</UnitId><ProductID>0</ProductID></Creator>";

  return (
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    `<TrainingCenterDatabase xmlns="${TCX_NS}" ` +
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">' +
    "<Activities>" +
    '<Activity Sport="Other">' +
    `<Id>${startIso}</Id>` +
    `<Lap StartTime="${startIso}">` +
    lapParts.join("") +
    "</Lap>" +
    `<Notes>${notes}</Notes>` +
    creator +
    "</Activity>" +
    "</Activities>" +
    "</TrainingCenterDatabase>\n"
  );
}

/** Filename stem `<date>_<psid>` shared by the .tcx and .txt sidecar. */
export function tcxStem(workout: Workout): string {
  const date = String(workout.workout_date ?? "unknown").slice(0, 10);
  return `${date}_${workout.performance_summary_id}`;
}
