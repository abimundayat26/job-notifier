"""Live smoke test (SPEC.md §13): hits the real aggregator repos on a
schedule, separate from normal CI, to catch silent source breakage that the
main pipeline's log-and-continue failure handling would otherwise miss
silently. Run explicitly with `pytest -m live`; excluded from the default
`pytest -m "not live"` run used in normal CI.
"""

import os

import pytest

from jobnotifier.config import load_config
from jobnotifier.sources.tier1_aggregator import Tier1AggregatorSource
from jobnotifier.sources.tier2_ats import PLATFORM_ADAPTERS
from jobnotifier.sources.tier3_scrapers import COMPANY_ADAPTERS

pytestmark = pytest.mark.live

REQUIRED_FIELDS = ("company", "title", "url")


def _load_test_config():
    os.environ.setdefault("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/placeholder/placeholder")
    return load_config("config/config.yaml")


def test_each_tier1_aggregator_returns_postings_with_required_fields():
    config = _load_test_config()
    assert config.sources.tier1_aggregators, "no tier1 aggregators configured"

    for row in config.sources.tier1_aggregators:
        source = Tier1AggregatorSource(repo=row.repo, ref=row.ref, path=row.path)
        raw = source.fetch()
        assert isinstance(raw, list) and len(raw) > 0, f"{source.source_id} returned no postings"

        postings = source.parse(raw)
        assert len(postings) > 0, f"{source.source_id} produced no parsed postings"

        active_postings = [p for p in postings if p.active is not False]
        assert active_postings, f"{source.source_id} has zero active postings"

        sample = active_postings[0]
        for field_name in REQUIRED_FIELDS:
            assert getattr(sample, field_name), f"{source.source_id} posting missing '{field_name}'"


def test_each_tier2_ats_row_returns_postings_with_required_fields():
    # tier2_ats starts empty until real, hand-verified company rows are added
    # (SPEC.md §13: an unverified slug would 404 and look identical to real
    # source breakage), so this loop is a no-op until then rather than a
    # hard assertion like the tier1 test above.
    config = _load_test_config()

    for row in config.sources.tier2_ats:
        adapter_cls = PLATFORM_ADAPTERS[row.platform]
        source = adapter_cls(company=row.company, slug=row.slug)
        raw = source.fetch()
        postings = source.parse(raw)
        assert len(postings) > 0, f"{source.source_id} produced no parsed postings"

        sample = postings[0]
        for field_name in REQUIRED_FIELDS:
            assert getattr(sample, field_name), f"{source.source_id} posting missing '{field_name}'"


def test_each_tier3_scraper_returns_postings_with_required_fields():
    config = _load_test_config()
    assert config.sources.tier3_scrapers, "no tier3 scrapers configured"

    for row in config.sources.tier3_scrapers:
        adapter_cls = COMPANY_ADAPTERS[row.company]
        source = adapter_cls(company=row.company)
        raw = source.fetch()
        postings = source.parse(raw)
        assert len(postings) > 0, f"{source.source_id} produced no parsed postings"

        sample = postings[0]
        for field_name in REQUIRED_FIELDS:
            assert getattr(sample, field_name), f"{source.source_id} posting missing '{field_name}'"
