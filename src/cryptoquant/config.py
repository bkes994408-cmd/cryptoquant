"""Configuration helpers with environment layering.

Priority order (low -> high):
1) Base defaults
2) Environment defaults (dev/stg/prd)
3) CQ_* environment variables
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from typing import Any, Dict


_ENV_ALIASES = {
    "dev": "dev",
    "development": "dev",
    "stg": "stg",
    "staging": "stg",
    "prd": "prd",
    "prod": "prd",
    "production": "prd",
}


@dataclass(frozen=True)
class Settings:
    env: str = "dev"
    log_level: str = "DEBUG"
    rest_base_url: str = "https://testnet.binancefuture.com"
    ws_base_url: str = "wss://stream.binancefuture.com/ws"
    default_symbol: str = "BTCUSDT"
    paper_trading: bool = True
    max_leverage: int = 3


_BASE_DEFAULTS: Dict[str, Any] = asdict(Settings())
_ENV_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "dev": {
        "log_level": "DEBUG",
        "paper_trading": True,
        "max_leverage": 3,
    },
    "stg": {
        "log_level": "INFO",
        "paper_trading": True,
        "max_leverage": 2,
    },
    "prd": {
        "log_level": "WARNING",
        "paper_trading": False,
        "max_leverage": 1,
    },
}


_FIELD_TYPES = {
    "env": str,
    "log_level": str,
    "rest_base_url": str,
    "ws_base_url": str,
    "default_symbol": str,
    "paper_trading": bool,
    "max_leverage": int,
}


def _normalize_env(value: str | None) -> str:
    env = (value or "dev").strip().lower()
    if env not in _ENV_ALIASES:
        raise ValueError(f"Unsupported environment: {value}")
    return _ENV_ALIASES[env]


def _parse_value(field: str, value: str) -> Any:
    t = _FIELD_TYPES[field]
    if t is bool:
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if t is int:
        return int(value)
    if t is float:
        return float(value)
    return value


def load_settings(env: str | None = None) -> Settings:
    """Load settings with layered defaults and env-var overrides.

    Environment variables use `CQ_` prefix, for example:
    - CQ_ENV=stg
    - CQ_LOG_LEVEL=INFO
    - CQ_PAPER_TRADING=false
    """

    requested_env = env or os.getenv("CQ_ENV")
    normalized_env = _normalize_env(requested_env)

    merged: Dict[str, Any] = {}
    merged.update(_BASE_DEFAULTS)
    merged.update(_ENV_DEFAULTS[normalized_env])
    merged["env"] = normalized_env

    for field in _FIELD_TYPES:
        key = f"CQ_{field.upper()}"
        if key in os.environ:
            merged[field] = _parse_value(field, os.environ[key])

    merged["env"] = _normalize_env(str(merged["env"]))
    return Settings(**merged)
