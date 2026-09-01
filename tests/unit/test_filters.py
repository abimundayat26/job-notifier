from datetime import date

from jobnotifier.config import FiltersConfig
from jobnotifier.filters import passes_filters, passes_freshness
from jobnotifier.models import Posting


def _posting(**overrides):
    defaults = dict(
        company="Acme",
        title="Software Engineer Intern",
        location="New York, NY",
        url="https://example.com/job/1",
        date_posted=date(2026, 8, 25),
    )
    defaults.update(overrides)
    return Posting(**defaults)


def _filters(**overrides):
    defaults = dict(
        title_include=[],
        title_exclude=[],
        locations=[],
        remote_only=False,
        seniority_exclude=[],
    )
    defaults.update(overrides)
    return FiltersConfig(**defaults)


def test_title_include_requires_match():
    f = _filters(title_include=["backend"])
    assert not passes_filters(_posting(title="Frontend Engineer"), f)
    assert passes_filters(_posting(title="Backend Engineer"), f)


def test_title_include_phrase_keyword_uses_substring_matching():
    f = _filters(title_include=["software engineer"])
    assert passes_filters(_posting(title="Software Engineering Intern"), f)


def test_title_include_single_word_keyword_uses_word_boundary_matching():
    f = _filters(title_include=["swe"])
    assert passes_filters(_posting(title="SWE Intern"), f)
    assert not passes_filters(_posting(title="Speech & Voice AI Analyst - Swedish Speakers"), f)


def test_title_exclude_rejects_match():
    f = _filters(title_exclude=["senior"])
    assert not passes_filters(_posting(title="Senior Software Engineer"), f)


def test_seniority_exclude_rejects_match():
    f = _filters(seniority_exclude=["staff"])
    assert not passes_filters(_posting(title="Staff Engineer"), f)


def test_location_filter_uses_alias_matching():
    f = _filters(locations=["New York, NY"])
    assert passes_filters(_posting(location="NYC"), f)
    assert not passes_filters(_posting(location="Austin, TX"), f)


def test_remote_only_requires_remote_location():
    f = _filters(remote_only=True)
    assert passes_filters(_posting(location="Remote"), f)
    assert not passes_filters(_posting(location="New York, NY"), f)


def test_us_only_rejects_non_us_location():
    f = _filters(us_only=True)
    assert passes_filters(_posting(location="New York, NY"), f)
    assert not passes_filters(_posting(location="London, UK"), f)


def test_us_only_defaults_to_false():
    f = _filters()
    assert passes_filters(_posting(location="London, UK"), f)


def test_salary_never_used_as_filter_input():
    f = _filters(title_include=["engineer"])
    assert passes_filters(_posting(salary="$999999"), f)
    assert passes_filters(_posting(salary=None), f)


def test_freshness_within_window():
    assert passes_freshness(_posting(date_posted=date(2026, 8, 21)), today=date(2026, 8, 27))


def test_freshness_outside_window():
    assert not passes_freshness(_posting(date_posted=date(2026, 8, 1)), today=date(2026, 8, 27))


def test_freshness_missing_date_always_passes():
    assert passes_freshness(_posting(date_posted=None), today=date(2026, 8, 27))
