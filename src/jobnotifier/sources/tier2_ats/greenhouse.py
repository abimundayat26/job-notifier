from typing import Any

import requests

from jobnotifier.models import Posting
from jobnotifier.sources.base import Source

_URL_TEMPLATE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=false"


class GreenhouseSource(Source):
    """Reads a company's public Greenhouse job board API.

    No published-date field distinct from `updated_at` is exposed by this
    endpoint, so `date_posted` is always None here (SPEC.md §6: `updated_at`
    is never used as a posting date, since a content edit bumping it would
    incorrectly resurface a stale posting as newly relevant). Freshness for
    Greenhouse postings relies entirely on state.py's new-key / closed->open
    transition detection, not date-based filtering (filters.passes_freshness
    already treats date_posted=None as always-passing).

    content=false is intentional, not an oversight: content=true would also
    return the full HTML job description, which Posting has no field for and
    would only bloat the response.
    """

    tier = 2

    def __init__(self, company: str, slug: str):
        self.company = company
        self.slug = slug
        self.source_id = f"tier2:greenhouse:{slug}"
        self._url = _URL_TEMPLATE.format(slug=slug)

    def fetch(self) -> dict[str, Any]:
        resp = requests.get(self._url, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def parse(self, raw: dict[str, Any]) -> list[Posting]:
        postings: list[Posting] = []
        for item in raw.get("jobs", []):
            location = (item.get("location") or {}).get("name") or ""
            postings.append(
                Posting(
                    company=self.company,
                    title=item.get("title", ""),
                    location=location,
                    url=item.get("absolute_url", ""),
                    date_posted=None,  # see class docstring
                    active=None,  # closed jobs just stop appearing; absence-based closure in state.py handles it
                    salary=None,
                    source_id=self.source_id,
                    extra={
                        "departments": [d.get("name") for d in item.get("departments", [])],
                        "offices": [o.get("name") for o in item.get("offices", [])],
                        "ats_id": item.get("id"),
                    },
                )
            )
        return postings
