# JobNotifier

Personal, low-cost job-posting monitor. See [SPEC.md](SPEC.md) for the full design.

Currently implemented:
- **Tier 1** — public aggregator repos (e.g. SimplifyJobs' `Summer2026-Internships`
  and `New-Grad-Positions`), read via the raw GitHub content CDN.
- **Tier 2** — ATS adapters (Greenhouse, Lever, Ashby), driven by a company→slug
  mapping in `config/config.yaml`. See `src/jobnotifier/sources/tier2_ats/`.
- **Tier 3** — hand-written scrapers for proprietary career pages with no ATS API.
  See `src/jobnotifier/sources/tier3_scrapers/`.
- **Tier 4** — a plain manual-check list, not a fetched source: companies unresolved
  by Tiers 1-3 go in `config.yaml` under `sources.tier4_manual` (validated on load —
  no duplicates, no entry that also has a working Tier 2/3 row) and are checked by
  hand. The pipeline never touches this list; see SPEC.md §4.

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
