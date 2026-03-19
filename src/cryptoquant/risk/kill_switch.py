from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class KillSwitchScope(str, Enum):
    GLOBAL = "global"
    ACCOUNT = "account"
    STRATEGY = "strategy"


@dataclass(frozen=True)
class KillSwitchBlock:
    scope: KillSwitchScope
    reason: str


class KillSwitch:
    """Layered kill switch with strategy/account/global protection levels.

    Backward compatibility:
    - ``engage(reason)`` / ``release()`` still map to global scope.
    - ``active``/``reason`` keep the original behavior contract.
    """

    def __init__(self) -> None:
        self._global_reason: str | None = None
        self._account_reasons: dict[str, str] = {}
        self._strategy_reasons: dict[tuple[str | None, str], str] = {}

    @property
    def active(self) -> bool:
        return (
            self._global_reason is not None
            or bool(self._account_reasons)
            or bool(self._strategy_reasons)
        )

    @property
    def reason(self) -> str | None:
        block = self.resolve_block()
        return block.reason if block is not None else None

    def engage(
        self,
        reason: str = "manual",
        *,
        scope: KillSwitchScope = KillSwitchScope.GLOBAL,
        account_id: str | None = None,
        strategy_id: str | None = None,
    ) -> None:
        if scope == KillSwitchScope.GLOBAL:
            self._global_reason = reason
            return
        if scope == KillSwitchScope.ACCOUNT:
            if account_id is None:
                raise ValueError("account_id is required for account kill switch")
            self._account_reasons[account_id] = reason
            return
        if strategy_id is None:
            raise ValueError("strategy_id is required for strategy kill switch")
        self._strategy_reasons[(account_id, strategy_id)] = reason

    def release(
        self,
        *,
        scope: KillSwitchScope = KillSwitchScope.GLOBAL,
        account_id: str | None = None,
        strategy_id: str | None = None,
    ) -> None:
        if scope == KillSwitchScope.GLOBAL:
            self._global_reason = None
            return
        if scope == KillSwitchScope.ACCOUNT:
            if account_id is None:
                raise ValueError("account_id is required for account kill switch")
            self._account_reasons.pop(account_id, None)
            return
        if strategy_id is None:
            raise ValueError("strategy_id is required for strategy kill switch")
        self._strategy_reasons.pop((account_id, strategy_id), None)

    def resolve_block(
        self,
        *,
        account_id: str | None = None,
        strategy_id: str | None = None,
    ) -> KillSwitchBlock | None:
        if self._global_reason is not None:
            return KillSwitchBlock(KillSwitchScope.GLOBAL, self._global_reason)

        if account_id is not None:
            account_reason = self._account_reasons.get(account_id)
            if account_reason is not None:
                return KillSwitchBlock(KillSwitchScope.ACCOUNT, account_reason)

        if strategy_id is not None:
            if account_id is not None:
                scoped = self._strategy_reasons.get((account_id, strategy_id))
                if scoped is not None:
                    return KillSwitchBlock(KillSwitchScope.STRATEGY, scoped)
            generic = self._strategy_reasons.get((None, strategy_id))
            if generic is not None:
                return KillSwitchBlock(KillSwitchScope.STRATEGY, generic)

        return None

    def assert_allows_execution(
        self,
        *,
        account_id: str | None = None,
        strategy_id: str | None = None,
    ) -> None:
        block = self.resolve_block(account_id=account_id, strategy_id=strategy_id)
        if block is not None:
            raise RuntimeError(f"kill switch active[{block.scope.value}]: {block.reason}")
