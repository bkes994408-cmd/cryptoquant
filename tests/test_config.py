from __future__ import annotations

import pytest

from cryptoquant.config import load_settings


def test_load_settings_defaults_to_dev() -> None:
    settings = load_settings()
    assert settings.env == "dev"
    assert settings.paper_trading is True
    assert settings.log_level == "DEBUG"


def test_load_settings_uses_env_layer() -> None:
    settings = load_settings("prd")
    assert settings.env == "prd"
    assert settings.paper_trading is False
    assert settings.log_level == "WARNING"


def test_load_settings_supports_aliases() -> None:
    settings = load_settings("production")
    assert settings.env == "prd"


def test_load_settings_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CQ_ENV", "stg")
    monkeypatch.setenv("CQ_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("CQ_PAPER_TRADING", "true")
    monkeypatch.setenv("CQ_MAX_LEVERAGE", "5")

    settings = load_settings()

    assert settings.env == "stg"
    assert settings.log_level == "ERROR"
    assert settings.paper_trading is True
    assert settings.max_leverage == 5


def test_load_settings_rejects_unknown_env() -> None:
    with pytest.raises(ValueError):
        load_settings("qa")
