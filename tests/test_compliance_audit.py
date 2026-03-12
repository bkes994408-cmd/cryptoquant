from __future__ import annotations

from cryptoquant.compliance import (
    AuditTrail,
    ComplianceRuleSet,
    RuleBasedComplianceChecker,
)


def test_rule_based_compliance_checker_allows_valid_order() -> None:
    checker = RuleBasedComplianceChecker(
        ComplianceRuleSet(
            blocked_symbols=frozenset({"XRPUSDT"}),
            allowed_accounts=frozenset({"acct-a"}),
            max_abs_qty=2.0,
        )
    )

    decision = checker.check_order(account_id="acct-a", symbol="BTCUSDT", qty=1.5)

    assert decision.allowed is True
    assert decision.reasons == ()


def test_rule_based_compliance_checker_blocks_invalid_order() -> None:
    checker = RuleBasedComplianceChecker(
        ComplianceRuleSet(
            blocked_symbols=frozenset({"XRPUSDT"}),
            allowed_accounts=frozenset({"acct-a"}),
            max_abs_qty=2.0,
        )
    )

    decision = checker.check_order(account_id="acct-b", symbol="XRPUSDT", qty=3.0)

    assert decision.allowed is False
    assert len(decision.reasons) == 3


def test_audit_trail_hash_chain_and_redaction() -> None:
    now = iter([1000, 2000])
    trail = AuditTrail(now_ms_fn=lambda: next(now))

    event1 = trail.append(
        event_type="execution.order_submitted",
        actor="executor",
        payload={"client_order_id": "coid-1", "api_key": "secret-key"},
    )
    event2 = trail.append(
        event_type="execution.order_acknowledged",
        actor="executor",
        payload={"client_order_id": "coid-1", "exchange_order_id": "123"},
    )

    assert event1.payload["api_key"] == "***"
    assert event2.prev_hash == event1.event_hash
    assert trail.verify_chain() is True


def test_audit_trail_detects_tamper() -> None:
    trail = AuditTrail(now_ms_fn=lambda: 1000)
    trail.append(event_type="x", actor="a", payload={"k": "v"})

    # mutate internal payload intentionally to emulate tampering
    trail._events[0].payload["k"] = "hacked"  # type: ignore[misc]

    assert trail.verify_chain() is False
