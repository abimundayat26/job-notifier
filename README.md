# JobNotifier

I got tired of refreshing career pages, so this checks them for me. It watches a
curated set of job sources and pings a Discord channel the moment something new
and relevant shows up — runs entirely on free tiers (GitHub Actions, Discord
webhooks), so it costs nothing to operate.

It looks in four places, ordered by how much they're trusted to just work:
- **Tier 1** — public aggregator repos on GitHub (currently SimplifyJobs'
  `Summer2027-Internships`), pulled straight off the raw content CDN. Someone
  else maintains these full-time, so it's the widest coverage for zero upkeep.
- **Tier 2** — each company's own ATS API (Greenhouse, Lever, Ashby), mapped by
  slug in `config/config.yaml`. A real API beats scraping every time, so this
  is the default whenever a company's ATS exposes one.
- **Tier 3** — a handful of hand-written scrapers for the proprietary career
  pages that have no API at all. Kept deliberately small — every scraper here
  is one more thing that silently breaks the next time a company redesigns
  its site, so it's reserved for companies worth that maintenance cost.
- **Tier 4** — everyone else: a plain list of companies to check by hand. Not
  worth writing a scraper for a company with no API and no site worth
  automating; the pipeline never touches this list, it's just a reminder.

A few other choices that aren't obvious from the code:
- **State is a JSON file committed to the repo, not a database.** No server to
  host or pay for, and every state change already shows up as a normal git
  commit — free history for free.
- **A source that fails to fetch never marks its own jobs "closed."** Otherwise
  one flaky day would close out everything from that source, and it'd all
  come back as "new" and re-notify the moment the source recovers.
- **Filtering is plain keyword rules, not an LLM.** Deterministic, free, and
  doesn't need to guess what "relevant" means — you already know.

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
