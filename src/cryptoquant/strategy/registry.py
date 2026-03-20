from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Mapping


class StrategyLifecycle(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class StrategyVersionStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    schema_version: str
    description: str = ""


@dataclass(frozen=True)
class FeatureDependency:
    feature_name: str
    required: bool = True
    min_schema_version: str | None = None


@dataclass(frozen=True)
class StrategyVersion:
    version: str
    status: StrategyVersionStatus
    created_at: datetime
    changelog: str = ""
    artifact_uri: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyRegistration:
    strategy_id: str
    name: str
    lifecycle: StrategyLifecycle
    dependencies: tuple[FeatureDependency, ...]
    versions: tuple[StrategyVersion, ...]
    active_version: str | None
    created_at: datetime


@dataclass(frozen=True)
class RegimeStrategyBinding:
    regime: str
    strategy_id: str
    strategy_name: str
    version: str
    weight: float


class StrategyRegistry:
    """Central registry for strategy identity, lifecycle, dependencies, versions, and regime-aware routing."""

    _LIFECYCLE_TRANSITIONS: dict[StrategyLifecycle, set[StrategyLifecycle]] = {
        StrategyLifecycle.DRAFT: {StrategyLifecycle.ACTIVE, StrategyLifecycle.ARCHIVED},
        StrategyLifecycle.ACTIVE: {StrategyLifecycle.PAUSED, StrategyLifecycle.DEPRECATED},
        StrategyLifecycle.PAUSED: {StrategyLifecycle.ACTIVE, StrategyLifecycle.DEPRECATED},
        StrategyLifecycle.DEPRECATED: {StrategyLifecycle.ARCHIVED},
        StrategyLifecycle.ARCHIVED: set(),
    }

    def __init__(self) -> None:
        self._strategies: dict[str, _StrategyState] = {}
        self._features: dict[str, FeatureSpec] = {}
        self._regime_routes: dict[str, dict[str, _RegimeRouteState]] = {}
        self._id_sequence = 0

    def register_strategy(self, *, name: str, strategy_id: str | None = None) -> str:
        candidate_id = strategy_id or self._next_strategy_id(name)
        if not candidate_id.startswith("strat-"):
            raise ValueError("strategy_id must start with 'strat-'")
        if candidate_id in self._strategies:
            raise ValueError(f"strategy already registered: {candidate_id}")

        now = datetime.now(timezone.utc)
        self._strategies[candidate_id] = _StrategyState(
            strategy_id=candidate_id,
            name=name,
            lifecycle=StrategyLifecycle.DRAFT,
            created_at=now,
        )
        return candidate_id

    def register_feature(self, *, name: str, schema_version: str, description: str = "") -> FeatureSpec:
        spec = FeatureSpec(name=name, schema_version=schema_version, description=description)
        self._features[name] = spec
        return spec

    def add_feature_dependency(
        self,
        strategy_id: str,
        *,
        feature_name: str,
        required: bool = True,
        min_schema_version: str | None = None,
    ) -> None:
        state = self._get_strategy(strategy_id)
        feature = self._features.get(feature_name)
        if feature is None:
            raise ValueError(f"feature is not registered: {feature_name}")
        if min_schema_version is not None and _version_lt(feature.schema_version, min_schema_version):
            raise ValueError(
                f"feature {feature_name} schema_version={feature.schema_version} does not meet min={min_schema_version}"
            )

        dep = FeatureDependency(
            feature_name=feature_name,
            required=required,
            min_schema_version=min_schema_version,
        )
        state.dependencies[feature_name] = dep

    def set_lifecycle(self, strategy_id: str, lifecycle: StrategyLifecycle) -> None:
        state = self._get_strategy(strategy_id)
        current = state.lifecycle
        if lifecycle == current:
            return
        allowed = self._LIFECYCLE_TRANSITIONS[current]
        if lifecycle not in allowed:
            raise ValueError(f"invalid lifecycle transition: {current.value} -> {lifecycle.value}")

        if lifecycle == StrategyLifecycle.ACTIVE and state.active_version is None:
            raise ValueError("cannot activate strategy without an active version")

        state.lifecycle = lifecycle

    def add_version(
        self,
        strategy_id: str,
        *,
        version: str,
        changelog: str = "",
        artifact_uri: str | None = None,
        metadata: Mapping[str, str] | None = None,
        activate: bool = False,
    ) -> StrategyVersion:
        state = self._get_strategy(strategy_id)
        if version in state.versions:
            raise ValueError(f"version already exists: {strategy_id}@{version}")

        created = datetime.now(timezone.utc)
        record = StrategyVersion(
            version=version,
            status=StrategyVersionStatus.ACTIVE if activate else StrategyVersionStatus.DRAFT,
            created_at=created,
            changelog=changelog,
            artifact_uri=artifact_uri,
            metadata=dict(metadata or {}),
        )
        state.versions[version] = record

        if activate:
            self.activate_version(strategy_id, version)

        return state.versions[version]

    def activate_version(self, strategy_id: str, version: str) -> None:
        state = self._get_strategy(strategy_id)
        if version not in state.versions:
            raise ValueError(f"version not found: {strategy_id}@{version}")

        for existing, record in list(state.versions.items()):
            if record.status == StrategyVersionStatus.ACTIVE and existing != version:
                state.versions[existing] = StrategyVersion(
                    version=record.version,
                    status=StrategyVersionStatus.DEPRECATED,
                    created_at=record.created_at,
                    changelog=record.changelog,
                    artifact_uri=record.artifact_uri,
                    metadata=record.metadata,
                )

        selected = state.versions[version]
        state.versions[version] = StrategyVersion(
            version=selected.version,
            status=StrategyVersionStatus.ACTIVE,
            created_at=selected.created_at,
            changelog=selected.changelog,
            artifact_uri=selected.artifact_uri,
            metadata=selected.metadata,
        )
        state.active_version = version

    def deprecate_version(self, strategy_id: str, version: str) -> None:
        state = self._get_strategy(strategy_id)
        record = state.versions.get(version)
        if record is None:
            raise ValueError(f"version not found: {strategy_id}@{version}")

        state.versions[version] = StrategyVersion(
            version=record.version,
            status=StrategyVersionStatus.DEPRECATED,
            created_at=record.created_at,
            changelog=record.changelog,
            artifact_uri=record.artifact_uri,
            metadata=record.metadata,
        )
        if state.active_version == version:
            state.active_version = None

    def configure_regime_route(
        self,
        regime: str,
        *,
        strategy_id: str,
        weight: float = 1.0,
        version: str | None = None,
    ) -> None:
        if not regime.strip():
            raise ValueError("regime must not be empty")
        if not isfinite(weight) or weight <= 0.0:
            raise ValueError("weight must be finite and > 0")

        state = self._get_strategy(strategy_id)
        if version is not None and version not in state.versions:
            raise ValueError(f"version not found: {strategy_id}@{version}")

        routes = self._regime_routes.setdefault(regime, {})
        routes[strategy_id] = _RegimeRouteState(weight=float(weight), version=version)

    def clear_regime_route(self, regime: str, *, strategy_id: str | None = None) -> None:
        if strategy_id is None:
            self._regime_routes.pop(regime, None)
            return

        routes = self._regime_routes.get(regime)
        if routes is None:
            return
        routes.pop(strategy_id, None)
        if not routes:
            self._regime_routes.pop(regime, None)

    def resolve_regime_bindings(self, regime: str, *, only_active: bool = True) -> tuple[RegimeStrategyBinding, ...]:
        configured = self._regime_routes.get(regime, {})
        if not configured:
            return ()

        selected: list[RegimeStrategyBinding] = []
        for strategy_id, route in sorted(configured.items()):
            state = self._get_strategy(strategy_id)
            if only_active and state.lifecycle != StrategyLifecycle.ACTIVE:
                continue

            version = route.version or state.active_version
            if version is None:
                continue

            record = state.versions.get(version)
            if record is None:
                continue
            if only_active and record.status != StrategyVersionStatus.ACTIVE:
                continue

            selected.append(
                RegimeStrategyBinding(
                    regime=regime,
                    strategy_id=strategy_id,
                    strategy_name=state.name,
                    version=version,
                    weight=route.weight,
                )
            )

        if not selected:
            return ()

        total_weight = sum(item.weight for item in selected)
        if total_weight <= 0.0:
            return ()

        normalized = tuple(
            RegimeStrategyBinding(
                regime=item.regime,
                strategy_id=item.strategy_id,
                strategy_name=item.strategy_name,
                version=item.version,
                weight=item.weight / total_weight,
            )
            for item in selected
        )
        return normalized

    def get(self, strategy_id: str) -> StrategyRegistration:
        state = self._get_strategy(strategy_id)
        versions = tuple(sorted(state.versions.values(), key=lambda x: _version_sort_key(x.version)))
        return StrategyRegistration(
            strategy_id=state.strategy_id,
            name=state.name,
            lifecycle=state.lifecycle,
            dependencies=tuple(sorted(state.dependencies.values(), key=lambda x: x.feature_name)),
            versions=versions,
            active_version=state.active_version,
            created_at=state.created_at,
        )

    def list_strategies(self) -> list[StrategyRegistration]:
        return [self.get(strategy_id) for strategy_id in sorted(self._strategies.keys())]

    def _next_strategy_id(self, name: str) -> str:
        slug = "-".join(name.lower().split())
        self._id_sequence += 1
        return f"strat-{slug}-{self._id_sequence:04d}"

    def _get_strategy(self, strategy_id: str) -> _StrategyState:
        state = self._strategies.get(strategy_id)
        if state is None:
            raise ValueError(f"strategy not found: {strategy_id}")
        return state


@dataclass
class _StrategyState:
    strategy_id: str
    name: str
    lifecycle: StrategyLifecycle
    created_at: datetime
    dependencies: dict[str, FeatureDependency] = field(default_factory=dict)
    versions: dict[str, StrategyVersion] = field(default_factory=dict)
    active_version: str | None = None


@dataclass
class _RegimeRouteState:
    weight: float
    version: str | None = None


def _version_sort_key(value: str) -> tuple[tuple[int, str], ...]:
    out: list[tuple[int, str]] = []
    for part in value.split("."):
        if part.isdigit():
            out.append((0, str(int(part))))
        else:
            out.append((1, part))
    return tuple(out)


def _version_lt(left: str, right: str) -> bool:
    lparts = left.split(".")
    rparts = right.split(".")
    max_len = max(len(lparts), len(rparts))
    for idx in range(max_len):
        left_part = lparts[idx] if idx < len(lparts) else "0"
        right_part = rparts[idx] if idx < len(rparts) else "0"
        if left_part == right_part:
            continue
        if left_part.isdigit() and right_part.isdigit():
            return int(left_part) < int(right_part)
        return left_part < right_part
    return False
