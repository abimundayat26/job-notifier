import pytest

from jobnotifier.failure import RunAbortedError, check_or_raise, should_abort


def test_no_sources_never_aborts():
    assert not should_abort({}, abort_threshold_pct=50)


def test_below_threshold_does_not_abort():
    fetch_success = {"a": True, "b": True, "c": False, "d": True}
    assert not should_abort(fetch_success, abort_threshold_pct=50)


def test_above_threshold_aborts():
    fetch_success = {"a": False, "b": False, "c": True}
    assert should_abort(fetch_success, abort_threshold_pct=50)


def test_exactly_at_threshold_does_not_abort():
    fetch_success = {"a": False, "b": True}
    assert not should_abort(fetch_success, abort_threshold_pct=50)


def test_check_or_raise_raises_with_source_names():
    fetch_success = {"tier1:a": False, "tier1:b": False, "tier1:c": True}
    with pytest.raises(RunAbortedError, match="tier1:a"):
        check_or_raise(fetch_success, abort_threshold_pct=50)


def test_check_or_raise_passes_when_healthy():
    fetch_success = {"tier1:a": True, "tier1:b": True}
    check_or_raise(fetch_success, abort_threshold_pct=50)  # should not raise
