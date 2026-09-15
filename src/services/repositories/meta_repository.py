"""Meta Repository Module.

Handles CRUD operations for the system_meta table, including current time,
timeline grouping configuration, graph lexicon, and generic name lookups.
"""

import json
import logging
from collections.abc import Iterable
from typing import Any, Dict, List, Literal, Optional, TypedDict

from src.services.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)

_OBJECT_METADATA_CHUNK_SIZE = 900


class ObjectDisplayMetadata(TypedDict):
    """Display metadata shared by Event and Entity references."""

    name: str | None
    kind: Literal["entity", "event"]


class MetaRepository(BaseRepository):
    """Repository for system_meta table operations.

    Provides methods for managing world-level metadata such as current time,
    timeline grouping configuration, and graph visual lexicon settings,
    as well as a generic helper for resolving object names.
    """

    def get_current_time(self) -> Optional[float]:
        """Retrieves the current time in the world from system_meta.

        Returns:
            Optional[float]: The current time in lore_date units, or None if not set.

        """
        sql = "SELECT value FROM system_meta WHERE key = 'current_time'"

        cursor = self._require_connection().execute(sql)
        row = cursor.fetchone()

        if row and row["value"]:
            try:
                return float(row["value"])
            except (ValueError, TypeError):
                logger.warning(f"Invalid current_time value: {row['value']}")
                return None
        return None

    def set_current_time(self, current_time: float) -> None:
        """Sets the current time in the world and persists it to system_meta.

        Args:
            current_time: The current time in lore_date units.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        sql = """
            INSERT INTO system_meta (key, value)
            VALUES ('current_time', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """
        with self.transaction() as conn:
            conn.execute(sql, (str(current_time),))
        logger.debug(f"Set current_time to {current_time}")

    def set_timeline_grouping_config(
        self,
        tag_order: List[str],
        mode: str = "DUPLICATE",
    ) -> None:
        """Stores timeline grouping configuration.

        Args:
            tag_order: List of tag names defining groups and their order.
            mode: Grouping mode - "DUPLICATE" or "FIRST_MATCH".

        Raises:
            ValueError: If mode is invalid.

        """
        if mode not in ("DUPLICATE", "FIRST_MATCH"):
            raise ValueError(f"Invalid mode: {mode}. Must be DUPLICATE or FIRST_MATCH")

        config = {"tag_order": tag_order, "mode": mode}
        config_json = json.dumps(config)

        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO system_meta (key, value)
                VALUES ('timeline_grouping_config', ?)
                """,
                (config_json,),
            )

        logger.debug(
            f"Saved timeline grouping config: {len(tag_order)} tags, mode={mode}"
        )

    def get_timeline_grouping_config(self) -> Optional[Dict[str, Any]]:
        """Retrieves timeline grouping configuration.

        Returns:
            Optional[Dict[str, Any]]: Config dict with tag_order and mode,
                                      or None if not set.

        """
        cursor = self._require_connection().execute(
            "SELECT value FROM system_meta WHERE key = 'timeline_grouping_config'"
        )
        result = cursor.fetchone()

        if result and result["value"]:
            return json.loads(result["value"])
        return None

    def clear_timeline_grouping_config(self) -> None:
        """Clears timeline grouping configuration."""
        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM system_meta WHERE key = 'timeline_grouping_config'"
            )

        logger.debug("Cleared timeline grouping config")

    def get_graph_lexicon(self) -> Optional[Dict[str, Any]]:
        """Retrieves the graph visual lexicon configuration.

        The lexicon defines custom visual styles (icon, color, shape) for
        entity types and (color, width, dashes) for relation types.

        Returns:
            Optional[Dict[str, Any]]: Lexicon config dict with 'nodes' and
                'edges' keys, or None if not configured.

        """
        cursor = self._require_connection().execute(
            "SELECT value FROM system_meta WHERE key = 'graph_lexicon_config'"
        )
        result = cursor.fetchone()

        if result and result["value"]:
            try:
                return json.loads(result["value"])
            except (json.JSONDecodeError, TypeError):
                logger.warning("Invalid graph_lexicon_config value in system_meta")
                return None
        return None

    def set_graph_lexicon(self, data: Dict[str, Any]) -> None:
        """Stores the graph visual lexicon configuration.

        Serializes the configuration dictionary to JSON and persists it in
        the system_meta table under the key 'graph_lexicon_config'.

        Args:
            data: Lexicon configuration dictionary. Expected structure:
                {
                    "nodes": {
                        "<entity_type>": {"color": str, "shape": str,
                                          "icon_id": str}
                    },
                    "edges": {
                        "<rel_type>": {"color": str, "width": int,
                                       "dashes": bool}
                    }
                }

        """
        config_json = json.dumps(data)

        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO system_meta (key, value)
                VALUES ('graph_lexicon_config', ?)
                """,
                (config_json,),
            )

        logger.debug(f"Saved graph lexicon config: {len(config_json)} bytes")

    def get_world_theme(self) -> Optional[str]:
        """Retrieves the saved theme name for this world from system_meta.

        Returns:
            Optional[str]: The theme name string, or None if not set.

        """
        cursor = self._require_connection().execute(
            "SELECT value FROM system_meta WHERE key = 'world_theme'"
        )
        row = cursor.fetchone()
        if row and row["value"]:
            return str(row["value"])
        return None

    def set_world_theme(self, theme_name: str) -> None:
        """Persists the active theme name for this world in system_meta.

        Args:
            theme_name: The theme key to store (e.g. 'dark_mode').

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO system_meta (key, value)
                VALUES ('world_theme', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (theme_name,),
            )
        logger.debug(f"Saved world_theme: {theme_name}")

    def get_ai_generation_preferences(self) -> Optional[Dict[str, Any]]:
        """Retrieve portable AI creative preferences for this world."""
        cursor = self._require_connection().execute(
            "SELECT value FROM system_meta WHERE key = 'ai_generation_preferences'"
        )
        row = cursor.fetchone()
        if not row or not row["value"]:
            return None
        try:
            value = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid ai_generation_preferences in system_meta")
            return None
        return value if isinstance(value, dict) else None

    def set_ai_generation_preferences(self, data: Dict[str, Any]) -> None:
        """Persist versioned AI creative preferences in the world database."""
        config_json = json.dumps(data, ensure_ascii=False)
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO system_meta (key, value)
                VALUES ('ai_generation_preferences', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (config_json,),
            )
        logger.debug("Saved portable AI generation preferences")

    def get_name(self, object_id: str) -> Optional[str]:
        """Retrieves the name of an entity or event by its ID.

        Args:
            object_id: The ID to resolve.

        Returns:
            Optional[str]: The name if found, else None.

        """
        # Try Entity
        connection = self._require_connection()
        cursor = connection.execute(
            "SELECT name FROM entities WHERE id = ?", (object_id,)
        )
        row = cursor.fetchone()
        if row:
            return row["name"]

        # Try Event
        cursor = connection.execute(
            "SELECT name FROM events WHERE id = ?", (object_id,)
        )
        row = cursor.fetchone()
        if row:
            return row["name"]

        return None

    def get_object_display_metadata(
        self, object_ids: Iterable[str]
    ) -> dict[str, ObjectDisplayMetadata]:
        """Resolve names and kinds for Event or Entity IDs in bounded batches.

        Entity rows intentionally take precedence if malformed data contains the
        same identifier in both object tables, matching :meth:`get_name`.

        Args:
            object_ids: Object IDs to resolve. Duplicates are ignored.

        Returns:
            Metadata keyed by IDs that currently exist. Missing IDs are omitted.

        """
        unique_ids = list(dict.fromkeys(object_ids))
        if not unique_ids:
            return {}

        connection = self._require_connection()
        result: dict[str, ObjectDisplayMetadata] = {}
        for start in range(0, len(unique_ids), _OBJECT_METADATA_CHUNK_SIZE):
            chunk = unique_ids[start : start + _OBJECT_METADATA_CHUNK_SIZE]
            placeholders = ",".join("?" for _object_id in chunk)
            entity_rows = connection.execute(
                f"SELECT id, name FROM entities WHERE id IN ({placeholders})",
                chunk,
            ).fetchall()
            for row in entity_rows:
                result[row["id"]] = {"name": row["name"], "kind": "entity"}

            event_rows = connection.execute(
                f"SELECT id, name FROM events WHERE id IN ({placeholders})",
                chunk,
            ).fetchall()
            for row in event_rows:
                result.setdefault(
                    row["id"], {"name": row["name"], "kind": "event"}
                )
        return result
