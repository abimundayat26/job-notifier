from datetime import datetime, timezone
from typing import Any

import requests

from jobnotifier.models import Posting
from jobnotifier.sources.base import Source

_URL_TEMPLATE = "https://api.lever.co/v0/postings/{slug}?mode=json"


class LeverSource(Source):
    """Reads a company's public Lever postings API.

    The response is a bare JSON array, not an object with a "jobs" key
    (unlike Greenhouse/Ashby) - parse() iterates the raw payload directly.

    createdAt is epoch *milliseconds*, unlike Tier 1's epoch-seconds
    date_posted field - divide by 1000 before converting, or dates land
    ~50 years in the future.
    """

    tier = 2

    def __init__(self, company: str, slug: str):
        self.company = company
        self.slug = slug
        self.source_id = f"tier2:lever:{slug}"
        self._url = _URL_TEMPLATE.format(slug=slug)

    def fetch(self) -> list[dict[str, Any]]:
        resp = requests.get(self._url, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def parse(self, raw: list[dict[str, Any]]) -> list[Posting]:
        postings: list[Posting] = []
        for item in raw:
            date_posted = None
            created_at_ms = item.get("createdAt")
            if created_at_ms:
                date_posted = datetime.fromtimestamp(
                    created_at_ms / 1000, tz=timezone.utc
                ).date()

            categories = item.get("categories") or {}
            postings.append(
                Posting(
                    company=self.company,
                    title=item.get("text", ""),
                    location=categories.get("location", ""),
                    url=item.get("hostedUrl", ""),
                    date_posted=date_posted,
                    active=None,  # closed jobs just stop appearing; absence-based closure in state.py handles it
                    salary=None,
                    source_id=self.source_id,
                    extra={
                        "team": categories.get("team"),
                        "commitment": categories.get("commitment"),
                        "ats_id": item.get("id"),
                    },
                )
            )
        return postings
