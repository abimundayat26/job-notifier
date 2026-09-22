import json
from pathlib import Path

from jobnotifier.sources.tier2_ats.greenhouse import GreenhouseSource

FIXTURES = Path(__file__).parent.parent / "fixtures" / "tier2"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _make_source() -> GreenhouseSource:
    return GreenhouseSource(company="Example Co", slug="examplecoslug")


def test_fetch_url_and_source_id():
    source = _make_source()
    assert source._url == "https://boards-api.greenhouse.io/v1/boards/examplecoslug/jobs?content=false"
    assert source.source_id == "tier2:greenhouse:examplecoslug"


def test_parses_normal_entry():
    raw = _load_fixture("greenhouse_sample.json")
    postings = _make_source().parse(raw)
    normal = next(p for p in postings if p.extra["ats_id"] == 4123456789)
    assert normal.company == "Example Co"
    assert normal.title == "Software Engineer, Backend"
    assert normal.location == "New York, NY"
    assert normal.url == "https://job-boards.greenhouse.io/examplecoslug/jobs/4123456789"
    assert normal.source_id == "tier2:greenhouse:examplecoslug"
    assert normal.extra["departments"] == ["Engineering"]
    assert normal.extra["offices"] == ["New York"]


def test_missing_location_becomes_empty_string_not_error():
    raw = _load_fixture("greenhouse_sample.json")
    postings = _make_source().parse(raw)
    remote = next(p for p in postings if p.extra["ats_id"] == 4123456790)
    assert remote.location == ""


def test_date_posted_is_always_none():
    # Greenhouse's jobs API exposes no field except updated_at, which is
    # never used as a posting date.
    raw = _load_fixture("greenhouse_sample.json")
    postings = _make_source().parse(raw)
    assert all(p.date_posted is None for p in postings)


def test_active_is_always_none():
    raw = _load_fixture("greenhouse_sample.json")
    postings = _make_source().parse(raw)
    assert all(p.active is None for p in postings)
