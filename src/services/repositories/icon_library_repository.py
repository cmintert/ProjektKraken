"""World-owned custom icon metadata and reference queries."""

from __future__ import annotations

import json
from typing import Any

from src.core.marker_appearance import MARKER_ICON_ID_ATTRIBUTE
from src.services.repositories.base_repository import BaseRepository


class IconLibraryRepository(BaseRepository):
    """Persist icon metadata without extending the database facade."""

    def read(self) -> dict[str, Any]:
        """Read versioned metadata, rejecting corrupt or unsupported documents."""
        row = (
            self._require_connection()
            .execute("SELECT value FROM system_meta WHERE key = 'custom_icon_library'")
            .fetchone()
        )
        if row is None:
            return {}
        payload = json.loads(row[0])
        if (
            not isinstance(payload, dict)
            or payload.get("version") != 1
            or not isinstance(payload.get("icons"), dict)
            or any(not isinstance(v, dict) for v in payload["icons"].values())
        ):
            raise ValueError("Unsupported or invalid custom icon library metadata")
        return dict(payload["icons"])

    def write(self, icons: dict[str, Any]) -> None:
        """Write metadata within the caller's command transaction."""
        self._require_connection().execute(
            "INSERT OR REPLACE INTO system_meta (key, value) VALUES (?, ?)",
            ("custom_icon_library", json.dumps({"version": 1, "icons": icons})),
        )

    def remove_document(self) -> None:
        """Restore the original absence of metadata on undo."""
        self._require_connection().execute(
            "DELETE FROM system_meta WHERE key = 'custom_icon_library'"
        )

    def exists(self) -> bool:
        """Return whether the metadata document is persisted."""
        return (
            self._require_connection()
            .execute("SELECT 1 FROM system_meta WHERE key = 'custom_icon_library'")
            .fetchone()
            is not None
        )

    def markers(self, icon_id: str) -> list[dict[str, Any]]:
        """Find references across all maps, including hidden markers."""
        result = []
        for row in self._require_connection().execute(
            "SELECT m.id, m.map_id, m.label, m.attributes, p.name AS map_name, "
            "p.image_path FROM markers m JOIN maps p ON p.id = m.map_id"
        ):
            item = dict(row)
            attributes = json.loads(item["attributes"] or "{}")
            if not isinstance(attributes, dict):
                raise ValueError("Invalid marker attributes prevent reference checking")
            if attributes.get(MARKER_ICON_ID_ATTRIBUTE) == icon_id:
                item["attributes"] = attributes
                result.append(item)
        return result

    def usage(self, icon_id: str) -> list[str]:
        """Return creator-facing persisted usage descriptions."""
        uses = [
            f"Marker {m['label'] or m['id']} on {m['map_name']}"
            for m in self.markers(icon_id)
        ]
        row = (
            self._require_connection()
            .execute("SELECT value FROM system_meta WHERE key = 'graph_lexicon_config'")
            .fetchone()
        )
        if row is not None:
            lexicon = json.loads(row[0])
            if not isinstance(lexicon, dict) or not isinstance(
                lexicon.get("nodes", {}), dict
            ):
                raise ValueError("Invalid Visual Lexicon prevents reference checking")
            for name, style in lexicon.get("nodes", {}).items():
                if not isinstance(style, dict):
                    raise ValueError("Invalid Visual Lexicon node")
                if style.get("icon_id") == icon_id:
                    uses.append(f"Visual Lexicon: {name}")
        return uses

    def set_marker_fields(
        self, marker_id: str, fields: dict[str, Any], missing: list[str] | None = None
    ) -> None:
        """Patch only icon-dependent fields, preserving unrelated attributes."""
        conn = self._require_connection()
        row = conn.execute(
            "SELECT attributes FROM markers WHERE id = ?", (marker_id,)
        ).fetchone()
        if row is None:
            raise ValueError("An affected marker no longer exists")
        attributes = json.loads(row[0] or "{}")
        for key, value in fields.items():
            if key in (missing or []):
                attributes.pop(key, None)
            else:
                attributes[key] = value
        conn.execute(
            "UPDATE markers SET attributes = ? WHERE id = ?",
            (json.dumps(attributes), marker_id),
        )
