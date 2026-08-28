# JobNotifier

Personal, low-cost job-posting monitor. See [SPEC.md](SPEC.md) for the full design.

Currently implemented: **Tier 1** (public aggregator repos, e.g. SimplifyJobs'
`Summer2026-Internships` and `New-Grad-Positions`, read via the raw GitHub content
CDN). Tiers 2-4 (ATS adapters, hand-written scrapers, manual-check list) are not
yet implemented — see `src/jobnotifier/sources/tier2_ats/` and
`src/jobnotifier/sources/tier3_scrapers/`.

## Setup

```
pip install -e ".[dev]"
cp .env.example .env   # fill in your Discord webhook URL, then export it
```

## Running locally

```
export DISCORD_WEBHOOK_URL="<your webhook url>"
python run.py
```

## Testing

```
pytest -m "not live"     # fast, fully offline (default CI suite)
pytest -m live tests/live  # hits real sources; run manually or via the
                            # scheduled live-smoke-test workflow
```

## Deployment

Runs as a scheduled GitHub Actions workflow (`.github/workflows/run.yml`) on a
**private** repo, every 4 hours. State (`state/seen_jobs.json`) is committed
back to `main` by the workflow itself. Requires a `DISCORD_WEBHOOK_URL` repo
secret.
