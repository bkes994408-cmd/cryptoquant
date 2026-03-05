from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

DEFAULT_SECRET_KEYS = {
    "api_key",
    "apikey",
    "secret",
    "api_secret",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "passphrase",
    "private_key",
}


def redact_secrets(value: Any, *, mask: str = "***", secret_keys: set[str] | None = None) -> Any:
    """Return a deep-redacted copy for safe logging.

    - Mapping keys matching known secret names are replaced by ``mask``.
    - Nested mappings/lists/tuples are recursively processed.
    - Primitive non-secret values are returned as-is.
    """

    keys = {k.lower() for k in (secret_keys or DEFAULT_SECRET_KEYS)}

    if isinstance(value, Mapping):
        out: dict[Any, Any] = {}
        for k, v in value.items():
            key_str = str(k).lower()
            if key_str in keys:
                out[k] = mask
            else:
                out[k] = redact_secrets(v, mask=mask, secret_keys=keys)
        return out

    if isinstance(value, tuple):
        return tuple(redact_secrets(v, mask=mask, secret_keys=keys) for v in value)

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_secrets(v, mask=mask, secret_keys=keys) for v in value]

    return value
