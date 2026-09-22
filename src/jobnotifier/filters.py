import re
from datetime import date

from jobnotifier import normalize
from jobnotifier.config import FiltersConfig
from jobnotifier.models import Posting

FRESHNESS_WINDOW_DAYS = 7


def _keyword_matches(title_lower: str, keyword: str) -> bool:
    # Multi-word phrases keep plain substring matching on purpose: it's what
    # lets "software engineer" also catch "Software Engineering Intern" for
    # free. Single-word keywords (especially short abbreviations like "swe"/
    # "sde") get word-boundary matching instead -- plain substring matching
    # on those false-positives inside unrelated words, e.g. "swe" inside
    # "Swedish" (there is no fuzzy matching elsewhere either; this keeps that
    # spirit while fixing the one class of false positive substrings cause).
    kw_lower = keyword.lower()
    if " " in kw_lower:
        return kw_lower in title_lower
    return re.search(rf"\b{re.escape(kw_lower)}\b", title_lower) is not None


def _title_contains_any(title: str, keywords: list[str]) -> bool:
    title_lower = title.lower()
    return any(_keyword_matches(title_lower, kw) for kw in keywords)


def _is_remote(location: str) -> bool:
    return "remote" in location.lower()


def passes_filters(posting: Posting, filters: FiltersConfig) -> bool:
    """Applies the keyword/location/remote/seniority filter rules.

    Salary is intentionally never consulted here — display-only.
    """
    if filters.title_include and not _title_contains_any(posting.title, filters.title_include):
        return False
    if _title_contains_any(posting.title, filters.title_exclude):
        return False
    if _title_contains_any(posting.title, filters.seniority_exclude):
        return False
    if filters.remote_only and not _is_remote(posting.location):
        return False
    if filters.us_only and not normalize.is_us_location(posting.location):
        return False
    if filters.locations and not normalize.location_matches_filter(posting.location, filters.locations):
        return False
    return True


def passes_freshness(posting: Posting, today: date, window_days: int = FRESHNESS_WINDOW_DAYS) -> bool:
    """A posting with no date is never freshness-filtered out —
    absence of a date is handled upstream by state.py's seed/reopen logic."""
    if posting.date_posted is None:
        return True
    return (today - posting.date_posted).days <= window_days
