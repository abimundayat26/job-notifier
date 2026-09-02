import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from jobnotifier import normalize

_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(ValueError):
    pass


def _substitute_env_vars(value):
    if isinstance(value, str):
        def replace(match: re.Match) -> str:
            name = match.group(1)
            if name not in os.environ:
                raise ConfigError(f"environment variable '{name}' referenced in config is not set")
            return os.environ[name]

        return _ENV_VAR_RE.sub(replace, value)
    if isinstance(value, dict):
        return {k: _substitute_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env_vars(v) for v in value]
    return value


@dataclass(frozen=True)
class Tier1AggregatorConfig:
    repo: str
    ref: str
    path: str


@dataclass(frozen=True)
class Tier2AtsConfig:
    platform: str
    company: str
    slug: str


@dataclass(frozen=True)
class Tier3ScraperConfig:
    company: str
    fetch_method: str
    sort_order: str


@dataclass(frozen=True)
class SourcesConfig:
    tier1_aggregators: list[Tier1AggregatorConfig] = field(default_factory=list)
    tier2_ats: list[Tier2AtsConfig] = field(default_factory=list)
    tier3_scrapers: list[Tier3ScraperConfig] = field(default_factory=list)
    tier4_manual: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FiltersConfig:
    title_include: list[str] = field(default_factory=list)
    title_exclude: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    remote_only: bool = False
    us_only: bool = False
    seniority_exclude: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NotificationConfig:
    """Two Discord channels, split by a posting's term (Posting.terms):
    postings tagged with `summer_term` -- or with no term at all, e.g. the
    non-internship Palantir/Citadel sources -- go to summer_webhook_url;
    everything else goes to off_season_webhook_url. A posting whose *only*
    term is one of exclude_exact_terms (e.g. a lone "Fall 2026") is dropped
    entirely rather than sent to either channel. per_channel_cap applies
    independently to each channel, not to the combined total."""

    summer_webhook_url: str
    off_season_webhook_url: str
    per_channel_cap: int = 10
    summer_term: str = "Summer 2027"
    exclude_exact_terms: list[str] = field(default_factory=lambda: ["Fall 2026"])


@dataclass(frozen=True)
class StateConfig:
    path: str = "state/seen_jobs.json"
    retention_days: int = 30
    seed_window_days: int = 30
    commit: bool = False


@dataclass(frozen=True)
class FailureConfig:
    abort_threshold_pct: int = 50


@dataclass(frozen=True)
class Config:
    sources: SourcesConfig
    filters: FiltersConfig
    notification: NotificationConfig
    state: StateConfig
    failure: FailureConfig


def _require(mapping: dict, key: str, context: str):
    if key not in mapping:
        raise ConfigError(f"missing required '{key}' in {context}")
    return mapping[key]


def _build_tier1_aggregators(rows: list[dict]) -> list[Tier1AggregatorConfig]:
    result = []
    for i, row in enumerate(rows):
        context = f"sources.tier1_aggregators[{i}]"
        result.append(
            Tier1AggregatorConfig(
                repo=_require(row, "repo", context),
                ref=_require(row, "ref", context),
                path=_require(row, "path", context),
            )
        )
    return result


def _build_tier2_ats(rows: list[dict]) -> list[Tier2AtsConfig]:
    result = []
    for i, row in enumerate(rows):
        context = f"sources.tier2_ats[{i}]"
        result.append(
            Tier2AtsConfig(
                platform=_require(row, "platform", context),
                company=_require(row, "company", context),
                slug=_require(row, "slug", context),
            )
        )
    return result


_VALID_FETCH_METHODS = {"http", "playwright"}
_VALID_SORT_ORDERS = {"date", "relevance"}


