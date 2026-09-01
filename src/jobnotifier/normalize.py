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
    "south sf": "south san francisco, ca",
    "bay area": "san francisco, ca",
    "dc": "washington, dc",
    "washington d.c.": "washington, dc",
    "washington d.c": "washington, dc",
    "la": "los angeles, ca",
}

_WHITESPACE_RE = re.compile(r"\s+")

_US_STATE_CODES: set[str] = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id",
    "il", "in", "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms",
    "mo", "mt", "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok",
    "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv",
    "wi", "wy", "dc",
}

_US_STATE_NAMES: set[str] = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming", "district of columbia",
    "washington dc",
}

_US_TOKENS: set[str] = {"united states", "usa", "us"}

# Matches "remote" with an optional explicit country qualifier, e.g. "remote
# in usa", "remote - canada", "remote (uk)". A bare "remote" (no qualifier)
# has no country signal at all -- treated as ambiguous, not excluded, rather
# than guessing (SPEC.md §9's dedup ambiguity philosophy applied to
# filtering: prefer letting an uncertain match through).
_REMOTE_RE = re.compile(r"\bremote\b")
_REMOTE_QUALIFIER_RE = re.compile(r"remote\s*(?:in|-|\()\s*([a-z .]+?)\)?$")


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


def _sub_location_indicates_us(part: str) -> bool:
    value = part.strip().lower().replace(".", "")
    if not value:
        return False
    value = _LOCATION_ALIASES.get(value, value)  # e.g. "nyc" -> "new york, ny"

    if _REMOTE_RE.search(value):
        qualifier_match = _REMOTE_QUALIFIER_RE.search(value)
        if qualifier_match:
            return qualifier_match.group(1).strip() in _US_TOKENS
        return True  # bare "remote", no country qualifier -- ambiguous, don't exclude

    if value in _US_TOKENS or value in _US_STATE_NAMES:
        return True

    if "," in value:
        suffix = value.rsplit(",", 1)[-1].strip()
        return suffix in _US_STATE_CODES or suffix in _US_STATE_NAMES or suffix in _US_TOKENS

    return value in _US_STATE_CODES


def is_us_location(location: str) -> bool:
    """True if `location` indicates a US location, per SPEC.md §8's
    country-level filter.

    A location merged across several offices (merge_locations) passes if
    *any* one of them is a US location -- a listing open in both New York
    and London is still relevant to a US-based search. Built from patterns
    observed in real Tier 1/2 data: "City, ST", bare state names/abbreviations,
    "United States", and "Remote in USA"/"Remote in <other country>".
    """
    parts = [p for p in location.split(";") if p.strip()] or [location]
    return any(_sub_location_indicates_us(part) for part in parts)


def merge_locations(locations: list[str]) -> str:
    """Combines one listing's multiple posted locations into a single display
    string (e.g. for a source that reports one job open across several
    offices), deduped and sorted for deterministic ordering -- so
    canonical_key() stays stable even if a source reorders its own list
    between fetches. Semicolon-separated since individual entries already
    contain commas (e.g. "New York, NY")."""
    cleaned = sorted({loc.strip() for loc in locations if loc and loc.strip()})
    return "; ".join(cleaned)
