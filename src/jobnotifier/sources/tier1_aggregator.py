from datetime import datetime, timezone
from typing import Any

import requests

from jobnotifier.models import Posting
from jobnotifier.sources.base import Source

_RAW_URL_TEMPLATE = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"


class Tier1AggregatorSource(Source):
    """Reads a public aggregator repo's listings.json via the raw content CDN.

    Not the GitHub REST Contents API: both SimplifyJobs listings.json files
    are 11-13MB, well over the Contents API's inline-content size cap, and the
    raw CDN needs no auth and doesn't consume API rate-limit quota.
    """

    tier = 1

    def __init__(self, repo: str, ref: str, path: str):
        self.repo = repo
        self.ref = ref
        self.path = path
        self.source_id = f"tier1:{repo}"
        self._url = _RAW_URL_TEMPLATE.format(repo=repo, ref=ref, path=path)

    def fetch(self) -> list[dict[str, Any]]:
        resp = requests.get(self._url, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def parse(self, raw: list[dict[str, Any]]) -> list[Posting]:
        postings: list[Posting] = []
        for item in raw:
            date_posted = None
            if item.get("date_posted"):
                # date_updated is never read as a posting date (SPEC.md §6):
                # a content edit bumps it and would incorrectly resurface a
                # stale posting as newly relevant.
                date_posted = datetime.fromtimestamp(
                    item["date_posted"], tz=timezone.utc
                ).date()

            locations = item.get("locations") or [""]
            for location in locations:
                postings.append(
                    Posting(
                        company=item.get("company_name", ""),
                        title=item.get("title", ""),
                        location=location,
                        url=item.get("url", ""),
                        date_posted=date_posted,
                        active=item.get("active"),
                        salary=None,
                        source_id=self.source_id,
                        extra={
                            "category": item.get("category"),
                            "degrees": item.get("degrees"),
                            "sponsorship": item.get("sponsorship"),
                            # Aggregator-internal id, kept for debugging only:
                            # never used as/in our canonical dedup key.
                            "aggregator_id": item.get("id"),
                        },
                    )
                )
        return postings
