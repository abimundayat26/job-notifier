from datetime import date

from jobnotifier.models import Posting, canonical_key
from jobnotifier.notify import build_message, send_notifications


def _posting(**overrides):
    defaults = dict(
        company="Citadel",
        title="Quantitative Researcher",
        location="NYC",
        url="https://example.com/job/1",
        date_posted=date(2026, 8, 20),
        source_id="tier1:SimplifyJobs/New-Grad-Positions",
    )
    defaults.update(overrides)
    return Posting(**defaults)


def test_build_message_includes_required_fields():
    posting = _posting(salary="$150k-$200k")
    message = build_message(posting)
    embed = message["embeds"][0]
    assert embed["title"] == posting.title
    assert embed["url"] == posting.url
    field_names = {f["name"] for f in embed["fields"]}
    assert {"Company", "Location", "Source", "Posted", "Salary", "Job Key"} <= field_names
    job_key_field = next(f for f in embed["fields"] if f["name"] == "Job Key")
    assert job_key_field["value"] == canonical_key(posting)


def test_build_message_omits_absent_optional_fields():
    posting = _posting(date_posted=None, salary=None, term=None)
    embed = build_message(posting)["embeds"][0]
    field_names = {f["name"] for f in embed["fields"]}
    assert "Posted" not in field_names
    assert "Salary" not in field_names
    assert "Term" not in field_names


def test_build_message_includes_term_when_present():
    posting = _posting(term="Summer 2027")
    embed = build_message(posting)["embeds"][0]
    term_field = next(f for f in embed["fields"] if f["name"] == "Term")
    assert term_field["value"] == "Summer 2027"


def test_build_message_truncates_long_location():
    long_location = "; ".join(f"City {i}, ST" for i in range(30))
    posting = _posting(location=long_location)
    embed = build_message(posting)["embeds"][0]
    location_field = next(f for f in embed["fields"] if f["name"] == "Location")
    assert len(location_field["value"]) <= 103  # max len + "..."
    assert location_field["value"].endswith("...")
    assert not location_field["value"][:-3].endswith(";")  # cut at a full location, not mid-entry


def test_build_message_short_location_not_truncated():
    posting = _posting(location="New York, NY; Remote")
    embed = build_message(posting)["embeds"][0]
    location_field = next(f for f in embed["fields"] if f["name"] == "Location")
    assert location_field["value"] == "New York, NY; Remote"


def test_send_notifications_respects_per_run_cap():
    postings = [_posting(title=f"Job {i}") for i in range(5)]
    calls = []

    def fake_post(url, json, timeout):
        calls.append(json)

        class Resp:
            def raise_for_status(self):
                pass

        return Resp()

    sleeps = []
    sent = send_notifications(
        postings, "https://discord.example/webhook", per_run_cap=2,
        post_fn=fake_post, sleep_fn=sleeps.append,
    )
    assert sent == 2
    assert len(calls) == 2
    assert len(sleeps) == 1  # throttled between the two sends, not after the last


def test_send_notifications_one_failure_does_not_block_remaining_sends():
    # A single posting's send failing (network blip, Discord 429/5xx, bad
    # embed) must not abort the batch -- otherwise an exception here would
    # propagate out of the pipeline and prevent state from being saved,
    # causing already-delivered notifications to be re-sent next run.
    postings = [_posting(title=f"Job {i}", url=f"https://example.com/job/{i}") for i in range(3)]
    calls = []

    class OkResp:
        def raise_for_status(self):
            pass

    def flaky_post(url, json, timeout):
        calls.append(json)
        if len(calls) == 2:
            raise ConnectionError("simulated network blip")
        return OkResp()

    sent = send_notifications(
        postings, "https://discord.example/webhook", per_run_cap=20,
        post_fn=flaky_post, sleep_fn=lambda s: None,
    )
    assert len(calls) == 3  # all three were attempted despite the middle one failing
    assert sent == 2  # only the two that actually succeeded are counted


def test_send_notifications_raise_for_status_failure_does_not_raise():
    postings = [_posting()]

    class BadResp:
        def raise_for_status(self):
            raise RuntimeError("Discord 429")

    sent = send_notifications(
        postings, "https://discord.example/webhook", per_run_cap=20,
        post_fn=lambda *a, **k: BadResp(), sleep_fn=lambda s: None,
    )
    assert sent == 0


def test_send_notifications_empty_list_sends_nothing():
    sent = send_notifications(
        [], "https://discord.example/webhook", per_run_cap=20,
        post_fn=lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not be called")),
        sleep_fn=lambda s: (_ for _ in ()).throw(AssertionError("should not be called")),
    )
    assert sent == 0
