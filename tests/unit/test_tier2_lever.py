import json
from datetime import date
from pathlib import Path

from jobnotifier.sources.tier2_ats.lever import LeverSource

FIXTURES = Path(__file__).parent.parent / "fixtures" / "tier2"


def _load_fixture(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _make_source() -> LeverSource:
    return LeverSource(company="Example Co", slug="examplecoslug")


def test_fetch_url_and_source_id():
    source = _make_source()
    assert source._url == "https://api.lever.co/v0/postings/examplecoslug?mode=json"
    assert source.source_id == "tier2:lever:examplecoslug"


def test_bare_array_response_parses_without_jobs_key():
    raw = _load_fixture("lever_sample.json")
    assert isinstance(raw, list)  # fixture itself is a bare array, not {"jobs": [...]}
    postings = _make_source().parse(raw)
    assert len(postings) == 2


def test_parses_normal_entry():
    raw = _load_fixture("lever_sample.json")
    postings = _make_source().parse(raw)
    normal = next(p for p in postings if p.extra["ats_id"] == "abc123-def456")
    assert normal.company == "Example Co"
    assert normal.title == "Software Engineer"
    assert normal.location == "New York"
    assert normal.url == "https://jobs.lever.co/examplecoslug/abc123-def456"
    assert normal.source_id == "tier2:lever:examplecoslug"
    assert normal.extra["team"] == "Engineering"


def test_created_at_epoch_milliseconds_converted_correctly():
    # createdAt in the fixture is 1755648000000 ms, i.e. 1755648000 s, which
    # is 2025-08-20T00:00:00Z. A missed /1000 would land ~50 years off.
    raw = _load_fixture("lever_sample.json")
    postings = _make_source().parse(raw)
    normal = next(p for p in postings if p.extra["ats_id"] == "abc123-def456")
    assert normal.date_posted == date(2025, 8, 20)


def test_missing_location_key_becomes_empty_string_not_error():
    raw = _load_fixture("lever_sample.json")
    postings = _make_source().parse(raw)
    sre = next(p for p in postings if p.extra["ats_id"] == "ghi789-jkl012")
    assert sre.location == ""


def test_active_is_always_none():
    raw = _load_fixture("lever_sample.json")
    postings = _make_source().parse(raw)
    assert all(p.active is None for p in postings)
