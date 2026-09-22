# JobNotifier

JobNotifier monitors a curated set of job sources and sends Discord notifications for new postings matching a keyword-based filter. Notifications are split across two channels — Summer 2027 internships and off-season roles. It runs entirely on free tiers (GitHub Actions, Discord webhooks), so there is no operating cost.

## Sources

Sources are organized into four tiers, ordered by reliability:

- **Tier 1 — Public aggregator repos.** Curated job-listing repositories on GitHub (currently SimplifyJobs' `Summer2027-Internships`), fetched as raw JSON. Maintained full-time by others, giving the widest coverage for no upkeep.
- **Tier 2 — ATS APIs.** Company career pages backed by Greenhouse, Lever, or Ashby, mapped by slug in `config/config.yaml`. A real API is always preferred over scraping.
- **Tier 3 — Hand-written scrapers.** For proprietary career pages with no API. Kept deliberately small — each scraper breaks silently the next time a company redesigns its site, so this tier is reserved for companies worth that maintenance cost.
- **Tier 4 — Manual check list.** Companies with no API and no scrapable site. The pipeline never touches this list; it exists as a reminder.

## Design notes

- **State is a JSON file committed to the repo** (`state/seen_jobs.json`), not a database. No server to host or pay for, and every state change is visible as a normal git commit.
- **A source that fails to fetch never marks its jobs closed.** Otherwise one flaky run would close out everything from that source, and all of it would re-notify as "new" on recovery.
- **Filtering is plain keyword rules, not an LLM.** Deterministic, free, and sufficient — relevance is defined by the filter config, not inferred.

## Setup

```
pip install -e ".[dev]"
cp .env.example .env   # fill in your two Discord webhook URLs, then export them
```

## Running locally

```
export DISCORD_WEBHOOK_URL_SUMMER="<summer channel webhook url>"
export DISCORD_WEBHOOK_URL_OFF_SEASON="<off-season channel webhook url>"
python run.py
```

## Testing

```
pytest -m "not live"       # fast, fully offline (default CI suite)
pytest -m live tests/live  # hits real sources; run manually or via the
                           # scheduled live-smoke-test workflow
```

The offline suite validates logic against fixtures. Only the live suite verifies that a source hasn't started blocking or reshaping its responses — a broken source otherwise fails silently in production (logged and skipped, not alerted on) until the live test runs against it.

## Deployment

Runs as a scheduled GitHub Actions workflow (`.github/workflows/run.yml`), every 4 hours. State (`state/seen_jobs.json`) is committed back to `main` by the workflow itself. Requires `DISCORD_WEBHOOK_URL_SUMMER` and `DISCORD_WEBHOOK_URL_OFF_SEASON` repo secrets.
