import json
from datetime import date
from pathlib import Path

from jobnotifier.models import Posting, canonical_key

_DATE_FMT = "%Y-%m-%d"


def load_state(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_state(path: str | Path, state: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


def _is_observed_open(posting: Posting) -> bool:
    # Present in a successfully-fetched source's results counts as open unless
    # that source explicitly says otherwise via `active`.
    return posting.active is not False


def diff_and_update(
    state: dict,
    postings_by_source: dict[str, list[Posting]],
    fetch_success: dict[str, bool],
    today: date,
    retention_days: int,
    seed_window_days: int,
) -> tuple[dict, list[Posting]]:
    """Diff freshly-fetched postings against committed state, update state in
    place (returning a new dict), and return the postings a caller should
    consider notifying on (new-to-state, not seeded, or reopened).

    See SPEC.md §9 for the closure-gating and reopen rules this implements.
    """
    new_state: dict = {k: dict(v, sources=list(v.get("sources", []))) for k, v in state.items()}
    to_consider: list[Posting] = []

    known_source_ids: set[str] = set()
    for entry in state.values():
        known_source_ids.update(entry.get("sources", []))

    observed_open_keys: set[str] = set()
    today_str = today.strftime(_DATE_FMT)

    for source_id, postings in postings_by_source.items():
        if not fetch_success.get(source_id, False):
            continue
        is_seed_source = source_id not in known_source_ids
        for posting in postings:
            if not _is_observed_open(posting):
                continue
            key = canonical_key(posting)
            observed_open_keys.add(key)
            existing = new_state.get(key)

            if existing is None:
                if is_seed_source:
                    if posting.date_posted is not None:
                        age_days = (today - posting.date_posted).days
                        if age_days > seed_window_days:
                            continue  # too old to seed; not tracked at all
                    new_state[key] = {
                        "first_seen": today_str,
                        "last_seen": today_str,
                        "status": "open",
                        "source": source_id,
                        "sources": [source_id],
                        "url": posting.url,
                    }
                    # Seeded silently: no notification.
                else:
                    new_state[key] = {
                        "first_seen": today_str,
                        "last_seen": today_str,
                        "status": "open",
                        "source": source_id,
                        "sources": [source_id],
                        "url": posting.url,
                    }
                    to_consider.append(posting)
            else:
                was_closed = existing["status"] == "closed"
                existing["last_seen"] = today_str
                existing["status"] = "open"
                existing["source"] = source_id
                existing["url"] = posting.url
                if source_id not in existing["sources"]:
                    existing["sources"].append(source_id)
                if was_closed:
                    to_consider.append(posting)

    # Closure pass: any currently-open state entry not observed open this run
    # gets closed, but only if every source that has ever reported it fetched
    # successfully this run (a failing source must never imply closure).
    for key, entry in new_state.items():
        if entry["status"] != "open" or key in observed_open_keys:
            continue
        sources = entry.get("sources", [])
        all_fetched_ok = bool(sources) and all(fetch_success.get(sid, False) for sid in sources)
        if all_fetched_ok:
            entry["status"] = "closed"

    # Prune: drop entries not seen open in over retention_days days.
    pruned_state = {
        key: entry
        for key, entry in new_state.items()
        if (today - date.fromisoformat(entry["last_seen"])).days <= retention_days
    }

    return pruned_state, to_consider
