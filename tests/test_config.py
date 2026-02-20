import pytest

from cryptoquant.config import ConfigError, load_config


def test_load_dev_config_defaults(monkeypatch):
    monkeypatch.delenv("CRYPTOQUANT_ENV", raising=False)
    cfg = load_config()

    assert cfg.env == "dev"
    assert cfg.log_level == "DEBUG"
    assert "testnet.binance.vision" in cfg.market_ws_url


def test_load_stg_config_by_argument():
    cfg = load_config("stg")

    assert cfg.env == "stg"
    assert cfg.log_level == "INFO"


def test_env_var_override_for_secrets(monkeypatch):
    monkeypatch.setenv("CRYPTOQUANT_ENV", "prd")
    monkeypatch.setenv("CRYPTOQUANT_API_KEY", "dummy_key")
    monkeypatch.setenv("CRYPTOQUANT_API_SECRET", "dummy_secret")
    monkeypatch.setenv("CRYPTOQUANT_LOG_LEVEL", "ERROR")

    cfg = load_config()

    assert cfg.env == "prd"
    assert cfg.api_key == "dummy_key"
    assert cfg.api_secret == "dummy_secret"
    assert cfg.log_level == "ERROR"


def test_invalid_env_raises_error():
    with pytest.raises(ConfigError):
        load_config("qa")
