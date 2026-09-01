import requests
from bs4 import BeautifulSoup

from jobnotifier import normalize
from jobnotifier.models import Posting
from jobnotifier.sources.base import Source
from jobnotifier.sources.tier3_scrapers import _http

_BASE_URL = "https://www.citadel.com/careers/open-opportunities/"
_PAGE_URL_TEMPLATE = "https://www.citadel.com/careers/open-opportunities/page/{page}/"

# Circuit breaker: stop paginating even if the site's markup changes in a way
# that defeats both of our normal stop conditions (a 404 or an empty page).
_MAX_PAGES = 20


class CitadelSource(Source):
    """Scrapes Citadel's public "Open Opportunities" careers page.

    No ATS API exists for Citadel (SPEC.md §4) -- this page is a fully
    server-rendered WordPress site with real /page/N/ pagination and no
    posted-date field anywhere, confirmed by fetching it live. Page-one-only
    would silently miss postings (SPEC.md §11: not sorted by date), so
    fetch() paginates until it finds an empty or 404 page.
    """

    tier = 3

    def __init__(self, company: str):
        self.company = company
        self.source_id = "tier3:citadel"

    def fetch(self) -> list[str]:
        pages: list[str] = []
        for page_num in range(1, _MAX_PAGES + 1):
            url = _BASE_URL if page_num == 1 else _PAGE_URL_TEMPLATE.format(page=page_num)
            try:
                resp = _http.polite_get(url)
            except requests.HTTPError as exc:
                if page_num > 1 and exc.response is not None and exc.response.status_code == 404:
                    break  # normal end of pagination
                raise

            if not _has_job_cards(resp.text):
                break  # a 200 with zero listings also marks the end

            pages.append(resp.text)
        return pages

    def parse(self, raw: list[str]) -> list[Posting]:
        postings: list[Posting] = []
        for html in raw:
            soup = BeautifulSoup(html, "html.parser")
            for card in soup.select("a.careers-listing-card"):
                title = (card.get("data-position") or "").strip()
                if not title:
                    heading = card.select_one("h2")
                    title = heading.get_text(strip=True) if heading else ""

                url = card.get("href", "")

                location_el = card.select_one(".careers-listing-card__location")
                location_text = location_el.get_text(strip=True) if location_el else ""
                locations = [loc.strip() for loc in location_text.split(",") if loc.strip()] or [""]

                # One listing can be posted open across several offices at
                # once; merge them into a single Posting/notification instead
                # of one per location (they share this same url/card -- it's
                # one real job).
                postings.append(
                    Posting(
                        company=self.company,
                        title=title,
                        location=normalize.merge_locations(locations),
                        url=url,
                        date_posted=None,
                        active=None,  # no listed/unlisted signal; absence-based closure in state.py handles it
                        salary=None,
                        source_id=self.source_id,
                        extra={},
                    )
                )
        return postings


def _has_job_cards(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return soup.select_one("a.careers-listing-card") is not None
