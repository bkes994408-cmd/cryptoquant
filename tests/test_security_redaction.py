from __future__ import annotations

from cryptoquant.security import redact_secrets


def test_redact_secrets_masks_known_secret_keys_recursively() -> None:
    payload = {
        "api_key": "abc",
        "nested": {
            "secret": "def",
            "public": "ok",
            "arr": [{"token": "ghi"}, {"x": 1}],
        },
        "password": "pw",
    }

    redacted = redact_secrets(payload)

    assert redacted["api_key"] == "***"
    assert redacted["nested"]["secret"] == "***"
    assert redacted["nested"]["public"] == "ok"
    assert redacted["nested"]["arr"][0]["token"] == "***"
    assert redacted["password"] == "***"


def test_redact_secrets_keeps_original_input_unchanged() -> None:
    payload = {"api_secret": "abc", "value": 1}

    redacted = redact_secrets(payload)

    assert payload["api_secret"] == "abc"
    assert redacted["api_secret"] == "***"
