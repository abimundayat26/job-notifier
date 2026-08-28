from datetime import date

from jobnotifier.models import Posting, canonical_key
from jobnotifier.state import diff_and_update


def _posting(**overrides):
    defaults = dict(
        company="Citadel",
        title="Quantitative Researcher",
        location="NYC",
        url="https://example.com/job/1",
        date_posted=date(2026, 8, 20),
        active=True,
    )
    defaults.update(overrides)
    return Posting(**defaults)


TODAY = date(2026, 8, 27)
SOURCE = "tier1:SimplifyJobs/New-Grad-Positions"


def test_first_sighting_from_known_source_is_new_and_notifiable():
    # Source already exists in state (has reported some other key before),
    # so this specific posting appearing for the first time is genuinely new.
    state = {
        "other|key|here": {
            "first_seen": "2026-08-01",
            "last_seen": "2026-08-27",
            "status": "open",
            "source": SOURCE,
            "sources": [SOURCE],
            "url": "https://example.com/other",
        }
    }
    posting = _posting()
    new_state, to_notify = diff_and_update(
        state,
        {SOURCE: [posting]},
        {SOURCE: True},
        today=TODAY,
        retention_days=30,
        seed_window_days=30,
    )
    assert to_notify == [posting]
    key = canonical_key(posting)
    assert new_state[key]["status"] == "open"
    assert new_state[key]["sources"] == [SOURCE]


def test_seed_mode_adds_to_state_without_notifying():
    # Source has never appeared in state before => seed mode.
    state: dict = {}
    posting = _posting()
    new_state, to_notify = diff_and_update(
        state,
        {SOURCE: [posting]},
        {SOURCE: True},
        today=TODAY,
        retention_days=30,
        seed_window_days=30,
    )
    assert to_notify == []
    key = canonical_key(posting)
    assert key in new_state
    assert new_state[key]["status"] == "open"


def test_seed_mode_skips_postings_older_than_seed_window():
    state: dict = {}
    old_posting = _posting(date_posted=date(2026, 1, 1))
    new_state, to_notify = diff_and_update(
        state,
        {SOURCE: [old_posting]},
        {SOURCE: True},
        today=TODAY,
        retention_days=30,
        seed_window_days=30,
    )
    assert to_notify == []
    assert canonical_key(old_posting) not in new_state


def test_failing_source_does_not_close_its_jobs():
    posting = _posting()
    key = canonical_key(posting)
    state = {
        key: {
            "first_seen": "2026-08-01",
            "last_seen": "2026-08-23",
            "status": "open",
            "source": SOURCE,
            "sources": [SOURCE],
            "url": posting.url,
        }
    }
    # Source fetch fails this run and reports nothing.
    new_state, to_notify = diff_and_update(
        state,
        {SOURCE: []},
        {SOURCE: False},
        today=TODAY,
        retention_days=30,
        seed_window_days=30,
    )
    assert new_state[key]["status"] == "open"
    assert to_notify == []


def test_absent_from_successful_source_closes_job():
    posting = _posting()
    key = canonical_key(posting)
    state = {
        key: {
            "first_seen": "2026-08-01",
            "last_seen": "2026-08-23",
            "status": "open",
            "source": SOURCE,
            "sources": [SOURCE],
            "url": posting.url,
        }
    }
    new_state, to_notify = diff_and_update(
        state,
        {SOURCE: []},
        {SOURCE: True},
        today=TODAY,
        retention_days=30,
        seed_window_days=30,
    )
    assert new_state[key]["status"] == "closed"
    assert to_notify == []


def test_explicit_active_false_closes_job():
    posting = _posting()
    key = canonical_key(posting)
    state = {
        key: {
            "first_seen": "2026-08-01",
            "last_seen": "2026-08-23",
            "status": "open",
            "source": SOURCE,
            "sources": [SOURCE],
            "url": posting.url,
        }
    }
    closed_posting = _posting(active=False)
    new_state, to_notify = diff_and_update(
        state,
        {SOURCE: [closed_posting]},
        {SOURCE: True},
        today=TODAY,
        retention_days=30,
        seed_window_days=30,
    )
    assert new_state[key]["status"] == "closed"
    assert to_notify == []


def test_reopen_after_closed_notifies_as_new():
    posting = _posting()
    key = canonical_key(posting)
    state = {
        key: {
            "first_seen": "2026-08-01",
            "last_seen": "2026-08-10",
            "status": "closed",
            "source": SOURCE,
            "sources": [SOURCE],
            "url": posting.url,
        }
    }
    new_state, to_notify = diff_and_update(
        state,
        {SOURCE: [posting]},
        {SOURCE: True},
        today=TODAY,
        retention_days=30,
        seed_window_days=30,
    )
    assert new_state[key]["status"] == "open"
    assert to_notify == [posting]


def test_content_only_change_does_not_renotify():
    # Same posting stays open across a run; must not be re-notified even
    # though e.g. its URL/title text could have been edited upstream.
    posting = _posting()
    key = canonical_key(posting)
    state = {
        key: {
            "first_seen": "2026-08-01",
            "last_seen": "2026-08-26",
            "status": "open",
            "source": SOURCE,
            "sources": [SOURCE],
            "url": posting.url,
        }
    }
    new_state, to_notify = diff_and_update(
        state,
        {SOURCE: [posting]},
        {SOURCE: True},
        today=TODAY,
        retention_days=30,
        seed_window_days=30,
    )
    assert to_notify == []
    assert new_state[key]["last_seen"] == "2026-08-27"


def test_prune_drops_entries_older_than_retention():
    state = {
        "stale|key|here": {
            "first_seen": "2026-01-01",
            "last_seen": "2026-01-01",
            "status": "closed",
            "source": SOURCE,
            "sources": [SOURCE],
            "url": "https://example.com/stale",
        }
    }
    new_state, _ = diff_and_update(
        state,
        {SOURCE: []},
        {SOURCE: True},
        today=TODAY,
        retention_days=30,
        seed_window_days=30,
    )
    assert "stale|key|here" not in new_state


def test_multi_source_key_requires_all_sources_to_close():
    posting = _posting()
    key = canonical_key(posting)
    other_source = "tier2:greenhouse:citadel"
    state = {
        key: {
            "first_seen": "2026-08-01",
            "last_seen": "2026-08-26",
            "status": "open",
            "source": other_source,
            "sources": [SOURCE, other_source],
            "url": posting.url,
        }
    }
    # SOURCE fetches successfully and no longer reports it, but other_source
    # fails to fetch this run -- must not close.
    new_state, to_notify = diff_and_update(
        state,
        {SOURCE: [], other_source: []},
        {SOURCE: True, other_source: False},
        today=TODAY,
        retention_days=30,
        seed_window_days=30,
    )
    assert new_state[key]["status"] == "open"
    assert to_notify == []
