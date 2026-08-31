import requests
import pytest

from jobnotifier.sources.tier3_scrapers import _http


@pytest.fixture(autouse=True)
def _clear_http_caches():
    # _robot_parsers/_last_request_at are module-level, domain-keyed caches --
    # clear them around every test so tests don't leak state into each other.
    _http._robot_parsers.clear()
    _http._last_request_at.clear()
    yield
    _http._robot_parsers.clear()
    _http._last_request_at.clear()


class _FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)


def test_robots_disallow_rule_raises(monkeypatch):
    robots_text = "User-agent: *\nDisallow: /careers/\n"
    monkeypatch.setattr(_http.requests, "get", lambda url, headers, timeout: _FakeResponse(200, robots_text))

    with pytest.raises(_http.RobotsDisallowedError):
        _http.check_robots_allowed("https://example.com/careers/open-opportunities/")


def test_robots_allow_rule_does_not_raise(monkeypatch):
    robots_text = "User-agent: *\nDisallow: /admin/\n"
    monkeypatch.setattr(_http.requests, "get", lambda url, headers, timeout: _FakeResponse(200, robots_text))

    _http.check_robots_allowed("https://example.com/careers/open-opportunities/")  # should not raise


def test_robots_fetch_403_treated_as_disallow_all(monkeypatch):
    # citadel.com's WAF 403s the default urllib UA robots.txt fetch even
    # though the file itself is permissive -- but if *our own* UA is the one
    # that gets a 403, that's a real "assume fully disallowed" signal.
    monkeypatch.setattr(_http.requests, "get", lambda url, headers, timeout: _FakeResponse(403))

    with pytest.raises(_http.RobotsDisallowedError):
        _http.check_robots_allowed("https://example.com/careers/")


def test_robots_fetch_404_treated_as_allow_all(monkeypatch):
    monkeypatch.setattr(_http.requests, "get", lambda url, headers, timeout: _FakeResponse(404))

    _http.check_robots_allowed("https://example.com/careers/")  # no robots.txt -- unrestricted


def test_robots_parser_cached_per_domain(monkeypatch):
    calls = []

    def fake_get(url, headers, timeout):
        calls.append(url)
        return _FakeResponse(200, "User-agent: *\nAllow: /\n")

    monkeypatch.setattr(_http.requests, "get", fake_get)

    _http.check_robots_allowed("https://example.com/a/")
    _http.check_robots_allowed("https://example.com/b/")

    assert calls == ["https://example.com/robots.txt"]  # fetched once, reused for the second URL


def test_polite_get_sends_identifying_user_agent(monkeypatch):
    captured = {}

    def dispatch(url, headers, timeout):
        if url.endswith("/robots.txt"):
            return _FakeResponse(200, "User-agent: *\nAllow: /\n")
        captured["headers"] = headers
        return _FakeResponse(200, "ok")

    monkeypatch.setattr(_http.requests, "get", dispatch)

    _http.polite_get("https://example.com/page/")

    assert captured["headers"]["User-Agent"] == _http.USER_AGENT


def test_rate_limit_sleeps_for_remaining_delay(monkeypatch):
    monkeypatch.setattr(_http.requests, "get", lambda url, headers, timeout: _FakeResponse(200, "User-agent: *\nAllow: /\n"))

    sleep_calls = []
    monkeypatch.setattr(_http.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    _http.check_robots_allowed("https://example.com/page/")  # populates the robots cache, no crawl-delay declared
    _http._last_request_at["example.com"] = _http.time.monotonic()

    _http._rate_limit("https://example.com/page/")

    assert len(sleep_calls) == 1
    assert 0 < sleep_calls[0] <= _http._DEFAULT_DELAY_SECONDS


def test_rate_limit_uses_declared_crawl_delay(monkeypatch):
    monkeypatch.setattr(
        _http.requests,
        "get",
        lambda url, headers, timeout: _FakeResponse(200, "User-agent: *\nCrawl-delay: 1\nAllow: /\n"),
    )

    sleep_calls = []
    monkeypatch.setattr(_http.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    _http.check_robots_allowed("https://example.com/page/")
    _http._last_request_at["example.com"] = _http.time.monotonic()

    _http._rate_limit("https://example.com/page/")

    assert len(sleep_calls) == 1
    assert sleep_calls[0] <= 1.0
