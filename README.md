# orangejuicer 🍊

**OTF Data Fetcher** — authenticate, download, visualise, and compare your
[OrangeTheory Fitness](https://www.orangetheory.com/) workout data, then
benchmark it against the community on [r/orangetheory](https://www.reddit.com/r/orangetheory/).

---

## Features

| Feature | Description |
|---------|-------------|
| 🔐 **Authentication** | Log in to `api.orangetheoryfitness.com` via the [`otf-api`](https://github.com/NodeJSmith/otf-api) library using email/password (or env vars). |
| 📥 **Data download** | Fetch your full workout history: splat points, calories, heart-rate zones, step count, coach, studio, and more. |
| 📊 **Visualisations** | Static PNG charts (splat points over time, calories, HR zone distribution, workout frequency) **plus** an interactive HTML dashboard. |
| 🔴 **Reddit comparison** | Scrape `r/orangetheory` with [`praw`](https://praw.readthedocs.io/) to build community benchmarks; see where you rank. |

---

## Quick start

### 1. Clone & install

```bash
git clone https://github.com/ThisIsAyman/orangejuicer.git
cd orangejuicer
pip install -r requirements.txt
```

### 2. Configure credentials

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

### 3. Run

```bash
# Print summary statistics
python main.py stats

# Generate all workout charts  →  output/
python main.py visualize

# Compare your stats against Reddit community data  →  output/
python main.py compare

# Do everything at once
python main.py all
```

All charts are saved to the `output/` directory (configurable with `--output-dir`).

---

## CLI reference

```
usage: orangejuicer [-h] [--output-dir DIR] [--limit N] [--reddit-limit N]
                    {stats,visualize,compare,all}

Fetch, visualise, and compare OrangeTheory Fitness data.

subcommands:
  stats       Print summary statistics to the console
  visualize   Generate workout visualisation charts
  compare     Compare personal data against Reddit community data
  all         Run stats + visualize + compare

options:
  --output-dir DIR    Directory where charts are saved (default: output/)
  --limit N           Maximum number of OTF workouts to retrieve (default: 100)
  --reddit-limit N    Maximum number of Reddit posts to fetch (default: 200)
```

---

## Generated charts

| File | Description |
|------|-------------|
| `splat_points_over_time.png` | Line chart of splat points per workout with your personal average |
| `calories_over_time.png` | Bar chart of calories burned per workout |
| `hr_zones_distribution.png` | Donut + bar charts showing cumulative time in each HR zone |
| `workout_frequency_heatmap.png` | Workouts by day-of-week and monthly trend |
| `dashboard.html` | Interactive Plotly dashboard (splat points, calories, HR) |
| `comparison_splat_points.png` | Your avg splat points vs Reddit community percentiles |
| `comparison_calories.png` | Your avg calories vs Reddit community percentiles |
| `comparison_percentile_rank.png` | Your estimated percentile rank in the community |

---

## Project structure

```
orangejuicer/
├── orangejuicer/
│   ├── __init__.py
│   ├── auth.py             # OTF authentication wrapper
│   ├── client.py           # OTF data fetching & normalisation
│   ├── reddit.py           # Reddit scraper & stat parser
│   ├── visualizations.py   # Matplotlib / Plotly chart generation
│   └── comparisons.py      # Personal vs. community comparison
├── tests/
│   ├── test_auth.py
│   ├── test_client.py
│   ├── test_comparisons.py
│   ├── test_reddit.py
│   └── test_visualizations.py
├── main.py                 # CLI entry point
├── requirements.txt
├── pyproject.toml
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
* Reddit data is fetched read-only via the official Reddit API; you must comply
  with [Reddit's API terms](https://www.redditinc.com/policies/data-api-terms).
* Never share your credentials.  Keep `.env` out of version control (it is
  already listed in `.gitignore`).

---

## License

[MIT](LICENSE) © 2026 Ayman El-Khashab
