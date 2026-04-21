# Changelog

All notable changes to orangejuicer are documented here.

## [Unreleased]

### Added
- **Local SQLite database** with 9-table schema (studios, workouts, treadmill/rower summaries, telemetry, reddit_posts, benchmarks, body_composition, sync_log)
- **Sync engine** (`orangejuicer/sync.py`) — full & incremental sync from OTF API with 90-day chunked fetching for large histories (1000+ workouts)
- **Demo/mock data system** (`orangejuicer/demo.py`) — generate 200 realistic synthetic workouts + 150 Reddit posts for development/testing without API credentials
- **JSON fixture files** (`fixtures/`) — committed demo data for instant `sync --demo`
- **CLI: `sync` command** with `--full`, `--demo`, `--capture` flags
- **CLI: `stats` command** now reads from local database instead of live API
- **Capture mode** (`sync --capture`) — saves raw API responses as JSON for offline replay
- **95 tests** across all modules (db, sync, demo, client, auth, reddit, viz, comparisons)

### Fixed
- **numpy SIGILL crash** on Intel Atom D510 — pinned to numpy 1.26.4 built from source (AVX2-free)
- **`get_workout_history` AttributeError** — updated client.py for otf-api v0.15.4 restructured API (`otf.workouts.get_workouts()`)
- **Only 16 workouts returned** — OTF API silently truncates large results; added 90-day chunked fetching with dedup

### Changed
- `client.py` rewritten for otf-api v0.15.4 sub-object API structure
- `stats` command reads from local SQLite DB (was: live API fetch every run)

---

## Backlog

### Planned Features
- [ ] **DB-backed visualisations** — rewire `visualize` command to read from local DB instead of live API
- [ ] **DB-backed comparisons** — rewire `compare` command to use local DB + reddit_posts table
- [ ] **Query command** — `python main.py query --last 30` for quick date-range queries
- [ ] **Export command** — dump SQLite → JSON/CSV for sharing or migration
- [ ] **Workout detail view** — `python main.py workout <id>` to show full telemetry for one session
- [ ] **Coach/studio analytics** — breakdown by coach and studio with trends
- [ ] **Reddit NLP parsing** — extract structured stats from unstructured Reddit post text
- [ ] **Benchmark tracking** — display challenge results and personal records over time
- [ ] **Progress dashboard** — month-over-month and quarter-over-quarter trends
- [ ] **Multi-user support** — separate DB profiles for household members

### Known Issues
- Visualisation and comparison commands still use live API fetch (not local DB yet)
- Reddit post stat extraction is regex-based and misses many post formats
- Body composition sync depends on OTF API endpoint availability (may return empty)
- numpy 2.x prebuilt wheels crash on CPUs without AVX2 (Intel Atom, older Celeron) — must build 1.26.4 from source
