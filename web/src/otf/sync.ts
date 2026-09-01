/**
 * Live-sync orchestration: pull the member's workouts from OTF and persist them
 * into the local Dexie store, reusing the same import path as paste-JSON import.
 */

import { OtfClient, type RawPerfSummary } from "./endpoints";
import { currentIdentity } from "./auth";
import { normalizeWorkout, perfSummaryId, type ExportWorkout } from "./normalize";
import { importJSON } from "../store/import";
import { db } from "../store/db";

export interface SyncProgress {
  phase: "listing" | "fetching" | "saving" | "done";
  fetched: number;
  total: number;
}

export interface SyncOptions {
  /** Cap on workouts to pull (most recent first). */
  limit?: number;
  /** If true, only fetch workouts not already in the local store (incremental). */
  incremental?: boolean;
  /** Parallel detail/telemetry requests. */
  concurrency?: number;
  onProgress?: (p: SyncProgress) => void;
}

async function mapPool<T, R>(
  items: T[],
  concurrency: number,
  worker: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  const results: R[] = new Array(items.length);
  let next = 0;
  const runners = Array.from({ length: Math.min(concurrency, items.length) }, async () => {
    while (true) {
      const i = next++;
      if (i >= items.length) break;
      results[i] = await worker(items[i], i);
    }
  });
  await Promise.all(runners);
  return results;
}

/**
 * Fetch workouts from OTF and write them into Dexie. Returns the number of
 * workouts saved. Requires an active login (see auth.login).
 */
export async function syncWorkouts(opts: SyncOptions = {}): Promise<number> {
  const { limit = 1000, incremental = false, concurrency = 5, onProgress } = opts;

  const identity = await currentIdentity();
  if (!identity) throw new Error("Not logged in — please sign in first.");
  const client = new OtfClient(identity);

  onProgress?.({ phase: "listing", fetched: 0, total: 0 });
  let summaries: RawPerfSummary[] = await client.listPerfSummaries(limit);

  if (incremental) {
    const existing = new Set<string>(await db.workouts.toCollection().primaryKeys());
    summaries = summaries.filter((s) => {
      const id = perfSummaryId(s);
      return id ? !existing.has(id) : false;
    });
  }

  const total = summaries.length;
  onProgress?.({ phase: "fetching", fetched: 0, total });

  let fetched = 0;
  const records = await mapPool<RawPerfSummary, ExportWorkout | null>(
    summaries,
    concurrency,
    async (summary) => {
      const id = perfSummaryId(summary);
      if (!id) return null;
      const [detail, telemetry] = await Promise.all([
        client.getPerfSummary(id),
        client.getTelemetry(id).catch(() => undefined), // telemetry is best-effort
      ]);
      fetched += 1;
      onProgress?.({ phase: "fetching", fetched, total });
      return normalizeWorkout(detail, telemetry);
    },
  );

  const clean = records.filter((r): r is ExportWorkout => r != null && r.performance_summary_id !== "");
  if (clean.length === 0) {
    onProgress?.({ phase: "done", fetched, total });
    return 0;
  }

  onProgress?.({ phase: "saving", fetched, total });
  const saved = await importJSON(JSON.stringify(clean));
  onProgress?.({ phase: "done", fetched, total });
  return saved;
}
