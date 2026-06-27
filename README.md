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

## Use it without Python (browser dashboard)

The `web/` dashboard can pull your data **directly in the browser** — no Python,
no install for the end user. Sign in with your OTF email/password and your
workouts sync straight into the browser's local storage (IndexedDB), where you
can browse, chart, and export them. Your synced data lives only in your browser;
**export** it to JSON/CSV anytime (interchangeable with `python main.py export`),
or drag-and-drop a CLI-exported JSON file to load it without logging in at all.

To host your own instance you deploy two things — a **static site** (the
dashboard, e.g. on GitHub Pages) and a tiny **relay proxy** (explained next).

### What is the proxy? (do I need Azure/AWS?)

**No — it is not a managed cloud service you provision and babysit.** It's a
~100-line **stateless serverless function** that you deploy *once* and then
forget. The recommended host is **Cloudflare Workers** (free tier, no
servers/VMs), deployed with a single command; it can also run on Vercel/Netlify
edge functions or any Node host.

It exists only to work around two **browser** restrictions — it has no other job:

1. **CORS** — browsers refuse to read responses from OrangeTheory's private API
   unless OTF whitelists your site (it never will). A plain server isn't bound by
   CORS, so the proxy calls OTF and adds the one header that lets *your* page
   read the reply.
2. **Forbidden `User-Agent`** — OTF expects a mobile-app user agent
   (`okhttp/4.12.0`) that browser JavaScript is not allowed to set; a server can.

The proxy **stores nothing, logs nothing, and holds no credentials.** Your
browser sends its login token with each request and the proxy just forwards it
to an allowlist of three OTF hostnames. If it vanished, no data would be lost or
exposed. Full deploy details: [`proxy/README.md`](proxy/README.md).

### How a sync request flows

```
  Browser (the dashboard)            Relay proxy (Cloudflare Worker)        OrangeTheory
  ───────────────────────            ──────────────────────────────        ────────────
  Sign in (Cognito SRP) ───────────────────────────────────────────────►  AWS Cognito
    password → Cognito only          (login skips the proxy entirely)       (CORS-enabled)
    tokens stored in YOUR browser ◄──────────────────────────────────────  ID/refresh tokens

  Sync: GET /relay?target=…  ──────►  adds User-Agent + CORS,
    Authorization: Bearer <token>     forwards token unchanged   ─────────►  api.orangetheory.*
                                       (stores nothing)           ◄─────────  workout JSON
  store in IndexedDB         ◄──────  relays body + CORS header
```

### Self-hosting walkthrough

**Prerequisites:** Node 20+, a free [Cloudflare](https://dash.cloudflare.com/sign-up)
account, and this repo cloned.

**1. Deploy the relay proxy.**

```bash
cd proxy
npx wrangler login          # one-time browser auth to Cloudflare
npx wrangler deploy
```

Wrangler prints a URL like `https://otf-proxy.<you>.workers.dev`. Edit
`proxy/wrangler.toml` and set `ALLOWED_ORIGIN` to the origin you'll serve the
dashboard from (e.g. `https://<you>.github.io`) so only your site can use the
proxy, then re-run `npx wrangler deploy`.

**2. Deploy the dashboard pointed at that proxy.** The proxy URL is baked in at
build time via `VITE_OTF_PROXY_URL` (see [`web/.env.example`](web/.env.example)).

- *GitHub Pages (automated):* in your repo, go to **Settings → Secrets and
  variables → Actions → Variables** and add a variable named **`OTF_PROXY_URL`**
  set to your Worker URL. The existing
  [`deploy.yml`](.github/workflows/deploy.yml) workflow injects it at build time
  and publishes `docs/` to Pages.
- *Any static host (manual):*
  ```bash
  cd web
  npm ci
  VITE_OTF_PROXY_URL=https://otf-proxy.<you>.workers.dev npm run build
  # → upload the generated ../docs/ folder to your static host
  ```

**3. Use it.** Open your site, click **Sign in**, enter your OTF
email/password, then **Sync all**. Subsequent visits keep you logged in; use
**Sync new** to fetch only workouts you don't already have.

### Proxy hosting alternatives

| Host | Cost | Notes |
|------|------|-------|
| **Cloudflare Workers** | Free tier | Recommended; `npx wrangler deploy`. See [`proxy/README.md`](proxy/README.md). |
| Vercel / Netlify Edge | Free tier | Same relay logic; thin platform wrapper around `proxy/worker.js`. |
| Any Node host | Varies | Port the handler to a small HTTP server; keep the host allowlist. |

### Trust model & privacy

- Your **password** goes only to AWS Cognito during login; it never touches the
  proxy or any orangejuicer server.
- Login **tokens** are stored only in your browser (IndexedDB/localStorage) so
  you stay signed in; **Sign out** clears them.
- The proxy is a **dumb, stateless relay**: no storage, no logging, no
  credentials, an OTF-only host allowlist, and it refuses upstream redirects so
  your token can't be replayed off-allowlist.
- Because tokens transit the proxy *in flight*, run an instance **you** trust
  (self-hosting it puts you in control). For **zero** third parties in the path,
  the client layer (`web/src/otf/`) is transport-agnostic, so the same code can
  ship as a browser extension that calls OTF directly with no proxy (planned).

### Local end-to-end dev

```bash
# terminal 1 — run the proxy locally
cd proxy && npx wrangler dev          # http://localhost:8787

# terminal 2 — run the dashboard against it
cd web && npm install
VITE_OTF_PROXY_URL=http://localhost:8787 npm run dev
```

---

## Export to Strava

OrangeTheory doesn't sync to Strava directly, but orangejuicer can emit a
**TCX file per workout** that Strava imports natively — heart rate, time,
distance, cadence and speed (OTF has no GPS, so Strava auto-tags it as an indoor
activity). No Garmin/Polar/TrainingPeaks detour is needed.

**From the CLI:**

```bash
# Writes one <date>_<psid>.tcx + matching .txt per workout into output/tcx/
python main.py export --format tcx
python main.py export --format tcx --output ~/strava-tcx   # custom directory
```

**From the browser dashboard:** click **Export TCX (Strava)** in the sync bar to
download a zip of every workout (`.tcx` + `.txt`), or open a single workout and
use **Export TCX** / **Copy description**.

**Then upload:**

1. Go to [strava.com/upload/select](https://www.strava.com/upload/select) and
   drag the `.tcx` files on (you can drop up to 25 at once).
2. Strava ignores the metadata embedded in the file's `<Notes>`, so to get the
   coach/studio/class onto the activity, open it and **paste the matching `.txt`
   description** (the dashboard's "Copy description" button does the same).

Re-uploading the same class creates a duplicate in Strava — filenames include the
date and performance-summary id so you can tell which ones you've already done.

---


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
│       ├── otf/            # Browser OTF client (auth, transport, endpoints, sync)
│       └── store/          # IndexedDB (Dexie) store, import & export
├── proxy/                  # Stateless Cloudflare Worker relay for live sync
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
