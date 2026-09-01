import pytest

from jobnotifier.config import ConfigError, load_config


def test_load_real_config_yaml(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config = load_config("config/config.yaml")

    assert len(config.sources.tier1_aggregators) == 1
    first = config.sources.tier1_aggregators[0]
    assert first.repo == "SimplifyJobs/Summer2027-Internships"
    assert first.ref == "dev"
    assert first.path == ".github/scripts/listings.json"

    assert len(config.sources.tier2_ats) == 1
    assert config.sources.tier2_ats[0].company == "Palantir"

    assert len(config.sources.tier3_scrapers) == 1
    assert config.sources.tier3_scrapers[0].company == "citadel"

    assert "Citadel Securities" in config.sources.tier4_manual
    assert "D. E. Shaw" in config.sources.tier4_manual

    assert config.notification.discord_webhook_url == "https://discord.com/api/webhooks/test"
    assert config.state.retention_days == 30
    assert config.state.commit is True
    assert config.failure.abort_threshold_pct == 50


def test_missing_env_var_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
notification:
  discord_webhook_url: "${DISCORD_WEBHOOK_URL}"
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_missing_required_field_raises(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("sources: {}\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_state_commit_defaults_to_false_when_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
notification:
  discord_webhook_url: "${DISCORD_WEBHOOK_URL}"
""",
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert config.state.commit is False


def test_state_commit_true_is_read(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
notification:
  discord_webhook_url: "${DISCORD_WEBHOOK_URL}"
state:
  commit: true
""",
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert config.state.commit is True


def test_tier1_row_missing_ref_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sources:
  tier1_aggregators:
    - repo: "SimplifyJobs/Summer2026-Internships"
      path: ".github/scripts/listings.json"
notification:
  discord_webhook_url: "${DISCORD_WEBHOOK_URL}"
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_tier2_ats_row_parses(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sources:
  tier2_ats:
    - platform: greenhouse
      company: "Example Co"
      slug: "examplecoslug"
notification:
  discord_webhook_url: "${DISCORD_WEBHOOK_URL}"
""",
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert len(config.sources.tier2_ats) == 1
    row = config.sources.tier2_ats[0]
    assert row.platform == "greenhouse"
    assert row.company == "Example Co"
    assert row.slug == "examplecoslug"


def test_tier2_ats_row_missing_slug_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sources:
  tier2_ats:
    - platform: greenhouse
      company: "Example Co"
notification:
  discord_webhook_url: "${DISCORD_WEBHOOK_URL}"
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_tier3_scraper_row_parses(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sources:
  tier3_scrapers:
    - company: "citadel"
      fetch_method: http
      sort_order: relevance
notification:
  discord_webhook_url: "${DISCORD_WEBHOOK_URL}"
""",
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert len(config.sources.tier3_scrapers) == 1
    row = config.sources.tier3_scrapers[0]
    assert row.company == "citadel"
    assert row.fetch_method == "http"
    assert row.sort_order == "relevance"


def test_tier3_scraper_row_missing_fetch_method_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sources:
  tier3_scrapers:
    - company: "citadel"
      sort_order: relevance
notification:
  discord_webhook_url: "${DISCORD_WEBHOOK_URL}"
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_tier3_scraper_row_invalid_sort_order_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sources:
  tier3_scrapers:
    - company: "citadel"
      fetch_method: http
      sort_order: alphabetical
notification:
  discord_webhook_url: "${DISCORD_WEBHOOK_URL}"
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_tier3_scraper_row_invalid_fetch_method_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sources:
  tier3_scrapers:
    - company: "citadel"
      fetch_method: carrier_pigeon
      sort_order: relevance
notification:
  discord_webhook_url: "${DISCORD_WEBHOOK_URL}"
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_tier4_manual_distinct_entries_parse(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sources:
  tier4_manual:
    - "Citadel Securities"
    - "D. E. Shaw"
notification:
  discord_webhook_url: "${DISCORD_WEBHOOK_URL}"
""",
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert config.sources.tier4_manual == ["Citadel Securities", "D. E. Shaw"]


def test_tier4_manual_empty_entry_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sources:
  tier4_manual:
    - "   "
notification:
  discord_webhook_url: "${DISCORD_WEBHOOK_URL}"
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_tier4_manual_duplicate_entry_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sources:
  tier4_manual:
    - "Foo Corp"
    - "  foo corp  "
notification:
  discord_webhook_url: "${DISCORD_WEBHOOK_URL}"
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_tier4_manual_collides_with_tier2_ats_company_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sources:
  tier2_ats:
    - platform: greenhouse
      company: "Example Co"
      slug: "examplecoslug"
  tier4_manual:
    - "example co"
notification:
  discord_webhook_url: "${DISCORD_WEBHOOK_URL}"
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_tier4_manual_collides_with_tier3_scraper_company_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sources:
  tier3_scrapers:
    - company: "citadel"
      fetch_method: http
      sort_order: relevance
  tier4_manual:
    - "Citadel"
notification:
  discord_webhook_url: "${DISCORD_WEBHOOK_URL}"
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(config_path)
