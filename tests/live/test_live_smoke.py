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
