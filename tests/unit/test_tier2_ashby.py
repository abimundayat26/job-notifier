import json
from datetime import date
from pathlib import Path

from jobnotifier.sources.tier2_ats.ashby import AshbySource

FIXTURES = Path(__file__).parent.parent / "fixtures" / "tier2"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _make_source() -> AshbySource:
    return AshbySource(company="Example Co", slug="examplecoslug")


def test_fetch_url_and_source_id():
    source = _make_source()
    assert source._url == (
        "https://api.ashbyhq.com/posting-api/job-board/examplecoslug?includeCompensation=true"
    )
    assert source.source_id == "tier2:ashby:examplecoslug"


def test_parses_normal_listed_entry():
    raw = _load_fixture("ashby_sample.json")
    postings = _make_source().parse(raw)
    listed = next(p for p in postings if p.extra["ats_id"] == "ashby-job-1")
    assert listed.company == "Example Co"
    assert listed.title == "Software Engineer, Platform"
    assert listed.location == "Remote - US"
    assert listed.url == "https://jobs.ashbyhq.com/examplecoslug/ashby-job-1"
    assert listed.source_id == "tier2:ashby:examplecoslug"
    assert listed.active is True
    assert listed.extra["department"] == "Engineering"
    assert listed.extra["is_remote"] is True


def test_published_at_iso_datetime_parsed_to_date():
    raw = _load_fixture("ashby_sample.json")
    postings = _make_source().parse(raw)
    listed = next(p for p in postings if p.extra["ats_id"] == "ashby-job-1")
    assert listed.date_posted == date(2026, 8, 1)


def test_unlisted_entry_maps_is_listed_false_to_active_false():
    raw = _load_fixture("ashby_sample.json")
    postings = _make_source().parse(raw)
    unlisted = next(p for p in postings if p.extra["ats_id"] == "ashby-job-2")
    assert unlisted.active is False


def test_compensation_tier_summary_becomes_salary():
    raw = _load_fixture("ashby_sample.json")
    postings = _make_source().parse(raw)
    listed = next(p for p in postings if p.extra["ats_id"] == "ashby-job-1")
    assert listed.salary == "$120K – $150K • Offers Equity"


def test_missing_compensation_becomes_salary_none():
    raw = _load_fixture("ashby_sample.json")
    postings = _make_source().parse(raw)
    unlisted = next(p for p in postings if p.extra["ats_id"] == "ashby-job-2")
    assert unlisted.salary is None
