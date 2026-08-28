from datetime import date
from pathlib import Path

import pytest

from jobnotifier.config import (
    Config,
    FailureConfig,
    FiltersConfig,
    NotificationConfig,
    SourcesConfig,
    StateConfig,
)
from jobnotifier.failure import RunAbortedError
from jobnotifier.models import Posting
from jobnotifier.sources.base import Source
from jobnotifier import pipeline


class FakeSource(Source):
    tier = 1

    def __init__(self, source_id: str, postings: list[Posting]):
        self.source_id = source_id
        self._postings = postings

    def fetch(self):
        return self._postings

    def parse(self, raw):
        return raw


def _config(state_path: str, commit: bool = False) -> Config:
    return Config(
        sources=SourcesConfig(),
        filters=FiltersConfig(),
        notification=NotificationConfig(discord_webhook_url="https://discord.example/webhook", per_run_cap=20),
        state=StateConfig(path=state_path, retention_days=30, seed_window_days=30, commit=commit),
        failure=FailureConfig(abort_threshold_pct=50),
    )


def _posting(**overrides):
    defaults = dict(
        company="Acme",
        title="Software Engineer",
        location="Remote",
        url="https://example.com/job/1",
        date_posted=date(2026, 8, 25),
        active=True,
        source_id="tier1:fake",
    )
    defaults.update(overrides)
    return Posting(**defaults)


def _patch_pipeline_dependencies(monkeypatch, sources, sent_notifications):
    monkeypatch.setattr(pipeline, "build_sources", lambda config: sources)
    monkeypatch.setattr(pipeline.git_ops, "commit_and_push_state", lambda *a, **k: False)

    def fake_send(postings, webhook_url, per_run_cap, **kwargs):
        sent_notifications.extend(postings[:per_run_cap])
        return min(len(postings), per_run_cap)

    monkeypatch.setattr(pipeline.notify, "send_notifications", fake_send)


def test_first_run_seeds_silently(tmp_path, monkeypatch):
    state_path = str(tmp_path / "seen_jobs.json")
    config = _config(state_path)
    source = FakeSource("tier1:fake", [_posting()])
    sent = []
    _patch_pipeline_dependencies(monkeypatch, [source], sent)

    result = pipeline.run_pipeline(config, today=date(2026, 8, 27))

    assert result == 0
    assert sent == []


def test_new_posting_from_known_source_is_notified(tmp_path, monkeypatch):
    state_path = str(tmp_path / "seen_jobs.json")
    config = _config(state_path)

    seed_posting = _posting(title="First Role")
    source = FakeSource("tier1:fake", [seed_posting])
    sent = []
    _patch_pipeline_dependencies(monkeypatch, [source], sent)
    pipeline.run_pipeline(config, today=date(2026, 8, 20))  # seed run

    new_posting = _posting(title="Second Role", url="https://example.com/job/2")
    source._postings = [seed_posting, new_posting]
    sent.clear()
    result = pipeline.run_pipeline(config, today=date(2026, 8, 27))

    assert result == 1
    assert sent[0].title == "Second Role"


def test_unfiltered_posting_is_excluded_from_notification(tmp_path, monkeypatch):
    state_path = str(tmp_path / "seen_jobs.json")
    config = _config(state_path)
    config.filters.title_include.append("backend")

    seed_source = FakeSource("tier1:fake", [_posting(title="Seed Role")])
    sent = []
    _patch_pipeline_dependencies(monkeypatch, [seed_source], sent)
    pipeline.run_pipeline(config, today=date(2026, 8, 20))

    non_matching = _posting(title="Frontend Engineer", url="https://example.com/job/3")
    seed_source._postings = [_posting(title="Seed Role"), non_matching]
    sent.clear()
    result = pipeline.run_pipeline(config, today=date(2026, 8, 27))

    assert result == 0
    assert sent == []


def test_commit_false_skips_git_commit_step(tmp_path, monkeypatch):
    state_path = str(tmp_path / "seen_jobs.json")
    config = _config(state_path, commit=False)
    source = FakeSource("tier1:fake", [_posting()])
    sent = []
    _patch_pipeline_dependencies(monkeypatch, [source], sent)

    calls = []
    monkeypatch.setattr(pipeline.git_ops, "commit_and_push_state", lambda *a, **k: calls.append((a, k)))

    pipeline.run_pipeline(config, today=date(2026, 8, 27))

    assert calls == []
    assert Path(state_path).exists()  # state is still written to disk


def test_commit_true_runs_git_commit_step(tmp_path, monkeypatch):
    state_path = str(tmp_path / "seen_jobs.json")
    config = _config(state_path, commit=True)
    source = FakeSource("tier1:fake", [_posting()])
    sent = []
    _patch_pipeline_dependencies(monkeypatch, [source], sent)

    calls = []
    monkeypatch.setattr(pipeline.git_ops, "commit_and_push_state", lambda *a, **k: calls.append((a, k)))

    pipeline.run_pipeline(config, today=date(2026, 8, 27))

    assert len(calls) == 1
    args, _ = calls[0]
    assert args[0] == state_path


def test_failing_source_beyond_threshold_aborts(tmp_path, monkeypatch):
    state_path = str(tmp_path / "seen_jobs.json")
    config = _config(state_path)

    class BrokenSource(Source):
        tier = 1
        source_id = "tier1:broken"

        def fetch(self):
            raise RuntimeError("boom")

        def parse(self, raw):
            return []

    sent = []
    _patch_pipeline_dependencies(monkeypatch, [BrokenSource()], sent)

    with pytest.raises(RunAbortedError):
        pipeline.run_pipeline(config, today=date(2026, 8, 27))
