from jobnotifier.config import Config
from jobnotifier.sources.base import Source, UnsupportedPlatformError, UnsupportedScraperError
from jobnotifier.sources.tier1_aggregator import Tier1AggregatorSource
from jobnotifier.sources.tier2_ats import PLATFORM_ADAPTERS
from jobnotifier.sources.tier3_scrapers import COMPANY_ADAPTERS


def build_sources(config: Config) -> list[Source]:
    sources: list[Source] = []
    for row in config.sources.tier1_aggregators:
        sources.append(Tier1AggregatorSource(repo=row.repo, ref=row.ref, path=row.path))
    for row in config.sources.tier2_ats:
        adapter_cls = PLATFORM_ADAPTERS.get(row.platform)
        if adapter_cls is None:
            raise UnsupportedPlatformError(
                f"unsupported tier2_ats platform '{row.platform}' "
                f"(supported: {', '.join(sorted(PLATFORM_ADAPTERS))})"
            )
        sources.append(adapter_cls(company=row.company, slug=row.slug))
    for row in config.sources.tier3_scrapers:
        adapter_cls = COMPANY_ADAPTERS.get(row.company)
        if adapter_cls is None:
            raise UnsupportedScraperError(
                f"unsupported tier3_scrapers company '{row.company}' "
                f"(supported: {', '.join(sorted(COMPANY_ADAPTERS))})"
            )
        sources.append(adapter_cls(company=row.company))
    return sources
