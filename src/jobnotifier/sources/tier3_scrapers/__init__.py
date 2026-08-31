# Tier 3 - hand-written scrapers, capped at 5 (SPEC.md §4). Each company gets
# its own bespoke adapter class; COMPANY_ADAPTERS just maps a config row's
# `company` slug to the class that knows how to scrape that specific site.

from jobnotifier.sources.base import Source
from jobnotifier.sources.tier3_scrapers.citadel import CitadelSource

COMPANY_ADAPTERS: dict[str, type[Source]] = {
    "citadel": CitadelSource,
}
