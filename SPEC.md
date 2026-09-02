# JobNotifier — Specification

## 1. Overview

JobNotifier is a personal, low-cost tool that monitors job postings from a curated set
of sources and sends Discord notifications for new postings matching a keyword-based
filter. It runs as a scheduled GitHub Actions workflow on a private repo, keeps all
state as a JSON file committed to the repo itself, and is designed to run for well
under $10/month.

## 2. Goals / Non-Goals

**Goals**
- Monitor a tiered mix of sources (public aggregator repos, ATS platform APIs, a small
  number of hand-written scrapers, and an explicit manual-check list) for new job
  postings.
- Filter postings by title keywords, location, remote status, and seniority.
- Notify a single Discord channel per new, relevant posting.
- Correctly dedup postings across sources and handle reopened postings without being
  fooled by transient source failures.
- Stay within a $10/month total cost ceiling.

**Non-Goals (v1)**
- LLM-based relevance scoring — filtering is keyword/rule-based only.
- Salary-based filtering — salary is notification-display-only, never a filter input.
- Multi-profile support — one filter set, one Discord destination, one source list.
- **Resume optimization in any form** — no feature, no placeholder section, no
  pluggable hook, no extension point. Considered and explicitly cut.
- Automated Notion sync — Notion, where used, stays a manually-curated tracker.

## 3. Architecture

Pipeline stages, run once per scheduled invocation:

1. **Fetch** — pull postings from each configured source, per its tier (see §4).
   Fetch success/failure is tracked per source.
2. **Parse / Normalize** — convert each source's raw response into a common posting
   shape (company, title, location, url, date, salary if present, source id).
3. **Dedup / diff against state** — compute each posting's canonical key, compare
   against the committed state file, and determine which are new, reopened, or already
   seen. Sources that failed to fetch are excluded from closed-posting inference (§9).
4. **Filter** — apply the keyword/location/remote/seniority filter (§8) and the 7-day
   freshness window (§6) to the new/reopened set.
5. **Notify** — send Discord messages for postings that pass filtering, respecting the
   per-run notification cap and send throttling (§10).
6. **Prune & commit state** — drop state entries older than 30 days, commit the updated
   state file back to `main` (§14).

**Deployment**: a GitHub Actions workflow on a **private repository**, scheduled via
`cron` to run **every 4 hours**. GitHub scheduled workflows are **best-effort** — runs
can be delayed or occasionally dropped under scheduler load, so this cadence is a
target, not a guarantee. A **concurrency group** ensures at most one run executes at a
time, protecting the committed state file from races.

## 4. Sources — Four Tiers

Sources are built and prioritized in this order. **Adapters are the default; per-company
HTML scraping is the anti-pattern** and is used only where nothing else works.

- **Tier 1 — Public aggregator repos (via GitHub API)**: Reads job-listing repositories
  (Simplify and similar internship/new-grad listing repos) through the GitHub API. This
  is the broadest-coverage tier and is also the **only** channel used for large
  proprietary-site employers (Google, Meta, Microsoft, Apple, Amazon, Uber) — these are
  never scraped directly.
- **Tier 2 — ATS adapters, one per platform**: A single adapter implementation per ATS
  platform — Greenhouse, Ashby, Lever, Workday, iCIMS — driven by a company→slug mapping
  in config. Adding a company on a supported platform means adding a config row, not
  writing new code.
- **Tier 3 — Hand-written one-off scrapers, capped at 5**: Reserved for proprietary
  career pages with no ATS API, specifically the quant-shop employers the user cares
  about most: Citadel, Citadel Securities, Two Sigma, D. E. Shaw, Palantir. Each scraper
  is a deliberate, individually-justified cost added ad hoc — this tier is explicitly
  not meant to grow into a general scraping framework.
- **Tier 4 — Manual-check list**: Any employer not resolved by Tiers 1–3 goes on a plain
  list the user checks by hand, rather than expanding Tier 3.

Scraping-specific policy (HTTP method, politeness, pagination — §11) applies only to
Tier 3, since it's the only tier that scrapes HTML.

## 5. Discovery Script

A standalone script that populates and verifies the company→ATS→slug config, replacing
signature-detection on rendered careers pages with **direct endpoint probing**:

1. Generate candidate slugs from a company name: lowercased, dehyphenated, with and
   without common corporate suffixes, plus known alternate names (e.g. `anysphere` for
   Cursor).
