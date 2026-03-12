from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ServiceRole(StrEnum):
    PRIMARY = "primary"
    STANDBY = "standby"


@dataclass(frozen=True)
class HealthSignal:
    role: ServiceRole
    instance_id: str
    heartbeat_age_sec: float
    is_reachable: bool
    lag_sec: float


@dataclass(frozen=True)
class ReplicaSnapshot:
    instance_id: str
    role: ServiceRole
    generation: int
    checkpoint_ts_ms: int
    checksum: str


@dataclass(frozen=True)
class FailoverDecision:
    should_failover: bool
    next_primary_instance_id: str | None
    reason: str


@dataclass(frozen=True)
class RecoveryPlan:
    source_instance_id: str
    checkpoint_ts_ms: int
    target_instance_id: str
    replay_required: bool
    reason: str


def evaluate_failover(
    primary: HealthSignal,
    standbys: list[HealthSignal],
    *,
    max_heartbeat_age_sec: float = 10.0,
    max_replication_lag_sec: float = 5.0,
) -> FailoverDecision:
    """Evaluate whether to fail over from primary to best standby.

    Rule:
    1) Primary is considered unhealthy if unreachable or heartbeat is stale.
    2) Candidate standbys must be reachable, heartbeat fresh, and lag below threshold.
    3) Pick candidate with minimum lag then minimum heartbeat age.
    """

    primary_unhealthy = (not primary.is_reachable) or (
        primary.heartbeat_age_sec > max_heartbeat_age_sec
    )
    if not primary_unhealthy:
        return FailoverDecision(False, None, "primary healthy")

    candidates = [
        s
        for s in standbys
        if s.is_reachable
        and s.heartbeat_age_sec <= max_heartbeat_age_sec
        and s.lag_sec <= max_replication_lag_sec
    ]
    if not candidates:
        return FailoverDecision(
            False,
            None,
            "primary unhealthy but no standby satisfies heartbeat/lag thresholds",
        )

    best = sorted(candidates, key=lambda s: (s.lag_sec, s.heartbeat_age_sec))[0]
    return FailoverDecision(
        True,
        best.instance_id,
        f"primary unhealthy; promote standby={best.instance_id}",
    )


def plan_disaster_recovery(
    snapshots: list[ReplicaSnapshot],
    *,
    target_instance_id: str,
) -> RecoveryPlan:
    """Generate deterministic DR plan from replicated checkpoints.

    Snapshot selection priority:
    1) highest generation
    2) latest checkpoint timestamp
    3) lexicographically smallest instance id (stable tie-break)

    replay_required is true when target instance is not source instance.
    """

    if not snapshots:
        raise ValueError("at least one snapshot is required")

    source = sorted(
        snapshots,
        key=lambda s: (-s.generation, -s.checkpoint_ts_ms, s.instance_id),
    )[0]
    replay_required = source.instance_id != target_instance_id
    reason = (
        f"selected snapshot from {source.instance_id} "
        f"(generation={source.generation}, checkpoint={source.checkpoint_ts_ms})"
    )
    return RecoveryPlan(
        source_instance_id=source.instance_id,
        checkpoint_ts_ms=source.checkpoint_ts_ms,
        target_instance_id=target_instance_id,
        replay_required=replay_required,
        reason=reason,
    )
