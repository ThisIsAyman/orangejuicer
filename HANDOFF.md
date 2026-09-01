# HANDOFF

Session log for resuming work. Newest entry on top.

---

## 2026-06-27 — Committed, pushed, PR opened

Short follow-up to the entry below. The large uncommitted tree from that entry
is now committed and on GitHub.

### State change
- ✅ All work **committed** as `13d261b` "Add browser no-Python flow and Strava
  TCX export" (34 files, +2714/−97).
- ✅ **Pushed** to `origin/branch_pr_1` (tracks upstream now).
- ✅ **PR #15** open: `branch_pr_1` → `main` —
  https://github.com/ThisIsAyman/orangejuicer/pull/15
- 🚧 GitHub Pages **deploy workflow** triggered on push (run `28281926031`,
  "Deploy Dashboard to GitHub Pages"); was in_progress at handoff time — verify
  it went green via `gh run list --branch branch_pr_1`.

### Cleanup done
- Removed two stray untracked files before committing: `oranejuicer.md` (an
  exported Copilot session transcript) and `workouts.json` (13MB demo export).
  Watch for these reappearing — neither is gitignored.

### Still open (carried forward — see entry below for full context)
- [ ] Live-test browser login/sync vs a real OTF account; verify
      `web/src/otf/normalize.ts` mapping. Deployed site won't sync until next item.
- [ ] Deploy Cloudflare Worker (`proxy/`) + set repo variable `OTF_PROXY_URL`
      so CI injects `VITE_OTF_PROXY_URL` (deploy.yml). JSON import + TCX work
      without it; only live-sync needs it.
- [ ] Review/merge PR #15.
- [ ] `extension-stub` todo — not started, scope unclear.

---

## 2026-06-26 — Browser no-Python flow + Strava TCX export

### 1. Project Goal
orangejuicer is a Python CLI + React/TS web dashboard for OrangeTheory Fitness
(OTF) data. Flow is one-directional: **OTF/Reddit APIs → local SQLite → stats /
charts / exports**. After initial `sync`, all read commands work offline.

### 2. Current State
- ✅ **Strava TCX export** (this session, fully done + verified). CLI
  `export --format tcx` and web "Export TCX" buttons. CLI↔web output is
  byte-for-byte identical (200 demo workouts).
- ✅ **Browser no-Python flow** (prior session, build-verified, NOT live-tested).
  In-browser OTF login (Cognito SRP) + sync via stateless Cloudflare Worker proxy.
- 🚧 **Everything above is UNCOMMITTED** — all on the working tree, no commits yet.
- ❌ **Live OTF auth/sync untested** — no real credentials available in this env.
  `web/src/otf/normalize.ts` field mapping unverified against real OTF JSON.
- 💤 `extension-stub` todo (a VS Code extension stub) — not started, out of scope.

### 3. Architecture
- **CLI** (`main.py`): argparse, one `cmd_*` per subcommand; heavy imports are
  **lazy** (inside each `cmd_*`). Subcommands: sync, stats, visualize, compare,
  workout, query, export, all.
- **Data layer**: `orangejuicer/db.py` (9-table SQLite schema + `upsert_*`),
  `adapters.py` (rows→dataclasses), `sync.py` (90-day chunked fetch w/ dedup —
  OTF API silently truncates large result sets), `demo.py` (synthetic data).
- **TCX**: `orangejuicer/tcx.py` (`build_tcx`, `build_description`) ⇄ mirrored by
  `web/src/store/tcx.ts` (`buildTcx`, `buildDescription`, `tcxStem`).
- **Web** (`web/`): React + Vite + Dexie (IndexedDB). `web/src/otf/` =
  transport-agnostic OTF client (auth/transport/endpoints/normalize/sync).
  `web/src/store/export.ts` = JSON/CSV/TCX-zip export. Build outputs to `docs/`
  (GitHub Pages via `.github/workflows/deploy.yml`).
- **Proxy** (`proxy/`): ~100-line stateless Cloudflare Worker. Contract:
  `GET /relay?target=<url-encoded otf-url>`. 3-host allowlist, `redirect:"manual"`,
  CORS via `ALLOWED_ORIGIN`. Configured into web build via `VITE_OTF_PROXY_URL`.

### 4. Decisions Log
- **Decision**: TCX uses `Sport="Other"` (→ Strava generic "Workout").
  **Why**: user wanted a single generic sport for all classes.
