"""Politeness helpers shared by Tier 3 scrapers only: an
identifying User-Agent, per-domain rate limiting, and robots.txt compliance.
Not a general scraping framework -- just enough shared plumbing that each of
the (at most 5) bespoke parsers doesn't reimplement the same three checks.
"""

import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

USER_AGENT = (
    "JobNotifierBot/1.0 (+https://github.com/abimundayat26/job-notifier; "
    "personal, low-volume job-alert scraper)"
)

# citadel.com's robots.txt declares "Crawl-delay: 10" *before* any
# "User-agent:" line, which urllib.robotparser silently drops (the directive
# has no entry to attach to) -- rp.crawl_delay() then returns None. Confirmed
# live that a shorter delay gets a 403 from the site's own rate limiting, so
# the fallback default here is deliberately as conservative as that orphaned
# directive, not a generic guess.
_DEFAULT_DELAY_SECONDS = 10.0

_robot_parsers: dict[str, RobotFileParser] = {}
_last_request_at: dict[str, float] = {}


class RobotsDisallowedError(RuntimeError):
    """Raised when robots.txt disallows fetching a URL for USER_AGENT."""


def _domain(url: str) -> str:
    return urlparse(url).netloc


def _get_robot_parser(url: str) -> RobotFileParser:
    # Deliberately not RobotFileParser.read(): it fetches via bare urllib with
    # no way to set a custom User-Agent, and some sites (e.g. citadel.com)
    # 403 the default urllib UA -- which read() then (correctly, per its own
    # rules) interprets as "disallow everything", even though the same
    # robots.txt is actually permissive for a real UA. Fetch it ourselves
    # with our own identifying header and feed the text to parse() instead.
    domain = _domain(url)
    rp = _robot_parsers.get(domain)
    if rp is None:
        robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        resp = requests.get(robots_url, headers={"User-Agent": USER_AGENT}, timeout=15)
        if resp.status_code in (401, 403):
            rp.disallow_all = True
        elif 400 <= resp.status_code < 500:
            rp.allow_all = True  # no robots.txt -- treat as unrestricted, matching RobotFileParser.read()
        else:
            resp.raise_for_status()  # a 5xx is a real failure, not a robots.txt policy signal
            rp.parse(resp.text.splitlines())
        rp.modified()
        _robot_parsers[domain] = rp
    return rp


def check_robots_allowed(url: str) -> None:
    rp = _get_robot_parser(url)
    if not rp.can_fetch(USER_AGENT, url):
        raise RobotsDisallowedError(f"robots.txt disallows fetching {url} for {USER_AGENT}")


def _rate_limit(url: str) -> None:
    domain = _domain(url)
    rp = _robot_parsers.get(domain)
    delay = (rp.crawl_delay(USER_AGENT) if rp else None) or _DEFAULT_DELAY_SECONDS

    last = _last_request_at.get(domain)
    if last is not None:
        elapsed = time.monotonic() - last
        remaining = delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

    _last_request_at[domain] = time.monotonic()


def polite_get(url: str, timeout: int = 30) -> requests.Response:
    """robots.txt check + per-domain rate limit + identifying UA, then GET."""
    check_robots_allowed(url)
    _rate_limit(url)
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return resp
