import logging
from datetime import date

from jobnotifier import failure, filters, git_ops, notify
from jobnotifier import state as state_module
from jobnotifier.config import Config
from jobnotifier.models import Posting
from jobnotifier.sources import build_sources

logger = logging.getLogger(__name__)


def run_pipeline(config: Config, today: date | None = None) -> int:
    """Runs one full fetch->parse->dedup->filter->notify->prune->commit cycle.
    Returns the number of notifications sent. Raises RunAbortedError (via
    failure.check_or_raise) if too many sources failed to fetch."""
    today = today or date.today()
    sources = build_sources(config)

    postings_by_source: dict[str, list[Posting]] = {}
    fetch_success: dict[str, bool] = {}

    for source in sources:
        try:
            raw = source.fetch()
            postings_by_source[source.source_id] = source.parse(raw)
            fetch_success[source.source_id] = True
        except Exception:
            logger.exception("source %s failed to fetch; skipping this run", source.source_id)
            postings_by_source[source.source_id] = []
            fetch_success[source.source_id] = False

    # A source that fails to fetch is excluded from closed-posting inference
    # by diff_and_update itself (it only reads fetch_success), not here.
    failure.check_or_raise(fetch_success, config.failure.abort_threshold_pct)

    state = state_module.load_state(config.state.path)
    new_state, candidates = state_module.diff_and_update(
        state,
        postings_by_source,
        fetch_success,
        today=today,
        retention_days=config.state.retention_days,
        seed_window_days=config.state.seed_window_days,
    )

    to_notify = [
        posting
        for posting in candidates
        if filters.passes_filters(posting, config.filters)
        and filters.passes_freshness(posting, today)
    ]

    logger.info(
        "post-filter: %d of %d candidates passed title/location/seniority/freshness filters",
        len(to_notify),
        len(candidates),
    )

    sent = notify.send_notifications(
        to_notify,
        config.notification.discord_webhook_url,
        config.notification.per_run_cap,
    )

    state_module.save_state(config.state.path, new_state)
    if config.state.commit:
        git_ops.commit_and_push_state(
            config.state.path, f"Update job state ({today.isoformat()})"
        )

    logger.info(
        "run complete: %d candidates, %d notified, %d state entries",
        len(candidates),
        sent,
        len(new_state),
    )
    return sent
