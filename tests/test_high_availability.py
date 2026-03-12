from cryptoquant.ops.high_availability import (
    HealthSignal,
    ReplicaSnapshot,
    ServiceRole,
    evaluate_failover,
    plan_disaster_recovery,
)


def test_failover_when_primary_unreachable_and_standby_healthy() -> None:
    primary = HealthSignal(
        role=ServiceRole.PRIMARY,
        instance_id="node-a",
        heartbeat_age_sec=1.0,
        is_reachable=False,
        lag_sec=0.0,
    )
    standby1 = HealthSignal(
        role=ServiceRole.STANDBY,
        instance_id="node-b",
        heartbeat_age_sec=1.5,
        is_reachable=True,
        lag_sec=2.0,
    )
    standby2 = HealthSignal(
        role=ServiceRole.STANDBY,
        instance_id="node-c",
        heartbeat_age_sec=0.8,
        is_reachable=True,
        lag_sec=1.0,
    )

    decision = evaluate_failover(primary, [standby1, standby2])

    assert decision.should_failover is True
    assert decision.next_primary_instance_id == "node-c"


def test_failover_skipped_when_no_eligible_standby() -> None:
    primary = HealthSignal(
        role=ServiceRole.PRIMARY,
        instance_id="node-a",
        heartbeat_age_sec=15.0,
        is_reachable=True,
        lag_sec=0.0,
    )
    stale_standby = HealthSignal(
        role=ServiceRole.STANDBY,
        instance_id="node-b",
        heartbeat_age_sec=20.0,
        is_reachable=True,
        lag_sec=1.0,
    )

    decision = evaluate_failover(primary, [stale_standby])

    assert decision.should_failover is False
    assert decision.next_primary_instance_id is None


def test_disaster_recovery_selects_highest_generation_then_latest_checkpoint() -> None:
    snapshots = [
        ReplicaSnapshot(
            instance_id="node-a",
            role=ServiceRole.PRIMARY,
            generation=9,
            checkpoint_ts_ms=1_710_000_000_000,
            checksum="aaa",
        ),
        ReplicaSnapshot(
            instance_id="node-b",
            role=ServiceRole.STANDBY,
            generation=10,
            checkpoint_ts_ms=1_709_999_999_999,
            checksum="bbb",
        ),
        ReplicaSnapshot(
            instance_id="node-c",
            role=ServiceRole.STANDBY,
            generation=10,
            checkpoint_ts_ms=1_710_000_000_111,
            checksum="ccc",
        ),
    ]

    plan = plan_disaster_recovery(snapshots, target_instance_id="node-d")

    assert plan.source_instance_id == "node-c"
    assert plan.target_instance_id == "node-d"
    assert plan.replay_required is True


def test_disaster_recovery_raises_when_no_snapshot() -> None:
    try:
        plan_disaster_recovery([], target_instance_id="node-z")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "at least one snapshot" in str(exc)
