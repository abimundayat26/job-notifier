import time
from typing import Callable

import requests

from jobnotifier.models import Posting, canonical_key

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
    Returns the number of notifications actually sent."""
    to_send = postings[:per_run_cap]

    for i, posting in enumerate(to_send):
        resp = post_fn(webhook_url, json=build_message(posting), timeout=15)
        resp.raise_for_status()
        if i < len(to_send) - 1:
            sleep_fn(THROTTLE_SECONDS)
    return len(to_send)
