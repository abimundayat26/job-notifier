# Tier 2 - ATS adapters, driven by a company->slug mapping in config
# Greenhouse, Lever, and Ashby are implemented; Workday and
# iCIMS are deferred (no clean, stable, public JSON API to adapt against).

from jobnotifier.sources.base import Source
from jobnotifier.sources.tier2_ats.ashby import AshbySource
from jobnotifier.sources.tier2_ats.greenhouse import GreenhouseSource
from jobnotifier.sources.tier2_ats.lever import LeverSource

PLATFORM_ADAPTERS: dict[str, type[Source]] = {
    "greenhouse": GreenhouseSource,
    "lever": LeverSource,
    "ashby": AshbySource,
}
