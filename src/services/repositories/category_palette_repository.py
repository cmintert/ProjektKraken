"""Portable derived presentation preferences, owned by the database thread."""

import json

from src.core.category_palette import assign_categories
from src.services.repositories.base_repository import BaseRepository

PALETTE_KEY = "explorer_category_palette_v1"


class CategoryPaletteRepository(BaseRepository):
    """Keep type colors independent of filtered GUI snapshots and lore undo."""

    def ensure_assignments(self, *, read_only: bool = False) -> dict[str, int]:
        """Atomically retain saved slots and allocate every actual world type."""
        connection = self._require_connection()
        with self.transaction():
            row = connection.execute(
                "SELECT value FROM system_meta WHERE key = ?", (PALETTE_KEY,)
            ).fetchone()
            payload = json.loads(row[0]) if row else {"schema": 1, "assignments": {}}
            if not isinstance(payload, dict) or payload.get("schema") != 1:
                raise ValueError("Unsupported type color settings")
            saved = payload["assignments"]
            if not isinstance(saved, dict):
                raise ValueError("Invalid type color settings")
            categories = connection.execute(
                "SELECT DISTINCT 'entity', type FROM entities "
                "UNION SELECT DISTINCT 'event', type FROM events"
            ).fetchall()
            assignments = assign_categories(saved, categories)
            if not read_only and assignments != saved:
                connection.execute(
                    "INSERT INTO system_meta(key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (
                        PALETTE_KEY,
                        json.dumps({"schema": 1, "assignments": assignments}),
                    ),
                )
        return assignments