2. Hit each ATS platform's public API directly with each candidate slug. A `200`
   response containing a valid job array is the only accepted proof of a match — no
   HTML/DOM signature heuristics.
3. Output a table of `company | ats_platform | slug | confirmed|unconfirmed`.

The script's first job is to **re-verify every row of the existing, partly-guessed
detection table**, not just resolve currently-unknown companies — several current slugs
are unconfirmed guesses.

## 6. Dates & Freshness

- Date precedence for a posting: **aggregator-supplied date** (Tier 1) first, then
  **ATS published date** (Tier 2/3 API responses), then **no date at all** — page-
  rendered display dates are never parsed as a fallback.
- **`updated_at` is never used** as a posting's date, since a content edit bumps it and
  would incorrectly resurface a stale posting as newly relevant.
- Postings are filtered to those dated within the **last 7 days**, where a date exists.
- Where no date is available (Tier 3 pages with no structured date), the posting is
  **seeded silently into state on first sight** (no notification), and only a later
  absent→present transition is treated as new.

## 7. Bootstrap

- **Seed mode**: on first run for a newly-added source (or the very first run overall),
  the state file is populated from that source's current postings
   **without sending any notifications** — prevents a flood of "new" alerts for jobs that were already posted.
   The seed window is limited to postings dated within the last 30 days 
   (configurable, and separate from the 7-day freshness filter used on normal runs)
- **Per-channel notification cap**: independent of seed mode, a configured maximum
  number of Discord messages per run, applied independently to each of the two
  channels (§10), prevents a large batch of genuinely new postings (e.g. a company
  posting many roles at once) from flooding either channel.

## 8. Filtering

Keyword/rule-based only, applied after dedup and the freshness filter:

- **Title include/exclude keyword lists**.
- **Location list**, a **remote-only** toggle, and a **US-only** toggle. US-only is a
  country-level check (US state/city, "United States", or "Remote in USA"), independent
  of the location list, so the location list can stay empty while still constraining to
  the US. A posting merged across several offices (§9) passes if any one of them is
  US-based. A bare "Remote" with no country given is ambiguous and is not excluded.
- **Seniority**, classified from title keywords (e.g. exclude "Senior"/"Staff"/
  "Principal").
- **Salary is display-only** — included in notifications when a source exposes it, but
  never used as a filter condition.

## 9. Dedup & State

- **Canonical key**: a normalized `(company, title, location)` match used to collapse
  the same role appearing through two sources (e.g. a Tier 2 company board and a Tier 1
  aggregator entry) into a single notification.
- **Ambiguity tie-break**: when a canonical-key match is uncertain, the system does
  **not** collapse — it prefers sending a duplicate notification over silently missing a
  posting.
- **State file schema** (JSON, keyed by canonical job key):
  ```
  {
    "<job_key>": {
      "first_seen": "<date>",
      "last_seen": "<date>",
      "status": "open" | "closed",
      "source": "<source_id>",
      "url": "<url>"
    }
  }
  ```
- **Closed/reopened detection, gated by fetch success**: a job's absence from a source's
  current results is only interpreted as "closed" **if that source fetched successfully
  in the current run**. Fetch success is tracked per source specifically so that a
  failing source can never mark its entire job set closed — which would otherwise cause
  every one of those jobs to be incorrectly re-notified as "reopened" once the source
  recovers.
- **Reopen rule**: a job key transitioning from `closed` back to an active posting
  re-notifies as new. A content edit alone does not re-notify (see §6 on `updated_at`).
- **Pruning**: entries with `last_seen` older than 30 days are dropped each run.
- **Concurrency**: guarded by the GitHub Actions concurrency group (§3) so the committed
  state file is never written by two overlapping runs.

## 10. Notifications

- **Channels**: two Discord webhooks, split by a posting's term (`Posting.terms`, only
  ever populated by the Tier 1 aggregator feed) — one for `summer_term` (default
  `"Summer 2027"`), one for everything else. A posting with no term at all (e.g. the
  non-internship Tier 2/3 sources) defaults to the summer channel. A posting whose
  *entire* term set is exactly one of `exclude_exact_terms` (default: a lone
  `"Fall 2026"`) is dropped — not sent to either channel — rather than treated as
  off-season; a posting tagged with an excluded term *plus* something else is not
  excluded.
- **Granularity**: one message per new/reopened posting that passes filtering, not a
  digest — sends are throttled/spaced out to stay under Discord's ~30 messages/minute
  webhook rate limit. `per_channel_cap` (§7) bounds each channel independently, not
  their combined total.
