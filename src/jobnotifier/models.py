from dataclasses import dataclass, field
from datetime import date

from jobnotifier import normalize


@dataclass(frozen=True)
class Posting:
    """Common posting shape every source adapter normalizes into."""

    company: str
    title: str
    location: str
    url: str
    date_posted: date | None = None
    active: bool | None = None
    salary: str | None = None
    term: str | None = None  # e.g. "Summer 2027" -- display-only, not part of canonical_key
    source_id: str = ""
    extra: dict = field(default_factory=dict)


def canonical_key(posting: Posting) -> str:
    """Deterministic (company, title, location) dedup key.

    Exact match on normalized strings only — no fuzzy matching. Anything
    that doesn't normalize identically stays a distinct key, so ambiguous
    matches never silently collapse (SPEC.md §9).
    """
    company = normalize.normalize_company(posting.company)
    title = normalize.normalize_title(posting.title)
    location = normalize.normalize_location(posting.location)
    return f"{company}|{title}|{location}"
