class RunAbortedError(RuntimeError):
    """Raised when more than the configured threshold of sources failed to
    fetch in a single run (SPEC.md §12). The caller should let this propagate
    out of run.py as a nonzero exit — that exit code IS the alerting
    mechanism; no custom notification is sent for this condition."""


def should_abort(fetch_success: dict[str, bool], abort_threshold_pct: int) -> bool:
    if not fetch_success:
        return False
    failed = sum(1 for ok in fetch_success.values() if not ok)
    failed_pct = (failed / len(fetch_success)) * 100
    return failed_pct > abort_threshold_pct


def check_or_raise(fetch_success: dict[str, bool], abort_threshold_pct: int) -> None:
    if should_abort(fetch_success, abort_threshold_pct):
        failed_sources = sorted(sid for sid, ok in fetch_success.items() if not ok)
        raise RunAbortedError(
            f"{len(failed_sources)}/{len(fetch_success)} sources failed to fetch "
            f"(exceeds {abort_threshold_pct}% threshold): {', '.join(failed_sources)}"
        )
