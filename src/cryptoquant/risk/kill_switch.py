from __future__ import annotations


class KillSwitch:
    """Simple in-memory kill switch to block new executions immediately."""

    def __init__(self) -> None:
        self._active = False
        self._reason: str | None = None

    @property
    def active(self) -> bool:
        return self._active

    @property
    def reason(self) -> str | None:
        return self._reason

    def engage(self, reason: str = "manual") -> None:
        self._active = True
        self._reason = reason

    def release(self) -> None:
        self._active = False
        self._reason = None

    def assert_allows_execution(self) -> None:
        if self._active:
            raise RuntimeError(f"kill switch active: {self._reason}")
