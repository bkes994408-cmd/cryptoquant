"""Environment-aware configuration loader.

Supports three environments:
- dev (default)
- stg
- prd

Configuration is loaded from JSON files under ``config/`` and can be overridden
by environment variables for secrets and runtime customization.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

_ALLOWED_ENVS = {"dev", "stg", "prd"}


@dataclass(frozen=True)
class AppConfig:
    env: str
    app_name: str
    log_level: str
    market_ws_url: str
    api_key: str | None
    api_secret: str | None


class ConfigError(ValueError):
    """Raised when configuration is invalid or cannot be loaded."""


def _config_root() -> Path:
    return Path(__file__).resolve().parents[2] / "config"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_env(env: str | None = None) -> str:
    resolved = (env or os.getenv("CRYPTOQUANT_ENV") or "dev").strip().lower()
    if resolved not in _ALLOWED_ENVS:
        raise ConfigError(
            f"Unsupported environment '{resolved}'. "
            f"Use one of: {', '.join(sorted(_ALLOWED_ENVS))}"
        )
    return resolved


def load_config(env: str | None = None) -> AppConfig:
    """Load layered config for target environment.

    Layer order (low -> high priority):
    1) config/config.base.json
    2) config/config.<env>.json
    3) environment variables
    """

    resolved_env = _resolve_env(env)
    root = _config_root()

    data: Dict[str, Any] = {}
    data.update(_read_json(root / "config.base.json"))
    data.update(_read_json(root / f"config.{resolved_env}.json"))

    # Env var overrides (especially for secrets)
    data["api_key"] = os.getenv("CRYPTOQUANT_API_KEY", data.get("api_key"))
    data["api_secret"] = os.getenv("CRYPTOQUANT_API_SECRET", data.get("api_secret"))
    data["log_level"] = os.getenv("CRYPTOQUANT_LOG_LEVEL", data.get("log_level", "INFO"))

    return AppConfig(
        env=resolved_env,
        app_name=str(data.get("app_name", "cryptoquant")),
        log_level=str(data.get("log_level", "INFO")),
        market_ws_url=str(data["market_ws_url"]),
        api_key=data.get("api_key"),
        api_secret=data.get("api_secret"),
    )
