from jobnotifier.config import (
    Config,
    FailureConfig,
    FiltersConfig,
    NotificationConfig,
    SourcesConfig,
    StateConfig,
)
from jobnotifier.sources import build_sources


def _config(**sources_kwargs) -> Config:
    return Config(
        sources=SourcesConfig(**sources_kwargs),
        filters=FiltersConfig(),
        notification=NotificationConfig(
            summer_webhook_url="https://discord.example/summer",
            off_season_webhook_url="https://discord.example/off-season",
        ),
        state=StateConfig(),
        failure=FailureConfig(),
    )


def test_build_sources_ignores_tier4_manual():
    """Tier 4 is a plain manual-check list (SPEC.md §4), not a fetchable source --
    build_sources() must never produce a Source for it."""
    config = _config(tier4_manual=["Citadel Securities", "D. E. Shaw"])
    assert build_sources(config) == []