- **Decision**: Ship a `.txt` description sidecar per `.tcx`.
  **Why**: Strava **ignores TCX `<Notes>`** on upload; sidecar is pasted manually.
- **Decision**: Stateless Cloudflare Worker proxy (not Azure/AWS managed service).
  **Why**: OTF data API blocks browser calls (no CORS + forbidden headers); a
  thin relay is the minimum needed and stores nothing/no credentials.
- **Decision**: Persist refresh token in browser; keep Python CLI.
  **Why**: user choices during planning.

### 5. Issues Resolved
- **Cadence parity mismatch CLI vs web**: Python `int(round(f))` uses banker's
  rounding (half-to-even); JS `Math.round` rounds half-up (24.5→25 vs 24). Fixed
  `toInt` in `web/src/store/tcx.ts` to do half-to-even. Now 0/200 mismatches.
- **`ModuleNotFoundError: No module named 'dotenv'`** running pytest: dev deps
  not on system Python. Fix: use repo venv → `.venv/bin/python -m pytest`.
- **Token-leak via redirect** (prior session security review): proxy followed
  redirects, could replay bearer off-allowlist. Fixed with `redirect:"manual"`.

### 6. Open Items
- [ ] **Commit the work.** Huge uncommitted tree spanning 2 features. Consider
      splitting into 2+ commits: (a) browser flow + proxy, (b) TCX export.
      Untracked dirs: `proxy/`, `web/src/otf/`, plus many modified/new files.
- [ ] **Delete stray artifacts before committing**: `workouts.json` (test export)
      and `oranejuicer.md` (typo'd stray file) at repo root — neither belongs.
- [ ] **Live-test browser login/sync** against real OTF account; verify
      `web/src/otf/normalize.ts` field mapping matches real API JSON.
- [ ] **Deploy the proxy** (Cloudflare Worker in `proxy/`) and set repo variable
      `OTF_PROXY_URL` so CI injects `VITE_OTF_PROXY_URL` (context: deploy.yml).
- [ ] `extension-stub` todo — not started; clarify scope before doing.

### 7. Environment
- Python deps live in repo `.venv` (system Python lacks them). Use
  `.venv/bin/python` for pytest/ruff/black. ruff+black NOT in venv until you
  `pip install ruff black` (done this session) or `pip install -e ".[dev]"`.
- numpy pinned ≤1.26.x (prebuilt 2.x wheels need AVX2; old CPUs need
  `numpy==1.26.4 --no-binary numpy`).
- Web: Node + npm; jszip added this session.

### 8. How to Resume
1. Read this file, then `plan.md` in the session-state folder if continuing TCX.
2. Verify state:
   - `.venv/bin/python -m pytest tests/test_tcx.py -q` → 8 pass.
   - `cd web && npm run build` → tsc + vite succeed (outputs to `docs/`).
3. To regen/inspect TCX: `OJ_DB_PATH=$(mktemp -d)/x.db .venv/bin/python main.py
   sync --demo && .venv/bin/python main.py export --format tcx --output /tmp/tcx`.
4. If touching exports, **keep CLI `tcx.py` and web `tcx.ts` in lockstep** and
   re-run the parity check (esbuild-bundle tcx.ts, diff vs CLI output).

### 9. Gotchas
- **CLI export and web export must stay byte-for-byte identical** (`tcx.py` ↔
  `tcx.ts`, incl. Python banker's rounding). Diverging silently breaks parity.
- **`main.py` has many pre-existing ruff E501 / black violations** in `cmd_*`
  print code. They are NOT yours — don't reformat out-of-scope code. New code
  must be clean, but the file as a whole does not pass black/ruff.
- **Strava ignores `<Notes>`** — that's why the `.txt` sidecar exists; not a bug.
- **DB path**: defaults to `~/.orangejuicer/orangejuicer.db`; override with
  `OJ_DB_PATH`. Tests use `tmp_path`. Never hardcode prod path in tests.
- **`otf-api` is unofficial** and has restructured before; pin/verify against
  `requirements.txt` (`otf-api>=0.15.4`).
- **Telemetry units**: tread distance = miles, tread speed = mph, rower distance
  = meters, rower pace = sec/500m. TCX needs meters/(m·s⁻¹) — conversions live in
  `_trackpoints`. `DistanceMeters` must be non-decreasing (carry-forward).
