from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatasetVersion:
    dataset: str
    schema_version: str
    row_count: int
    checksum_sha256: str
    min_ts: str | None
    max_ts: str | None
    created_at: str


def build_dataset_version(
    *,
    dataset: str,
    schema_version: str,
    rows: list[dict[str, Any]],
) -> DatasetVersion:
    payload_rows = [_stable_row_payload(row) for row in rows]
    payload = json.dumps(payload_rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    timestamps = [row["ts"] for row in rows if isinstance(row.get("ts"), datetime)]
    min_ts = min(timestamps).isoformat() if timestamps else None
    max_ts = max(timestamps).isoformat() if timestamps else None

    return DatasetVersion(
        dataset=dataset,
        schema_version=schema_version,
        row_count=len(rows),
        checksum_sha256=checksum,
        min_ts=min_ts,
        max_ts=max_ts,
        created_at=datetime.now(tz=timezone.utc).isoformat(),
    )


class DatasetVersionStore:
    """File-based manifest store for initial dataset versioning."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def save(self, version: DatasetVersion) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        filename = f"{_safe_name(version.dataset)}-{version.checksum_sha256[:12]}.json"
        target = self._root / filename
        target.write_text(json.dumps(asdict(version), ensure_ascii=False, indent=2), encoding="utf-8")
        return target


def _safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name)


def _stable_row_payload(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out
