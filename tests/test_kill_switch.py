from __future__ import annotations

import pytest

from cryptoquant.risk import KillSwitch, KillSwitchScope


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


def test_kill_switch_supports_account_scope() -> None:
    ks = KillSwitch()
    ks.engage("account incident", scope=KillSwitchScope.ACCOUNT, account_id="acct-a")

    with pytest.raises(RuntimeError, match=r"kill switch active\[account\]"):
        ks.assert_allows_execution(account_id="acct-a")

    ks.assert_allows_execution(account_id="acct-b")


def test_kill_switch_supports_strategy_scope_with_optional_account_binding() -> None:
    ks = KillSwitch()
    ks.engage("strategy paused", scope=KillSwitchScope.STRATEGY, strategy_id="mean-revert")
    ks.engage(
        "strategy paused for account",
        scope=KillSwitchScope.STRATEGY,
        account_id="acct-a",
        strategy_id="carry",
    )

    with pytest.raises(RuntimeError, match=r"kill switch active\[strategy\]"):
        ks.assert_allows_execution(strategy_id="mean-revert")

    with pytest.raises(RuntimeError, match=r"kill switch active\[strategy\]"):
        ks.assert_allows_execution(account_id="acct-a", strategy_id="carry")

    ks.assert_allows_execution(account_id="acct-b", strategy_id="carry")


def test_kill_switch_global_has_highest_priority_over_scoped_rules() -> None:
    ks = KillSwitch()
    ks.engage("acct issue", scope=KillSwitchScope.ACCOUNT, account_id="acct-a")
    ks.engage("global halt", scope=KillSwitchScope.GLOBAL)

    with pytest.raises(RuntimeError, match=r"kill switch active\[global\]: global halt"):
        ks.assert_allows_execution(account_id="acct-a")
