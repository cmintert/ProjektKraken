"""
Calendar Repository Module.

Handles CRUD operations for Calendar configuration in the database.
"""

import logging
from typing import List, Optional

from src.core.calendar import CalendarConfig
from src.services.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class CalendarRepository(BaseRepository):
    """
    Repository for Calendar configuration.

    Provides specialized methods for creating, reading, updating,
    and deleting calendar configurations from the database.
    """

    def insert(self, config: CalendarConfig) -> None:
        """
        Insert a new calendar configuration or update an existing one.

        Args:
            config: The calendar configuration to persist.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        sql = """
            INSERT INTO calendar_config 
                (id, name, config_json, is_active, created_at, modified_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                config_json=excluded.config_json,
                is_active=excluded.is_active,
                modified_at=excluded.modified_at;
        """
        with self.transaction() as conn:
            conn.execute(
                sql,
                (
                    config.id,
                    config.name,
                    config.to_json(),
                    1 if config.is_active else 0,
                    config.created_at,
                    config.modified_at,
                ),
            )

    def get(self, config_id: str) -> Optional[CalendarConfig]:
        """
        Retrieve a calendar configuration by its UUID.

        Args:
            config_id: The unique identifier of the configuration.

        Returns:
            The CalendarConfig object if found, else None.
        """
        sql = "SELECT * FROM calendar_config WHERE id = ?"

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql, (config_id,))
        row = cursor.fetchone()

        if row:
            data = dict(row)
            return CalendarConfig.from_json(data["config_json"])
        return None

    def get_all(self) -> List[CalendarConfig]:
        """
        Retrieve all calendar configurations.

        Returns:
            List of all CalendarConfig objects.
        """
        sql = "SELECT * FROM calendar_config ORDER BY name ASC"

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql)
        configs = []
        for row in cursor.fetchall():
            data = dict(row)
            configs.append(CalendarConfig.from_json(data["config_json"]))
        return configs

    def get_active(self) -> Optional[CalendarConfig]:
        """
        Retrieve the active calendar configuration.

        Returns:
            The active CalendarConfig object if found, else None.
        """
        sql = "SELECT * FROM calendar_config WHERE is_active = 1 LIMIT 1"

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql)
        row = cursor.fetchone()

        if row:
            data = dict(row)
            return CalendarConfig.from_json(data["config_json"])
        return None

    def set_active(self, config_id: str) -> None:
        """
        Set a calendar configuration as active (deactivates all others).

        Args:
            config_id: The unique identifier of the configuration to activate.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        with self.transaction() as conn:
            # Deactivate all configurations
            conn.execute("UPDATE calendar_config SET is_active = 0")
            # Activate the specified configuration
            conn.execute(
                "UPDATE calendar_config SET is_active = 1 WHERE id = ?",
                (config_id,),
            )

    def delete(self, config_id: str) -> None:
        """
        Delete a calendar configuration permanently.

        Args:
            config_id: The unique identifier of the configuration to delete.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        with self.transaction() as conn:
            conn.execute("DELETE FROM calendar_config WHERE id = ?", (config_id,))
