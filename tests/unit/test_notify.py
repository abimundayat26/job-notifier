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
    posting = _posting(date_posted=None, salary=None)
    embed = build_message(posting)["embeds"][0]
    field_names = {f["name"] for f in embed["fields"]}
    assert "Posted" not in field_names
    assert "Salary" not in field_names


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


def test_send_notifications_empty_list_sends_nothing():
    sent = send_notifications(
        [], "https://discord.example/webhook", per_run_cap=20,
        post_fn=lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not be called")),
        sleep_fn=lambda s: (_ for _ in ()).throw(AssertionError("should not be called")),
    )
    assert sent == 0