def _build_tier3_scrapers(rows: list[dict]) -> list[Tier3ScraperConfig]:
    result = []
    for i, row in enumerate(rows):
        context = f"sources.tier3_scrapers[{i}]"
        fetch_method = _require(row, "fetch_method", context)
        if fetch_method not in _VALID_FETCH_METHODS:
            raise ConfigError(
                f"invalid fetch_method '{fetch_method}' in {context} "
                f"(must be one of {sorted(_VALID_FETCH_METHODS)})"
            )
        sort_order = _require(row, "sort_order", context)
        if sort_order not in _VALID_SORT_ORDERS:
            raise ConfigError(
                f"invalid sort_order '{sort_order}' in {context} "
                f"(must be one of {sorted(_VALID_SORT_ORDERS)})"
            )
        result.append(
            Tier3ScraperConfig(
                company=_require(row, "company", context),
                fetch_method=fetch_method,
                sort_order=sort_order,
            )
        )
    return result


def _build_tier4_manual(
    rows: list, tier2_rows: list[Tier2AtsConfig], tier3_rows: list[Tier3ScraperConfig]
) -> list[str]:
    automated_companies = {normalize.normalize_company(row.company): row.company for row in tier2_rows}
    automated_companies.update(
        {normalize.normalize_company(row.company): row.company for row in tier3_rows}
    )

    result: list[str] = []
    seen: dict[str, str] = {}
    for i, raw in enumerate(rows):
        context = f"sources.tier4_manual[{i}]"
        name = raw.strip() if isinstance(raw, str) else ""
        if not name:
            raise ConfigError(f"{context} must be a non-empty string")

        key = normalize.normalize_company(name)
        if key in seen:
            raise ConfigError(f"duplicate tier4_manual entry: '{name}' (also listed as '{seen[key]}')")
        if key in automated_companies:
            raise ConfigError(
                f"'{name}' is in tier4_manual but also has a configured tier2_ats/tier3_scrapers "
                f"row ('{automated_companies[key]}') -- remove it from one of the two"
            )

        seen[key] = name
        result.append(name)
    return result


def load_config(path: str | Path) -> Config:
    raw_text = Path(path).read_text(encoding="utf-8")
    raw = yaml.safe_load(raw_text) or {}
    raw = _substitute_env_vars(raw)

    sources_raw = raw.get("sources", {})
    tier2_ats = _build_tier2_ats(sources_raw.get("tier2_ats", []))
    tier3_scrapers = _build_tier3_scrapers(sources_raw.get("tier3_scrapers", []))
    sources = SourcesConfig(
        tier1_aggregators=_build_tier1_aggregators(sources_raw.get("tier1_aggregators", [])),
        tier2_ats=tier2_ats,
        tier3_scrapers=tier3_scrapers,
        tier4_manual=_build_tier4_manual(sources_raw.get("tier4_manual", []), tier2_ats, tier3_scrapers),
    )

    filters_raw = raw.get("filters", {})
    filters = FiltersConfig(
        title_include=filters_raw.get("title_include", []),
        title_exclude=filters_raw.get("title_exclude", []),
        locations=filters_raw.get("locations", []),
        remote_only=filters_raw.get("remote_only", False),
        us_only=filters_raw.get("us_only", False),
        seniority_exclude=filters_raw.get("seniority_exclude", []),
    )

    notification_raw = raw.get("notification", {})
    notification = NotificationConfig(
        summer_webhook_url=_require(notification_raw, "summer_webhook_url", "notification"),
        off_season_webhook_url=_require(notification_raw, "off_season_webhook_url", "notification"),
        per_channel_cap=notification_raw.get("per_channel_cap", 10),
        summer_term=notification_raw.get("summer_term", "Summer 2027"),
        exclude_exact_terms=notification_raw.get("exclude_exact_terms", ["Fall 2026"]),
    )

    state_raw = raw.get("state", {})
    state = StateConfig(
        path=state_raw.get("path", "state/seen_jobs.json"),
        retention_days=state_raw.get("retention_days", 30),
        seed_window_days=state_raw.get("seed_window_days", 30),
        commit=state_raw.get("commit", False),
    )

    failure_raw = raw.get("failure", {})
    failure = FailureConfig(
        abort_threshold_pct=failure_raw.get("abort_threshold_pct", 50),
    )

    return Config(
        sources=sources,
        filters=filters,
        notification=notification,
        state=state,
        failure=failure,
    )
