import pytest

from jobnotifier.config import ConfigError, load_config


def test_load_real_config_yaml(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    config = load_config("config/config.yaml")

    assert len(config.sources.tier1_aggregators) == 2
    first = config.sources.tier1_aggregators[0]
    assert first.repo == "SimplifyJobs/Summer2026-Internships"
    assert first.ref == "dev"
    assert first.path == ".github/scripts/listings.json"

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
