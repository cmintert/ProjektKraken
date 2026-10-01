"""Serializable failures for migration and startup recovery."""

from typing import Any


class MigrationError(RuntimeError):
    """Block writable startup while retaining actionable recovery details."""

    def __init__(
        self,
        message: str,
        *,
        step: str = "inspection",
        database_path: str = "",
        recovery_path: str | None = None,
        record_ids: list[str] | None = None,
    ) -> None:
        """Capture the failing step and any verified recovery location."""
        super().__init__(message)
        self.step = step
        self.database_path = database_path
        self.recovery_path = recovery_path
        self.record_ids = record_ids or []

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot suitable for queued Qt signals and CLI callers."""
        return {
            "success": False,
            "message": str(self),
            "failed_step": self.step,
            "database_path": self.database_path,
            "recovery_path": self.recovery_path,
            "record_ids": list(self.record_ids),
        }
