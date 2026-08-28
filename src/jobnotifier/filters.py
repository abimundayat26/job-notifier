from datetime import date

from jobnotifier import normalize
from jobnotifier.config import FiltersConfig
from jobnotifier.models import Posting

FRESHNESS_WINDOW_DAYS = 7


def _title_contains_any(title: str, keywords: list[str]) -> bool:
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in keywords)


def _is_remote(location: str) -> bool:
    return "remote" in location.lower()


def passes_filters(posting: Posting, filters: FiltersConfig) -> bool:
    """Applies SPEC.md §8's keyword/location/remote/seniority rules.

    Salary is intentionally never consulted here — display-only per spec.
    """
    if filters.title_include and not _title_contains_any(posting.title, filters.title_include):
        return False
    if _title_contains_any(posting.title, filters.title_exclude):
        return False
    if _title_contains_any(posting.title, filters.seniority_exclude):
        return False
    if filters.remote_only and not _is_remote(posting.location):
        return False
    if filters.locations and not normalize.location_matches_filter(posting.location, filters.locations):
        return False
    return True


def passes_freshness(posting: Posting, today: date, window_days: int = FRESHNESS_WINDOW_DAYS) -> bool:
    """A posting with no date is never freshness-filtered out (SPEC.md §6) —
    absence of a date is handled upstream by state.py's seed/reopen logic."""
    if posting.date_posted is None:
        return True
    return (today - posting.date_posted).days <= window_days
