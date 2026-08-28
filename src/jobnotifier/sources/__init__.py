from jobnotifier.config import Config
from jobnotifier.sources.base import Source
from jobnotifier.sources.tier1_aggregator import Tier1AggregatorSource


def build_sources(config: Config) -> list[Source]:
    sources: list[Source] = []
    for row in config.sources.tier1_aggregators:
        sources.append(Tier1AggregatorSource(repo=row.repo, ref=row.ref, path=row.path))
    return sources
