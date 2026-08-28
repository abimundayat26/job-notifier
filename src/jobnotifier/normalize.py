import re

# Aliases seen in real Tier 1 aggregator data where the same place is spelled
# multiple ways within a single source (e.g. Simplify's listings.json mixes
# "NYC" and "New York, NY" for the same city). Keys and values are matched
# after lowercase/whitespace normalization. Extend as new mismatches surface.
_LOCATION_ALIASES: dict[str, str] = {
    "nyc": "new york, ny",
    "new york city": "new york, ny",
    "sf": "san francisco, ca",
    "san fran": "san francisco, ca",
    "bay area": "san francisco, ca",
    "dc": "washington, dc",
    "washington d.c.": "washington, dc",
    "washington d.c": "washington, dc",
    "la": "los angeles, ca",
}

_WHITESPACE_RE = re.compile(r"\s+")


def _collapse_whitespace(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value.strip())


def normalize_company(company: str) -> str:
    return _collapse_whitespace(company).lower()


def normalize_title(title: str) -> str:
    return _collapse_whitespace(title).lower()


def normalize_location(location: str) -> str:
    value = _collapse_whitespace(location).lower()
    value = value.rstrip(".")
    return _LOCATION_ALIASES.get(value, value)


def location_matches_filter(location: str, filter_locations: list[str]) -> bool:
    """True if `location` normalizes to the same place as any configured filter entry."""
    normalized = normalize_location(location)
    return any(normalized == normalize_location(entry) for entry in filter_locations)
