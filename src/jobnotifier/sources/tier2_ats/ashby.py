from datetime import datetime
from typing import Any

import requests

from jobnotifier.models import Posting
from jobnotifier.sources.base import Source

_URL_TEMPLATE = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"


class AshbySource(Source):
    """Reads a company's public Ashby job board API.

    publishedAt is a clean ISO-8601 datetime - the one Tier 2 platform with a
    genuinely reliable posted date (Greenhouse/Lever have no reliable date or
    only a coarse creation timestamp).

    isListed maps to `active`, but this is a best-guess mapping never
    confirmed against a real payload containing an unlisted job. Low risk
    either way: absence-based closure in state.py is the fallback path
    regardless of what `active` says.

    includeCompensation=true is what makes `compensation.compensationTierSummary`
    (a human-readable string, e.g. "$120K – $150K • Offers Equity") available
    on each job -- confirmed against a live Ashby board. Not every posting has
    compensation data set, so the field/object can be absent.
    """

    tier = 2

    def __init__(self, company: str, slug: str):
        self.company = company
        self.slug = slug
        self.source_id = f"tier2:ashby:{slug}"
        self._url = _URL_TEMPLATE.format(slug=slug)

    def fetch(self) -> dict[str, Any]:
        resp = requests.get(self._url, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def parse(self, raw: dict[str, Any]) -> list[Posting]:
        postings: list[Posting] = []
        for item in raw.get("jobs", []):
            date_posted = None
            published_at = item.get("publishedAt")
            if published_at:
                date_posted = datetime.fromisoformat(
                    published_at.replace("Z", "+00:00")
                ).date()

            compensation = item.get("compensation") or {}

            postings.append(
                Posting(
                    company=self.company,
                    title=item.get("title", ""),
                    location=item.get("location", ""),
                    url=item.get("jobUrl", ""),
                    date_posted=date_posted,
                    active=item.get("isListed"),  # see class docstring: best-guess, unconfirmed
                    salary=compensation.get("compensationTierSummary"),
                    source_id=self.source_id,
                    extra={
                        "department": item.get("department"),
                        "is_remote": item.get("isRemote"),
                        "ats_id": item.get("id"),
                    },
                )
            )
        return postings
