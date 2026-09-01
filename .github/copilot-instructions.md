# Copilot instructions for orangejuicer

orangejuicer is a Python CLI that authenticates against OrangeTheory Fitness,
syncs workout/telemetry/Reddit data into a local SQLite database, and renders
stats, charts, and community comparisons. A separate React + TypeScript dashboard
(`web/`) renders the same data in the browser from drag-and-dropped JSON exports.

## Commands

Python (run from repo root):

```bash
pip install -r requirements.txt          # runtime deps
pip install -e ".[dev]"                  # dev deps (pytest, black, ruff)

pytest tests/ -v                         # full suite (~106 tests)
pytest tests/test_db.py -v               # single file
pytest tests/test_db.py::TestSchema::test_reopen_is_idempotent  # single test

ruff check .                             # lint
black .                                  # format (line-length 100, py39 target)
```

Web dashboard (run from `web/`):

```bash
npm ci          # install
npm run dev     # local dev server (vite)
npm run build   # tsc -b && vite build → outputs to docs/ for GitHub Pages
```

The CLI is invoked as `python main.py <command>`. Subcommands: `sync`, `stats`,
`visualize`, `compare`, `workout`, `query`, `export`, `all`.

## Architecture

Data flows in one direction: **OTF/Reddit APIs → local SQLite → everything else.**
After an initial `sync`, all read commands (`stats`, `visualize`, `compare`,
`query`, `workout`, `export`) work offline against the DB — no credentials needed.

- `main.py` — argparse CLI entry point. Each subcommand is a `cmd_*` function.
- `orangejuicer/auth.py` — OTF login wrapper (reads `OTF_EMAIL`/`OTF_PASSWORD`).
- `orangejuicer/client.py` — fetches and normalises data from the unofficial
  `otf-api` library into plain dicts.
- `orangejuicer/sync.py` — sync engine. Full vs. incremental; fetches large
  histories in **90-day chunks with dedup** because the OTF API silently
  truncates large result sets. Per-entity cursors live in the `sync_log` table.
- `orangejuicer/db.py` — SQLite schema, connection, migrations, and `upsert_*`
  functions. Owns the canonical 9-table schema.
- `orangejuicer/adapters.py` — converts raw SQLite rows into domain dataclasses,
  with filtering (date range, coach, studio). Read-side bridge between DB and
  the stats/viz/export commands.
- `orangejuicer/demo.py` — synthetic data generator + fixture loader for
  `sync --demo` (no API needed).
- `orangejuicer/reddit.py` — Reddit scraper (via `praw`) and stat parser.
- `orangejuicer/visualizations.py` / `comparisons.py` — matplotlib/plotly charts
  and personal-vs-community comparisons.

The workout data model has three levels: workout summary (one row/class),
equipment summaries (treadmill/rower, one row each), and per-second telemetry
(~150 samples/class). See the README "Workout data model" section for the full
field reference before touching schema or adapters.

## Conventions

- **DB path**: defaults to `~/.orangejuicer/orangejuicer.db`, overridable via
  the `OJ_DB_PATH` env var. `get_connection(db_path=None)` accepts an explicit
  path — tests pass `tmp_path / "test.db"` to stay isolated. Never hardcode the
  production path in tests.
- **Schema changes** go through `db.py`: add `CREATE TABLE IF NOT EXISTS` and a
  matching `upsert_*` function; persistence is idempotent upsert, not insert.
- **Lazy imports**: `main.py` imports heavy modules (matplotlib, db, etc.)
  *inside* each `cmd_*` function, not at module top, to keep CLI startup fast.
  Preserve this pattern when adding commands.
- **Credentials** come from env vars / `.env` (loaded via `python-dotenv`).
  Never commit `.env` or log secrets.
- **numpy pin**: prebuilt numpy 2.x wheels require AVX2; on old CPUs install
  `numpy==1.26.4 --no-binary numpy`. Don't bump numpy past 1.26.x assumptions.
- **Web build output** is committed to `docs/` (served by GitHub Pages via
  `.github/workflows/deploy.yml`). Rebuild `docs/` when changing `web/`.
- Code style is enforced by ruff + black at **line-length 100**, targeting
  Python 3.9.

## Gotchas

- The `otf-api` library is unofficial and has restructured its API before
  (e.g. `otf.workouts.get_workouts()`); pin and verify against the version in
  `requirements.txt` (`otf-api>=0.15.4`).
- `sync --capture` saves raw API responses to `fixtures/captured_*.json` (gitignored)
  for offline replay; committed fixtures are `fixtures/demo_*.json`.
