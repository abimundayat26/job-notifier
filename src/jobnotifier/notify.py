import logging
import time
from typing import Callable

import requests

from jobnotifier.config import NotificationConfig
from jobnotifier.models import Posting, canonical_key

logger = logging.getLogger(__name__)

# Discord webhooks are rate-limited to ~30 messages/minute; 2.5s spacing
# keeps a comfortable margin under that (SPEC.md §10).
THROTTLE_SECONDS = 2.5

# A merged multi-location posting (normalize.merge_locations) can run to
# hundreds of characters -- keep the notification skimmable by truncating at
# the last complete "; "-separated location that still fits, rather than
# showing the whole list.
_MAX_LOCATION_DISPLAY_LEN = 100


def _display_location(location: str) -> str:
    if len(location) <= _MAX_LOCATION_DISPLAY_LEN:
        return location
    truncated = location[:_MAX_LOCATION_DISPLAY_LEN]
    last_sep = truncated.rfind("; ")
    if last_sep > 0:
        truncated = truncated[:last_sep]
    return truncated + "..."


def build_message(posting: Posting) -> dict:
    fields = [
        {"name": "Company", "value": posting.company, "inline": True},
        {"name": "Location", "value": _display_location(posting.location), "inline": True},
        {"name": "Source", "value": posting.source_id, "inline": True},
    ]
    if posting.term:
        fields.append({"name": "Term", "value": posting.term, "inline": True})
    if posting.date_posted is not None:
        fields.append({"name": "Posted", "value": posting.date_posted.isoformat(), "inline": True})
    if posting.salary:
        fields.append({"name": "Salary", "value": posting.salary, "inline": True})
    fields.append({"name": "Job Key", "value": canonical_key(posting), "inline": False})

    return {
        "embeds": [
            {
                "title": posting.title,
                "url": posting.url,
                "fields": fields,
            }
        ]
    }


def send_notifications(
    postings: list[Posting],
    webhook_url: str,
    per_run_cap: int,
    post_fn: Callable = requests.post,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    """Sends one Discord message per posting, capped and throttled per SPEC.md §10.
    Returns the number of notifications actually sent.

    A single posting's send failing (a transient network error, a Discord
    429/5xx, a malformed embed) is logged and skipped rather than aborting
    the batch: it must never propagate out of here and prevent the caller
    from persisting this run's state, or an already-delivered notification
    earlier in the batch gets re-sent as a duplicate next run (its key would
    never have been recorded as seen).
    """
    to_send = postings[:per_run_cap]

    sent = 0
    for i, posting in enumerate(to_send):
        try:
            resp = post_fn(webhook_url, json=build_message(posting), timeout=15)
            resp.raise_for_status()
            sent += 1
        except Exception:
            logger.exception(
                "failed to send Discord notification for %s; continuing with remaining postings",
                canonical_key(posting),
            )
        if i < len(to_send) - 1:
            sleep_fn(THROTTLE_SECONDS)
    return sent


def classify_channel(posting: Posting, config: NotificationConfig) -> str | None:
    """Routes a posting to "summer" or "off_season", or excludes it (None).

    Only Tier 1 aggregator postings carry `terms` at all (SPEC.md §16's
    summer_term/exclude_exact_terms describe that vocabulary) -- a posting
    with no term info, e.g. Palantir/Citadel's non-internship boards, has no
    way to tell summer from off-season and defaults to the summer channel.

    Exclusion only fires when the posting's *entire* term set is exactly one
    excluded term (e.g. a lone "Fall 2026") -- a posting tagged both "Fall
    2026" and something else (a rolling multi-term listing) is not excluded.
    """
    terms = {t.strip().lower() for t in posting.terms if t.strip()}
    exclude_terms = {t.strip().lower() for t in config.exclude_exact_terms}

    if len(terms) == 1 and next(iter(terms)) in exclude_terms:
        return None

    if not terms or config.summer_term.strip().lower() in terms:
        return "summer"

    return "off_season"


def send_channeled_notifications(
    postings: list[Posting],
    config: NotificationConfig,
    post_fn: Callable = requests.post,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> tuple[int, int]:
    """Splits `postings` by classify_channel() and sends each group to its
    own webhook via send_notifications(), independently capped and
    throttled. Returns (summer_sent, off_season_sent)."""
    summer: list[Posting] = []
    off_season: list[Posting] = []
    for posting in postings:
        channel = classify_channel(posting, config)
        if channel == "summer":
            summer.append(posting)
        elif channel == "off_season":
            off_season.append(posting)
        # else: excluded -- dropped, not sent to either channel

    summer_sent = send_notifications(
        summer, config.summer_webhook_url, config.per_channel_cap, post_fn, sleep_fn
    )
    off_season_sent = send_notifications(
        off_season, config.off_season_webhook_url, config.per_channel_cap, post_fn, sleep_fn
    )
    return summer_sent, off_season_sent
