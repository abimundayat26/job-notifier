import subprocess

import pytest

from jobnotifier.git_ops import PushFailedError, commit_and_push_state


class FakeRunner:
    def __init__(self, push_results):
        self.push_results = list(push_results)
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        if cmd[:2] == ["git", "status"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=" M state/seen_jobs.json\n", stderr="")
        if cmd[:2] == ["git", "push"]:
            code = self.push_results.pop(0)
            return subprocess.CompletedProcess(cmd, code, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


class FakeRunnerNoChanges:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        if cmd[:2] == ["git", "status"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


def test_commits_and_pushes_on_first_try():
    runner = FakeRunner(push_results=[0])
    result = commit_and_push_state("state/seen_jobs.json", "update state", runner=runner)
    assert result is True
    assert ["git", "commit", "-m", "update state"] in runner.calls
    assert runner.calls.count(["git", "push"]) == 1


def test_returns_false_when_nothing_to_commit():
    runner = FakeRunnerNoChanges()
    result = commit_and_push_state("state/seen_jobs.json", "update state", runner=runner)
    assert result is False
    assert not any(c[:2] == ["git", "commit"] for c in runner.calls)


def test_rebases_and_retries_on_push_rejection():
    runner = FakeRunner(push_results=[1, 0])
    result = commit_and_push_state("state/seen_jobs.json", "update state", runner=runner)
    assert result is True
    assert ["git", "fetch", "origin", "main"] in runner.calls
    assert ["git", "rebase", "origin/main"] in runner.calls
    assert runner.calls.count(["git", "push"]) == 2


def test_raises_after_exhausting_retries():
    runner = FakeRunner(push_results=[1, 1, 1])
    with pytest.raises(PushFailedError):
        commit_and_push_state("state/seen_jobs.json", "update state", max_retries=3, runner=runner)
