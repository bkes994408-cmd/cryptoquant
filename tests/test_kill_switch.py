from __future__ import annotations

import pytest

from cryptoquant.risk import KillSwitch


def test_kill_switch_engage_and_release() -> None:
    ks = KillSwitch()

    assert ks.active is False
    assert ks.reason is None

    ks.engage("manual stop")
    assert ks.active is True
    assert ks.reason == "manual stop"

    ks.release()
    assert ks.active is False
    assert ks.reason is None


def test_kill_switch_blocks_execution_when_active() -> None:
    ks = KillSwitch()
    ks.engage("incident")

    with pytest.raises(RuntimeError, match="kill switch active"):
        ks.assert_allows_execution()
