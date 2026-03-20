from __future__ import annotations

from cryptoquant.risk import (
    AutoDegradationController,
    DegradationThresholds,
    ExecutionHealthSample,
    KillSwitch,
    ProtectionMode,
    RiskAlert,
)


def _sample(*, latency_ms: float, rejected: bool = False, slippage_bps: float = 0.0) -> ExecutionHealthSample:
    return ExecutionHealthSample(
        latency_ms=latency_ms,
        rejected=rejected,
        slippage_bps=slippage_bps,
    )


def test_auto_degradation_enters_degraded_on_warn_breach() -> None:
    thresholds = DegradationThresholds(
        latency_warn_ms=80,
        latency_critical_ms=200,
        reject_rate_warn=0.2,
        reject_rate_critical=0.5,
        slippage_warn_bps=4,
        slippage_critical_bps=12,
    )
    ctrl = AutoDegradationController(thresholds, window_size=3)

    snap = ctrl.record_sample(_sample(latency_ms=100, rejected=False, slippage_bps=1))

    assert snap.mode == ProtectionMode.DEGRADED
    assert "latency_warn" in snap.reasons


def test_auto_degradation_halts_and_engages_kill_switch_on_critical() -> None:
    alerts: list[RiskAlert] = []
    ks = KillSwitch()
    thresholds = DegradationThresholds(
        latency_warn_ms=80,
        latency_critical_ms=200,
        reject_rate_warn=0.2,
        reject_rate_critical=0.5,
        slippage_warn_bps=4,
        slippage_critical_bps=12,
    )
    ctrl = AutoDegradationController(
        thresholds,
        window_size=2,
        alert_sink=alerts.append,
        kill_switch=ks,
    )

    snap = ctrl.record_sample(_sample(latency_ms=250, rejected=False, slippage_bps=1))

    assert snap.mode == ProtectionMode.HALTED
    assert ks.active is True
    assert ks.reason is not None
    assert "latency_critical" in ks.reason

    codes = [a.code for a in alerts]
    assert "risk.anomaly.latency.critical" in codes
    assert "risk.degradation.mode_changed" in codes


def test_auto_degradation_recovers_to_normal_and_releases_auto_halt() -> None:
    ks = KillSwitch()
    thresholds = DegradationThresholds(
        latency_warn_ms=80,
        latency_critical_ms=200,
        reject_rate_warn=0.2,
        reject_rate_critical=0.5,
        slippage_warn_bps=4,
        slippage_critical_bps=12,
    )
    ctrl = AutoDegradationController(
        thresholds,
        window_size=2,
        recover_healthy_samples=2,
        kill_switch=ks,
    )

    ctrl.record_sample(_sample(latency_ms=250))
    assert ks.active is True

    ctrl.record_sample(_sample(latency_ms=20, rejected=False, slippage_bps=0.5))
    ctrl.record_sample(_sample(latency_ms=25, rejected=False, slippage_bps=0.8))
    ctrl.record_sample(_sample(latency_ms=30, rejected=False, slippage_bps=0.9))
    snap = ctrl.record_sample(_sample(latency_ms=35, rejected=False, slippage_bps=0.7))

    assert snap.mode == ProtectionMode.NORMAL
    assert ks.active is False


def test_auto_degradation_does_not_release_manual_kill_switch() -> None:
    ks = KillSwitch()
    ks.engage("manual emergency")

    thresholds = DegradationThresholds(
        latency_warn_ms=80,
        latency_critical_ms=200,
        reject_rate_warn=0.2,
        reject_rate_critical=0.5,
        slippage_warn_bps=4,
        slippage_critical_bps=12,
    )
    ctrl = AutoDegradationController(
        thresholds,
        window_size=2,
        recover_healthy_samples=1,
        kill_switch=ks,
    )

    ctrl.record_sample(_sample(latency_ms=250))
    ctrl.record_sample(_sample(latency_ms=20))

    assert ks.active is True
    assert ks.reason == "manual emergency"


def test_anomaly_alerts_are_edge_triggered() -> None:
    alerts: list[RiskAlert] = []
    thresholds = DegradationThresholds(
        latency_warn_ms=80,
        latency_critical_ms=200,
        reject_rate_warn=0.2,
        reject_rate_critical=0.5,
        slippage_warn_bps=4,
        slippage_critical_bps=12,
    )
    ctrl = AutoDegradationController(thresholds, window_size=1, alert_sink=alerts.append)

    ctrl.record_sample(_sample(latency_ms=100))
    ctrl.record_sample(_sample(latency_ms=110))
    ctrl.record_sample(_sample(latency_ms=50))
    ctrl.record_sample(_sample(latency_ms=100))

    latency_warn_codes = [a.code for a in alerts if a.code == "risk.anomaly.latency.warn"]
    assert len(latency_warn_codes) == 2
