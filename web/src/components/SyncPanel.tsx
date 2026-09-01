import { useState } from "react";
import { syncWorkouts, type SyncProgress } from "../otf/sync";
import { downloadExport, downloadTcxZip } from "../store/export";
import { logout } from "../otf/auth";

interface Props {
  /** Called after a successful sync (so the dashboard can refresh). */
  onSynced: () => void;
  /** Called after logout. */
  onLoggedOut: () => void;
}

/** Controls for live-syncing from OTF, exporting, and signing out. */
export default function SyncPanel({ onSynced, onLoggedOut }: Props) {
  const [progress, setProgress] = useState<SyncProgress | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runSync = async (incremental: boolean) => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const saved = await syncWorkouts({ incremental, onProgress: setProgress });
      setMessage(`Synced ${saved} workout${saved === 1 ? "" : "s"}.`);
      onSynced();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setBusy(false);
      setProgress(null);
    }
  };

  const handleLogout = () => {
    logout();
    onLoggedOut();
  };

  const exportTcx = async () => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const n = await downloadTcxZip();
      setMessage(`Exported ${n} TCX file${n === 1 ? "" : "s"} (zip).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "TCX export failed");
    } finally {
      setBusy(false);
    }
  };

  const progressText = progress
    ? progress.phase === "fetching"
      ? `Fetching workouts ${progress.fetched}/${progress.total}…`
      : `${progress.phase}…`
    : null;

  return (
    <div className="sync-panel">
      <button className="btn-primary" disabled={busy} onClick={() => runSync(false)}>
        {busy ? "Syncing…" : "Sync all"}
      </button>
      <button className="btn-secondary" disabled={busy} onClick={() => runSync(true)}>
        Sync new
      </button>
      <button className="btn-secondary" disabled={busy} onClick={() => downloadExport("json")}>
        Export JSON
      </button>
      <button className="btn-secondary" disabled={busy} onClick={() => downloadExport("csv")}>
        Export CSV
      </button>
      <button className="btn-secondary" disabled={busy} onClick={exportTcx}>
        Export TCX (Strava)
      </button>
      <button className="btn-clear" onClick={handleLogout} title="Sign out">
        Sign out
      </button>
      {progressText && <span className="sync-status">{progressText}</span>}
      {message && <span className="sync-status success">{message}</span>}
      {error && <span className="sync-status error">{error}</span>}
    </div>
  );
}
