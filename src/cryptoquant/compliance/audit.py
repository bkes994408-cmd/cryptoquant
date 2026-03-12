from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable

from cryptoquant.security import redact_secrets


@dataclass(frozen=True)
class AuditEvent:
    seq: int
    ts_ms: int
    event_type: str
    actor: str
    payload: dict[str, Any]
    prev_hash: str
    event_hash: str


class AuditTrail:
    """In-memory tamper-evident audit ledger.

    Each event hash includes the previous event hash, forming a hash chain.
    Payload is deep-redacted before persistence to avoid secret leakage.
    """

    def __init__(
        self,
        *,
        now_ms_fn: Callable[[], int] | None = None,
        genesis_hash: str = "GENESIS",
    ) -> None:
        self._now_ms_fn = now_ms_fn or (lambda: 0)
        self._genesis_hash = genesis_hash
        self._events: list[AuditEvent] = []

    def append(self, *, event_type: str, actor: str, payload: dict[str, Any]) -> AuditEvent:
        seq = len(self._events) + 1
        ts_ms = self._now_ms_fn()
        prev_hash = self._events[-1].event_hash if self._events else self._genesis_hash
        redacted_payload = redact_secrets(payload)
        event_hash = self._compute_hash(
            seq=seq,
            ts_ms=ts_ms,
            event_type=event_type,
            actor=actor,
            payload=redacted_payload,
            prev_hash=prev_hash,
        )
        event = AuditEvent(
            seq=seq,
            ts_ms=ts_ms,
            event_type=event_type,
            actor=actor,
            payload=redacted_payload,
            prev_hash=prev_hash,
            event_hash=event_hash,
        )
        self._events.append(event)
        return event

    def verify_chain(self) -> bool:
        prev_hash = self._genesis_hash
        for idx, event in enumerate(self._events, start=1):
            if event.seq != idx:
                return False
            if event.prev_hash != prev_hash:
                return False
            expected_hash = self._compute_hash(
                seq=event.seq,
                ts_ms=event.ts_ms,
                event_type=event.event_type,
                actor=event.actor,
                payload=event.payload,
                prev_hash=event.prev_hash,
            )
            if expected_hash != event.event_hash:
                return False
            prev_hash = event.event_hash
        return True

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(event.__dict__, sort_keys=True) for event in self._events)

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)

    @staticmethod
    def _compute_hash(
        *,
        seq: int,
        ts_ms: int,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
        prev_hash: str,
    ) -> str:
        canonical = json.dumps(
            {
                "seq": seq,
                "ts_ms": ts_ms,
                "event_type": event_type,
                "actor": actor,
                "payload": payload,
                "prev_hash": prev_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
