import json
from datetime import datetime, timezone
from pathlib import Path

from jobnotifier.sources.tier1_aggregator import Tier1AggregatorSource

FIXTURES = Path(__file__).parent.parent / "fixtures" / "tier1"


def _load_fixture(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _make_source() -> Tier1AggregatorSource:
    return Tier1AggregatorSource(
        repo="SimplifyJobs/Summer2026-Internships",
        ref="dev",
        path=".github/scripts/listings.json",
    )


def test_fetch_url_uses_raw_cdn_not_contents_api():
    source = _make_source()
    assert source._url == (
        "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships"
        "/dev/.github/scripts/listings.json"
    )
    assert source.source_id == "tier1:SimplifyJobs/Summer2026-Internships"


def test_multi_location_entry_merges_into_one_posting():
    raw = _load_fixture("summer2026_sample.json")
    postings = _make_source().parse(raw)
    citadel_postings = [p for p in postings if p.company == "Citadel"]
    assert len(citadel_postings) == 1
    assert citadel_postings[0].location == "Greenwich, CT; Houston, TX; Miami, FL; NYC"
    assert citadel_postings[0].title == "Quantitative Researcher"


def test_active_flag_passed_through_unchanged():
    raw = _load_fixture("summer2026_sample.json")
    postings = _make_source().parse(raw)
    tiktok = next(p for p in postings if p.company == "TikTok")
    aerospace = [p for p in postings if p.company == "The Aerospace Corporation"]
    assert tiktok.active is True
    assert all(p.active is False for p in aerospace)


def test_date_posted_uses_date_posted_field_not_date_updated():
    raw = _load_fixture("summer2026_sample.json")
    postings = _make_source().parse(raw)
    tiktok = next(p for p in postings if p.company == "TikTok")
    # date_posted for the TikTok fixture entry is epoch 1768443444
    assert tiktok.date_posted == datetime.fromtimestamp(1768443444, tz=timezone.utc).date()


def test_zero_date_posted_treated_as_missing():
    raw = _load_fixture("summer2026_sample.json")
    postings = _make_source().parse(raw)
    edge_case = next(p for p in postings if p.company == "Edge Case Co")
    assert edge_case.date_posted is None


def test_aggregator_id_kept_only_in_extra_not_used_elsewhere():
    raw = _load_fixture("summer2026_sample.json")
    postings = _make_source().parse(raw)
    tiktok = next(p for p in postings if p.company == "TikTok")
    assert tiktok.extra["aggregator_id"] == "e7d90cdc-955f-4bb2-8a94-81ea48265d84"


def test_terms_field_becomes_posting_term():
    raw = _load_fixture("summer2026_sample.json")
    postings = _make_source().parse(raw)
    tiktok = next(p for p in postings if p.company == "TikTok")
    assert tiktok.term == "Summer 2026"


def test_community_submitted_source_field_does_not_break_parsing():
    raw = _load_fixture("summer2026_sample.json")
    postings = _make_source().parse(raw)
    amazon_postings = [p for p in postings if p.company == "Amazon"]
    assert len(amazon_postings) == 1  # merged across two locations
    assert amazon_postings[0].location == "Dallas, TX; Herdon, VA"
    assert all(p.source_id == "tier1:SimplifyJobs/Summer2026-Internships" for p in amazon_postings)


def test_newgrad_fixture_parses_without_terms_field():
    raw = _load_fixture("newgrad_sample.json")
    postings = _make_source().parse(raw)
    assert len(postings) == 2  # 1 merged Citadel + 1 Mechanize
    mechanize = next(p for p in postings if p.company == "Mechanize")
    assert mechanize.location == "SF"
    assert mechanize.active is False
    assert mechanize.term is None
