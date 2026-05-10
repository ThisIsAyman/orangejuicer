# orangejuicer 🍊

**Your OrangeTheory data, locally.** Authenticate, sync, browse, visualise,
and compare your [OrangeTheory Fitness](https://www.orangetheory.com/) workout
data — then benchmark it against the community on
[r/orangetheory](https://www.reddit.com/r/orangetheory/).

All data is stored in a local SQLite database so you never have to re-fetch.

---

## Features

| Feature | Status | Description |
|---------|--------|-------------|
| 🔐 **Authentication** | ✅ | Log in via [`otf-api`](https://github.com/NodeJSmith/otf-api) (email/password or env vars). |
| 📥 **Local sync** | ✅ | Full & incremental sync of workouts, telemetry, benchmarks, body composition, and Reddit posts into a local SQLite database. Handles 1000+ workouts via 90-day chunked fetching. |
| 🎭 **Demo mode** | ✅ | Generate 200 realistic synthetic workouts + 150 Reddit posts for development/testing — no API credentials needed. |
| 📊 **Statistics** | ✅ | CLI summary stats from the local database (splats, calories, HR, coaches, studios). |
| 📈 **Visualisations** | 🚧 | PNG charts + interactive HTML dashboard (splat trends, calories, HR zones, workout frequency). |
| 🔴 **Reddit comparison** | 🚧 | Compare your stats against r/orangetheory community benchmarks. |

---

## Quick start

### 1. Clone & install

```bash
git clone https://github.com/ThisIsAyman/orangejuicer.git
cd orangejuicer
pip install -r requirements.txt
```

### 2. Try it instantly with demo data (no credentials needed)

```bash
python main.py sync --demo
python main.py stats
```

### 3. Or configure credentials for real data

Copy `.env.example` to `.env` and fill in your details:

```bash
cp .env.example .env
```

```dotenv
# OrangeTheory Fitness
OTF_EMAIL=your_email@example.com
OTF_PASSWORD=your_password

# Reddit API  (create an app at https://www.reddit.com/prefs/apps — choose "script")
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=orangejuicer/0.1.0 by u/your_reddit_username
```

### 4. Sync & explore

```bash
# Sync all data from the OTF API (first run = full history)
python main.py sync

# Subsequent syncs only fetch new data (with 7-day lookback)
python main.py sync

# Force a full re-sync
python main.py sync --full

# Save raw API responses as JSON fixtures for offline replay
python main.py sync --capture

# Print summary statistics from local database
python main.py stats

# Generate all workout charts → output/
python main.py visualize

# Compare your stats against Reddit community → output/
python main.py compare

# Do everything at once
python main.py all
```

All charts are saved to the `output/` directory (configurable with `--output-dir`).

---

## CLI reference

```
usage: orangejuicer [-h] [--output-dir DIR] [--limit N] [--reddit-limit N]
                    {sync,stats,visualize,compare,all}

subcommands:
  sync        Sync OTF and Reddit data to local database
  stats       Print summary statistics to the console
  visualize   Generate workout visualisation charts
  compare     Compare personal data against Reddit community data
  all         Run stats + visualize + compare

sync options:
  --full      Force a full re-sync (fetch all history)
  --demo      Load demo/fixture data (no API needed)
  --capture   Save raw API responses as JSON fixtures

global options:
  --output-dir DIR    Directory where charts are saved (default: output/)
  --limit N           Maximum OTF workouts to retrieve (default: 100)
  --reddit-limit N    Maximum Reddit posts to fetch (default: 200)
```

---

## Database

Data is stored in `~/.orangejuicer/orangejuicer.db` (override with `OJ_DB_PATH` env var).

**Schema** (9 tables):

| Table | Description |
|-------|-------------|
| `studios` | Studio metadata (name, location, timezone) |
| `workouts` | One row per completed class (date, coach, calories, splats, HR, zones) |
| `treadmill_summary` | Per-workout treadmill aggregates (pace, speed, distance, incline) |
| `rower_summary` | Per-workout rower aggregates (pace, power, cadence, distance) |
| `telemetry` | Full per-second time-series (~150 points/workout: HR, tread, rower) |
| `reddit_posts` | Parsed r/orangetheory posts with extracted stats |
| `benchmarks` | Challenge/benchmark results |
| `body_composition` | Body composition records |
| `sync_log` | Per-entity sync cursors for incremental sync |

### Workout data model

Each workout contains three levels of data:

#### Workout summary (one row per class)

| Field | Type | Description |
|-------|------|-------------|
| `performance_summary_id` | text | Primary key (from OTF API) |
| `workout_date` | date | Class date (ISO) |
| `starts_at` | datetime | Full class start time |
| `class_name` / `class_type` | text | e.g. "Orange 60", "Lift 45" |
| `coach_name` | text | Instructor name |
| `studio_uuid` | text | FK to studios table |
| `calories_burned` | int | Total calories |
| `splat_points` | int | Minutes in orange + red zones |
| `step_count` | int | Total steps |
| `active_time_seconds` | int | Active workout duration |
| `avg_hr` / `max_hr` / `peak_hr` | int | Heart rate stats (bpm) |
| `avg_hr_percent` / `peak_hr_percent` | int | % of max heart rate |
| `zone_gray_min` .. `zone_red_min` | int | Minutes in each HR zone |
| `class_rating` / `coach_rating` | int | User ratings (0–3) |

#### Equipment summaries (one row per workout, per equipment)

**Treadmill** (`treadmill_summary`):

| Field | Type | Description |
|-------|------|-------------|
| `avg_speed` / `max_speed` | real | mph |
| `avg_pace` / `max_pace` | real | min/mile |
| `total_distance` | real | miles |
| `avg_incline` / `max_incline` | real | % grade |
| `elevation_gained` | real | feet |
| `moving_time` | real | seconds on the tread |

**Rower** (`rower_summary`):

| Field | Type | Description |
|-------|------|-------------|
| `avg_speed` / `max_speed` | real | speed units |
| `avg_pace` / `max_pace` | real | sec per 500m |
| `total_distance` | real | meters |
| `avg_cadence` / `max_cadence` | real | strokes per minute |
| `avg_power` | real | watts |
| `moving_time` | real | seconds on the rower |

#### Telemetry time-series (~150 samples per workout, every ~18 seconds)

| Field | Type | When populated | Description |
|-------|------|----------------|-------------|
| `relative_timestamp` | int | Always | Seconds from class start |
| `timestamp` | datetime | Always | Absolute time |
| `hr` | int | Full class | Heart rate (bpm) |
| `agg_splats` | int | Full class | Cumulative splat points at this moment |
| `agg_calories` | int | Full class | Cumulative calories at this moment |
| `tread_speed` | real | On treadmill only | Current speed (mph) |
| `tread_incline` | real | On treadmill only | Current incline (%) |
| `tread_distance` | real | On treadmill only | Cumulative distance (miles) |
| `row_speed` | real | On rower only | Current speed |
| `row_spm` | real | On rower only | Current strokes per minute |
| `row_distance` | real | On rower only | Cumulative distance (meters) |
| `row_pace` | int | On rower only | Current pace (sec per 500m) |

> **Note:** Equipment fields are `null` when you're not on that station (e.g. on the
> floor or transitioning). HR and cumulative fields are present throughout the entire class.
> You can derive per-interval speed/distance by computing deltas between consecutive samples.

---

## Project structure

```
orangejuicer/
├── orangejuicer/
│   ├── __init__.py
│   ├── auth.py             # OTF authentication wrapper
│   ├── client.py           # OTF data fetching & normalisation
│   ├── db.py               # SQLite schema, migrations, upsert functions
│   ├── sync.py             # Sync engine (full/incremental, chunked fetch)
│   ├── demo.py             # Synthetic data generator & fixture loader
│   ├── reddit.py           # Reddit scraper & stat parser
│   ├── visualizations.py   # Matplotlib / Plotly chart generation
│   └── comparisons.py      # Personal vs. community comparison
├── fixtures/
│   ├── demo_workouts.json  # 200 synthetic workouts (committed)
│   └── demo_reddit.json    # 150 synthetic Reddit posts (committed)
├── tests/                  # 106 tests (pytest)
├── web/                    # React + TypeScript web dashboard
│   └── src/
├── main.py                 # CLI entry point
├── requirements.txt
├── pyproject.toml
├── CHANGELOG.md
└── .env.example
```

---

## Running tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## Notes & disclaimer

* The OTF API is **unofficial** and may change without notice.  This project uses
  the community-maintained [`otf-api`](https://pypi.org/project/otf-api/) library.
* **CPU compatibility**: prebuilt numpy 2.x wheels require AVX2. On older CPUs
  (e.g. Intel Atom), install numpy 1.26.4 from source:
  `pip install numpy==1.26.4 --no-binary numpy`
* Reddit data is fetched read-only via the official Reddit API; you must comply
  with [Reddit's API terms](https://www.redditinc.com/policies/data-api-terms).
* Never share your credentials.  Keep `.env` out of version control (it is
  already listed in `.gitignore`).

---

## License

[MIT](LICENSE) © 2026 Ayman El-Khashab
