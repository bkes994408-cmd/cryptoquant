from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ComplianceDecision:
    allowed: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComplianceRuleSet:
    blocked_symbols: frozenset[str] = field(default_factory=frozenset)
    allowed_accounts: frozenset[str] = field(default_factory=frozenset)
    max_abs_qty: float | None = None


class OrderComplianceChecker(Protocol):
    def check_order(self, *, account_id: str, symbol: str, qty: float) -> ComplianceDecision: ...


class RuleBasedComplianceChecker:
    """Simple pre-trade compliance checker for account/symbol/size constraints."""

    def __init__(self, rules: ComplianceRuleSet) -> None:
        self._rules = rules

    def check_order(self, *, account_id: str, symbol: str, qty: float) -> ComplianceDecision:
        reasons: list[str] = []

        if not account_id:
            reasons.append("account_id must not be empty")

        if symbol in self._rules.blocked_symbols:
            reasons.append(f"symbol {symbol} is blocked")

        if self._rules.allowed_accounts and account_id not in self._rules.allowed_accounts:
            reasons.append(f"account_id {account_id} is not in allowlist")

        if self._rules.max_abs_qty is not None and abs(qty) > self._rules.max_abs_qty:
            reasons.append(
                f"abs(qty) exceeds max_abs_qty: abs(qty)={abs(qty)} > {self._rules.max_abs_qty}"
            )

        return ComplianceDecision(allowed=not reasons, reasons=tuple(reasons))
