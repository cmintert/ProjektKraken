"""Map Repository Module.

Handles CRUD operations for Map and MapFeature (Marker) entities in the database.
"""

import json
import logging
from typing import List, Optional

from src.core.map import Map
from src.core.marker import MapFeature, Marker
from src.services.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class MapRepository(BaseRepository):
    """Repository for Map and Marker entities.

    Provides specialized methods for creating, reading, updating, and deleting maps and
    markers from the database.

    The hierarchical layer tree is persisted inside the map's ``attributes``
    JSON column under the ``"layers"`` key.
    """

    # Map operations
    def insert_map(self, map_obj: Map) -> None:
        """Insert a new map or update an existing one (Upsert).

        The layer tree (if present) is serialised into the ``attributes``
        JSON column under ``"layers"`` so it survives round-trips.

        Args:
            map_obj: The map domain object to persist.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        # Ensure layers are embedded in attributes for persistence
        attrs = dict(map_obj.attributes) if map_obj.attributes else {}
        if map_obj.layers is not None:
            attrs["layers"] = map_obj.layers.to_dict()
        elif "layers" not in attrs:
            pass  # no layers, nothing to store

        sql = """
            INSERT INTO maps (id, name, image_path, description,
                              attributes, created_at, modified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                image_path=excluded.image_path,
                description=excluded.description,
                attributes=excluded.attributes,
                modified_at=excluded.modified_at;
        """
        with self.transaction() as conn:
            conn.execute(
                sql,
                (
                    map_obj.id,
                    map_obj.name,
                    map_obj.image_path,
                    map_obj.description,
                    self._serialize_json(attrs),
                    map_obj.created_at,
                    map_obj.modified_at,
                ),
            )

    def get_map(self, map_id: str) -> Optional[Map]:
        """Retrieve a single map by its UUID.

        Automatically reconstructs the ``layers`` tree from the
        ``attributes`` JSON if present.

        Args:
            map_id: The unique identifier of the map.

        Returns:
            The Map object if found, else None.

        """
        sql = "SELECT * FROM maps WHERE id = ?"

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql, (map_id,))
        row = cursor.fetchone()

        if row:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            map_obj = Map.from_dict(data)
            # Reconstruct layers from attributes if present
            layers_data = (map_obj.attributes or {}).get("layers")
            if layers_data and map_obj.layers is None:
                from src.core.map import MapLayerNode

                map_obj.layers = MapLayerNode.from_dict(layers_data)
            return map_obj
        return None

    def get_all_maps(self) -> List[Map]:
        """Retrieve all maps from the database.

        Returns:
            List of all Map objects in the database, with layers reconstructed.

        """
        sql = "SELECT * FROM maps ORDER BY name ASC"

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql)
        maps = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            map_obj = Map.from_dict(data)
            layers_data = (map_obj.attributes or {}).get("layers")
            if layers_data and map_obj.layers is None:
                from src.core.map import MapLayerNode

                map_obj.layers = MapLayerNode.from_dict(layers_data)
            maps.append(map_obj)
        return maps

    def delete_map(self, map_id: str) -> None:
        """Delete a map permanently (markers are CASCADE deleted).

        Args:
            map_id: The unique identifier of the map to delete.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        with self.transaction() as conn:
            conn.execute("DELETE FROM maps WHERE id = ?", (map_id,))

    # Marker operations
    def insert_marker(self, marker: Marker) -> None:
        """Insert a new marker/feature or update an existing one (Upsert).

        Args:
            marker: The marker/feature domain object to persist.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        sql = """
            INSERT INTO markers (id, map_id, object_id, object_type, x, y,
                                label, attributes, created_at, modified_at,
                                feature_type, geometry, style)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                x=excluded.x,
                y=excluded.y,
                label=excluded.label,
                attributes=excluded.attributes,
                modified_at=excluded.modified_at,
                feature_type=excluded.feature_type,
                geometry=excluded.geometry,
                style=excluded.style;
        """
        with self.transaction() as conn:
            conn.execute(
                sql,
                (
                    marker.id,
                    marker.map_id,
                    marker.object_id,
                    marker.object_type,
                    marker.x,
                    marker.y,
                    marker.label,
                    self._serialize_json(marker.attributes),
                    marker.created_at,
                    marker.modified_at,
                    marker.feature_type,
                    json.dumps(marker.geometry) if marker.geometry else None,
                    json.dumps(marker.style) if marker.style else None,
                ),
            )

    def get_markers_by_map(self, map_id: str) -> List[Marker]:
        """Retrieve all markers for a specific map.

        Args:
            map_id: The map ID to get markers for.

        Returns:
            List of Marker objects for the specified map.

        """
        sql = "SELECT * FROM markers WHERE map_id = ?"

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql, (map_id,))
        markers = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            markers.append(Marker.from_dict(data))
        return markers

    def get_marker(self, marker_id: str) -> Optional[Marker]:
        """Retrieve a single marker by its UUID.

        Args:
            marker_id: The unique identifier of the marker.

        Returns:
            The Marker object if found, else None.

        """
        sql = "SELECT * FROM markers WHERE id = ?"

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql, (marker_id,))
        row = cursor.fetchone()

        if row:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            return Marker.from_dict(data)
        return None

    def delete_marker(self, marker_id: str) -> None:
        """Delete a marker permanently.

        Args:
            marker_id: The unique identifier of the marker to delete.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        with self.transaction() as conn:
            conn.execute("DELETE FROM markers WHERE id = ?", (marker_id,))