- **Message fields**: title, company, location/remote status, application link, source,
  posted date (when available), salary (when available), and the **canonical job key**
  (as a short ID line or URL fragment), so any message can be traced back to its
  state-file entry later.

## 11. Scraping Details (Tier 3 only)

- **Fetch method**: HTTP + HTML parsing (requests/httpx + BeautifulSoup) first;
  Playwright headless-browser fallback per source, used only where a page requires JS
  rendering.
- **Politeness**: respect `robots.txt`, apply per-domain rate limiting/delay, use an
  identifying User-Agent.
- **Pagination**: relevant only to Tier 3. Sort order is recorded per source.
  Page-one-only fetching is valid **only** when the page sorts by date; if a page sorts
  by relevance instead, page-one-only is invalid (would silently miss postings) and
  pagination must be implemented for that source.

## 12. Failure Handling

- A source that fails to fetch is logged and skipped; the run continues processing the
  remaining sources (and that source is excluded from closed-posting inference, §9).
- If more than a threshold of configured sources fail within a single run (default:
  **>50%**, configurable), the run **aborts and exits nonzero**.
- That nonzero exit **is** the alerting mechanism: GitHub's built-in workflow-failure
  email notifies the user of a systemic break. No custom failure-alerting code is built
  — per-source failures are log-only, and a full-run abort is surfaced for free via
  GitHub's native email, not a bespoke notification path.

## 13. Testing

- **Static fixtures**: hand-saved HTML/JSON sample responses per source/parser, used for
  fast, fully offline unit tests that run in normal CI.
- **Scheduled live smoke test**: a separate workflow (not part of normal CI) that hits
  every real source on a schedule and asserts a nonzero postings count with required
  fields present. This is the actual early-warning signal for silent source breakage,
  since production run failures are only logged (§12) and not otherwise actively
  monitored.

## 14. State Commits

- The state file lives on **`main`**, committed by the workflow itself at the end of
  each run.
- On a push conflict (e.g. a manual commit landed between fetch and push), the workflow
  **rebases and retries** rather than failing the run outright.
- Regular commits have a secondary benefit worth noting: they keep the repository
  active, which prevents GitHub from auto-disabling a scheduled workflow after 60 days
  of repository inactivity.

## 15. Cadence & Cost Model

- **Cadence**: every 4 hours (6 runs/day, ~180 runs/month).
- **Actions minutes**: on a private repo, ~180 runs/month at an estimated 3–8 minutes
  per run (upper end accounting for occasional Tier 3 Playwright use) is roughly
  **540–1,440 minutes/month**, comfortably within the 2,000 free Actions minutes/month
  on GitHub's Free plan.
- **Other costs**: Discord webhooks are free; no paid job-board APIs are used. A small
  proxy budget is reserved (not committed upfront) within the overall $10/month ceiling,
  in case a Tier 3 source starts blocking the Actions runner's IP.

## 16. Config Schema

Single profile, roughly:

```yaml
sources:
  tier1_aggregators:
    - repo: "owner/simplify-jobs-repo"
  tier2_ats:
    - platform: greenhouse
      company: "example-co"
      slug: "examplecoslug"
    - platform: lever
      company: "another-co"
      slug: "anothercoslug"
  tier3_scrapers:
    - company: "citadel"
      fetch_method: http   # or "playwright"
      sort_order: date     # or "relevance"
  tier4_manual:
    - "some-company-with-no-viable-source"

filters:
  title_include: ["software engineer", "backend"]
  title_exclude: ["senior", "staff", "principal"]
  locations: ["New York, NY", "Remote"]
  remote_only: false
  us_only: true
  seniority_exclude: ["senior", "staff", "principal"]

notification:
  summer_webhook_url: "${DISCORD_WEBHOOK_URL_SUMMER}"           # GitHub Actions secret
  off_season_webhook_url: "${DISCORD_WEBHOOK_URL_OFF_SEASON}"   # GitHub Actions secret
  per_channel_cap: 10
  summer_term: "Summer 2027"
  exclude_exact_terms: ["Fall 2026"]

state:
  path: "state/seen_jobs.json"
  retention_days: 30

failure:
  abort_threshold_pct: 50
```

## 17. Notion

Out of scope for v1. Discord is the live notification stream; Notion, if used, remains a
tracker the user fills in manually for the subset of postings (~10%) they actually apply
to. Possible future addition, not designed here: a CLI that takes a job URL and creates
the corresponding Notion row from the matching state-file entry.
