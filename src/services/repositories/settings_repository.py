"""Narrow access to Settings Center metadata, without a new database schema."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from src.services.repositories.base_repository import BaseRepository

META_KEYS = {
    "world.theme": "world_theme",
    "world.ai": "ai_generation_preferences",
    "world.grouping": "timeline_grouping_config",
    "world.lexicon": "graph_lexicon_config",
}
POLICY_KEY = "world_preferences"


class SettingsRepository(BaseRepository):
    """Read and restore exact metadata rows for undoable world configuration."""

    def raw(self, key: str) -> str | None:
        """Return the exact persisted representation, including absence."""
        row = (
            self._require_connection()
            .execute("SELECT value FROM system_meta WHERE key = ?", (key,))
            .fetchone()
        )
        return row[0] if row else None

    def restore(self, key: str, value: str | None) -> None:
        """Restore a row within the caller's transaction."""
        if key not in {*META_KEYS.values(), POLICY_KEY}:
            raise ValueError("Unknown settings metadata")
        connection = self._require_connection()
        if value is None:
            connection.execute("DELETE FROM system_meta WHERE key = ?", (key,))
        else:
            connection.execute(
                "INSERT INTO system_meta(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def policy(self) -> dict[str, Any]:
        """Return the world's policy; unknown fields survive future writes."""
        raw = self.raw(POLICY_KEY)
        data = json.loads(raw) if raw is not None else {}
        if not isinstance(data, dict):
            raise ValueError("Invalid world preferences")
        return deepcopy(data)

    def ensure_policy(self, seed: dict[str, Any]) -> None:
        """Import legacy values once; absence is not a reset instruction."""
        if self.raw(POLICY_KEY) is not None:
            return
        with self.transaction():
            self.restore(
                POLICY_KEY,
                json.dumps(
                    {
                        "version": 1,
                        "auto_relations": bool(seed.get("auto_relations", False)),
                        "excluded_attributes": list(
                            seed.get("excluded_attributes", [])
                        ),
                        "migration": "legacy-local-v1"
                        if seed
                        else "product-defaults-v1",
                        "index_requires_rebuild": False,
                    }
                ),
            )
