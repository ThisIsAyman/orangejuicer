# Changelog

All notable changes to orangejuicer are documented here.

## [Unreleased]

### Added
- **Web dashboard** (`web/`) — React + TypeScript static site with drag-and-drop JSON import, workout charts (HR, tread, rower), summary cards, zone distribution, and OTF-inspired dark theme. Hosted via GitHub Pages.
- **GitHub Actions** (`.github/workflows/deploy.yml`) — automated build and deploy of web dashboard on push
- **Local SQLite database** with 9-table schema (studios, workouts, treadmill/rower summaries, telemetry, reddit_posts, benchmarks, body_composition, sync_log)
- **Sync engine** (`orangejuicer/sync.py`) — full & incremental sync from OTF API with 90-day chunked fetching for large histories (1000+ workouts)
- **Demo/mock data system** (`orangejuicer/demo.py`) — generate 200 realistic synthetic workouts + 150 Reddit posts for development/testing without API credentials
- **JSON fixture files** (`fixtures/`) — committed demo data for instant `sync --demo`
- **CLI: `sync` command** with `--full`, `--demo`, `--capture` flags
- **CLI: `stats` command** now reads from local database instead of live API
- **Capture mode** (`sync --capture`) — saves raw API responses as JSON for offline replay
- **DB adapters** (`orangejuicer/adapters.py`) — convert SQLite rows to domain dataclasses with filtering (date range, coach, studio)
- **CLI: `workout` command** — detailed single-workout view with HR zones, treadmill/rower metrics, ASCII telemetry sparkline
- **CLI: `query` command** — filter workouts by `--last N`, `--from/--to`, `--coach`, `--studio` with formatted table output
- **CLI: `export` command** — export to JSON or CSV (`--format json|csv`), with optional `--full` for telemetry
- **CLI: `visualize` and `compare`** now read from local DB (no API credentials needed after sync)
- **106 tests** across all modules

### Fixed
- **numpy SIGILL crash** on Intel Atom D510 — pinned to numpy 1.26.4 built from source (AVX2-free)
- **`get_workout_history` AttributeError** — updated client.py for otf-api v0.15.4 restructured API (`otf.workouts.get_workouts()`)
- **Only 16 workouts returned** — OTF API silently truncates large results; added 90-day chunked fetching with dedup
- **Body composition sync error** (#13) — no longer logs tracebacks when endpoint is unavailable

### Changed
- `client.py` rewritten for otf-api v0.15.4 sub-object API structure
- `visualize` and `compare` commands read from local SQLite DB (were: live API fetch every run)
- `stats` command reads from local SQLite DB (was: live API fetch every run)

Features, bugs, and backlog are tracked in [GitHub Issues](https://github.com/ThisIsAyman/orangejuicer/issues).
