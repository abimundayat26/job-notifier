from pathlib import Path

import pytest
import requests

from jobnotifier.sources.tier3_scrapers import _http
from jobnotifier.sources.tier3_scrapers.citadel import CitadelSource, _BASE_URL, _PAGE_URL_TEMPLATE

FIXTURES = Path(__file__).parent.parent / "fixtures" / "tier3"


def _load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _make_source() -> CitadelSource:
    return CitadelSource(company="Citadel")


def test_source_id_and_urls():
    source = _make_source()
    assert source.source_id == "tier3:citadel"
    assert _BASE_URL == "https://www.citadel.com/careers/open-opportunities/"
    assert _PAGE_URL_TEMPLATE.format(page=2) == "https://www.citadel.com/careers/open-opportunities/page/2/"


def test_parses_normal_entry():
    raw = [_load_fixture("citadel_page1_sample.html")]
    postings = _make_source().parse(raw)
    normal = next(p for p in postings if p.title == "Software Engineer – Intern (Europe)")
    assert normal.company == "Citadel"
    assert normal.url == "https://www.citadel.com/careers/details/software-engineer-intern-europe/"
    assert normal.location == "London"
    assert normal.date_posted is None
    assert normal.active is None
    assert normal.source_id == "tier3:citadel"


def test_multi_location_entry_explodes_into_one_posting_per_location():
    raw = [_load_fixture("citadel_page1_sample.html")]
    postings = _make_source().parse(raw)
    grad_postings = [p for p in postings if p.title == "Software Engineer – University Graduate (US)"]
    assert {p.location for p in grad_postings} == {"Greenwich", "Houston", "Miami", "New York"}
    assert all(p.url == grad_postings[0].url for p in grad_postings)


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


def test_fetch_stops_at_first_empty_page(monkeypatch):
    pages = [_load_fixture("citadel_page1_sample.html"), _load_fixture("citadel_empty_page.html")]
    calls = []

    def fake_polite_get(url, timeout=30):
        calls.append(url)
        return _FakeResponse(pages[len(calls) - 1])

    monkeypatch.setattr(_http, "polite_get", fake_polite_get)

    result = _make_source().fetch()

    assert len(result) == 1
    assert calls == [_BASE_URL, _PAGE_URL_TEMPLATE.format(page=2)]


def test_fetch_stops_on_404(monkeypatch):
    class _FakeHTTPResponse:
        status_code = 404

    def fake_polite_get(url, timeout=30):
        if url == _BASE_URL:
            return _FakeResponse(_load_fixture("citadel_page1_sample.html"))
        error = requests.HTTPError("not found")
        error.response = _FakeHTTPResponse()
        raise error

    monkeypatch.setattr(_http, "polite_get", fake_polite_get)

    result = _make_source().fetch()

    assert len(result) == 1


def test_fetch_propagates_non_404_http_error(monkeypatch):
    class _FakeHTTPResponse:
        status_code = 500

    def fake_polite_get(url, timeout=30):
        if url == _BASE_URL:
            return _FakeResponse(_load_fixture("citadel_page1_sample.html"))
        error = requests.HTTPError("server error")
        error.response = _FakeHTTPResponse()
        raise error

    monkeypatch.setattr(_http, "polite_get", fake_polite_get)

    with pytest.raises(requests.HTTPError):
        _make_source().fetch()
