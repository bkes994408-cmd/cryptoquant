from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .kill_switch import KillSwitch, KillSwitchScope
from .manager import RiskAlert, RiskAlertLevel


class ProtectionMode(str, Enum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    HALTED = "HALTED"


@dataclass(frozen=True)
class DegradationThresholds:
    latency_warn_ms: float
    latency_critical_ms: float
    reject_rate_warn: float
    reject_rate_critical: float
    slippage_warn_bps: float
    slippage_critical_bps: float

    def __post_init__(self) -> None:
        if not (0 <= self.reject_rate_warn <= 1 and 0 <= self.reject_rate_critical <= 1):
            raise ValueError("reject_rate thresholds must be in [0, 1]")
        if self.latency_warn_ms <= 0 or self.latency_critical_ms <= 0:
            raise ValueError("latency thresholds must be positive")
        if self.slippage_warn_bps < 0 or self.slippage_critical_bps < 0:
            raise ValueError("slippage thresholds must be non-negative")
        if self.latency_warn_ms >= self.latency_critical_ms:
            raise ValueError("latency_warn_ms must be < latency_critical_ms")
        if self.reject_rate_warn >= self.reject_rate_critical:
            raise ValueError("reject_rate_warn must be < reject_rate_critical")
        if self.slippage_warn_bps >= self.slippage_critical_bps:
            raise ValueError("slippage_warn_bps must be < slippage_critical_bps")


@dataclass(frozen=True)
class DegradationSnapshot:
    mode: ProtectionMode
    avg_latency_ms: float
    reject_rate: float
    avg_slippage_bps: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ExecutionHealthSample:
    latency_ms: float
    rejected: bool
    slippage_bps: float


class AutoDegradationController:
    """Auto-degrade based on execution health and optionally drive kill switch.

    Heuristics:
    - Any critical breach => HALTED + global kill switch engage
    - Any warn breach (without critical) => DEGRADED
    - Recover to NORMAL after N consecutive healthy windows
    """

    def __init__(
        self,
        thresholds: DegradationThresholds,
        *,
        window_size: int = 20,
        recover_healthy_samples: int = 3,
        alert_sink: Callable[[RiskAlert], None] | None = None,
        kill_switch: KillSwitch | None = None,
    ) -> None:
        if window_size <= 0:
            raise ValueError("window_size must be positive")
        if recover_healthy_samples <= 0:
            raise ValueError("recover_healthy_samples must be positive")
        self._thresholds = thresholds
        self._window: deque[ExecutionHealthSample] = deque(maxlen=window_size)
        self._recover_healthy_samples = recover_healthy_samples
        self._alert_sink = alert_sink
        self._kill_switch = kill_switch

        self._mode = ProtectionMode.NORMAL
        self._healthy_count = 0
        self._active_anomalies: set[str] = set()
        self._auto_halt_reason: str | None = None

    @property
    def mode(self) -> ProtectionMode:
        return self._mode

    def record_sample(self, sample: ExecutionHealthSample) -> DegradationSnapshot:
        if sample.latency_ms < 0:
            raise ValueError("latency_ms must be >= 0")
        if sample.slippage_bps < 0:
            raise ValueError("slippage_bps must be >= 0")

        self._window.append(sample)
        avg_latency_ms = sum(s.latency_ms for s in self._window) / len(self._window)
        reject_rate = sum(1 for s in self._window if s.rejected) / len(self._window)
        avg_slippage_bps = sum(s.slippage_bps for s in self._window) / len(self._window)

        critical_reasons = self._collect_metric_breaches(
            severity="critical",
            avg_latency_ms=avg_latency_ms,
            reject_rate=reject_rate,
            avg_slippage_bps=avg_slippage_bps,
        )
        warn_reasons = self._collect_metric_breaches(
            severity="warn",
            avg_latency_ms=avg_latency_ms,
            reject_rate=reject_rate,
            avg_slippage_bps=avg_slippage_bps,
        )

        self._emit_anomaly_alerts(critical_reasons=critical_reasons, warn_reasons=warn_reasons)

        previous_mode = self._mode
        reasons: tuple[str, ...]
        if critical_reasons:
            reasons = tuple(sorted(critical_reasons))
            self._mode = ProtectionMode.HALTED
            self._healthy_count = 0
            reason = f"auto-degradation critical: {', '.join(reasons)}"
            if self._kill_switch is not None:
                active_global = self._kill_switch.resolve_block()
                if active_global is None:
                    self._kill_switch.engage(reason, scope=KillSwitchScope.GLOBAL)
                    self._auto_halt_reason = reason
                elif active_global.scope == KillSwitchScope.GLOBAL and active_global.reason == reason:
                    self._auto_halt_reason = reason
            else:
                self._auto_halt_reason = reason
        elif warn_reasons:
            reasons = tuple(sorted(warn_reasons))
            self._mode = ProtectionMode.DEGRADED
            self._healthy_count = 0
        else:
            reasons = tuple()
            self._healthy_count += 1
            if self._healthy_count >= self._recover_healthy_samples:
                self._mode = ProtectionMode.NORMAL
                if self._kill_switch is not None and self._auto_halt_reason is not None:
                    current = self._kill_switch.resolve_block()
                    if current is not None and current.reason == self._auto_halt_reason:
                        self._kill_switch.release(scope=KillSwitchScope.GLOBAL)
                    self._auto_halt_reason = None

        if previous_mode != self._mode:
            self._emit_alert(
                RiskAlert(
                    level=self._mode_alert_level(self._mode),
                    code="risk.degradation.mode_changed",
                    message=(
                        f"mode={self._mode.value} prev={previous_mode.value} "
                        f"reasons={', '.join(reasons) if reasons else 'healthy'}"
                    ),
                )
            )

        return DegradationSnapshot(
            mode=self._mode,
            avg_latency_ms=avg_latency_ms,
            reject_rate=reject_rate,
            avg_slippage_bps=avg_slippage_bps,
            reasons=reasons,
        )

    def _collect_metric_breaches(
        self,
        *,
        severity: str,
        avg_latency_ms: float,
        reject_rate: float,
        avg_slippage_bps: float,
    ) -> set[str]:
        if severity == "critical":
            latency_threshold = self._thresholds.latency_critical_ms
            reject_threshold = self._thresholds.reject_rate_critical
            slippage_threshold = self._thresholds.slippage_critical_bps
        else:
            latency_threshold = self._thresholds.latency_warn_ms
            reject_threshold = self._thresholds.reject_rate_warn
            slippage_threshold = self._thresholds.slippage_warn_bps

        reasons: set[str] = set()
        if avg_latency_ms >= latency_threshold:
            reasons.add(f"latency_{severity}")
        if reject_rate >= reject_threshold:
            reasons.add(f"reject_rate_{severity}")
        if avg_slippage_bps >= slippage_threshold:
            reasons.add(f"slippage_{severity}")
        return reasons

    def _emit_anomaly_alerts(self, *, critical_reasons: set[str], warn_reasons: set[str]) -> None:
        active = critical_reasons | warn_reasons
        new_reasons = active - self._active_anomalies
        self._active_anomalies = active

        for reason in sorted(new_reasons):
            metric, severity = reason.rsplit("_", 1)
            level = RiskAlertLevel.ERROR if severity == "critical" else RiskAlertLevel.WARN
            self._emit_alert(
                RiskAlert(
                    level=level,
                    code=f"risk.anomaly.{metric}.{severity}",
                    message=f"execution anomaly detected: {metric} ({severity})",
                )
            )

    def _emit_alert(self, alert: RiskAlert) -> None:
        if self._alert_sink is not None:
            self._alert_sink(alert)

    @staticmethod
    def _mode_alert_level(mode: ProtectionMode) -> RiskAlertLevel:
        if mode == ProtectionMode.HALTED:
            return RiskAlertLevel.ERROR
        if mode == ProtectionMode.DEGRADED:
            return RiskAlertLevel.WARN
        return RiskAlertLevel.INFO
