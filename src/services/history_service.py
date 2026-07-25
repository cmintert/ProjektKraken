"""History Service Module.

Manages command history persistence for undo/redo across sessions.
Implements Phase 2 of the undo/redo system.
"""

import json
import logging
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from src.services.command_artifact_store import CommandArtifactStore

if TYPE_CHECKING:
    from src.commands.base_command import BaseCommand
    from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


class HistoryService:
    """Manages command history persistence to database.

    Handles:
    - Saving commands to command_history table
    - Loading recent commands on startup
    - Session tracking and management
    - Command serialization/deserialization
    """

    def __init__(self, db_service: "DatabaseService", world_id: str) -> None:
        """Initialize the history service.

        Args:
            db_service: Database service instance
            world_id: Unique identifier for the current world
        """
        self.db_service = db_service
        self.world_id = world_id
        self.session_id = self._generate_session_id()
        self._command_registry: Dict[str, type] = {}

        # Start a new session
        self._start_session()
        logger.info(
            f"HistoryService initialized for world {world_id}, session {self.session_id}"
        )

    def _generate_session_id(self) -> str:
        """Generate a unique session ID.

        Returns:
            str: UUID-based session identifier
        """
        return f"session_{uuid.uuid4().hex[:16]}"

    def _start_session(self) -> None:
        """Record session start in database."""
        try:
            # Get app version
            app_version = "0.10.3"  # TODO: Get from config/package

            with self.db_service.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO edit_sessions (session_id, world_id, started_at, app_version)
                    VALUES (?, ?, ?, ?)
                    """,
                    (self.session_id, self.world_id, time.time(), app_version),
                )
            logger.debug(f"Session {self.session_id} started")
        except Exception as e:
            logger.error(f"Failed to start session: {e}")

    def end_session(self) -> None:
        """Mark session as ended in database."""
        try:
            with self.db_service.transaction() as conn:
                conn.execute(
                    """
                    UPDATE edit_sessions 
                    SET ended_at = ?
                    WHERE session_id = ?
                    """,
                    (time.time(), self.session_id),
                )
            logger.debug(f"Session {self.session_id} ended")
        except Exception as e:
            logger.error(f"Failed to end session: {e}")

    def register_command_type(self, command_type: str, command_class: type) -> None:
        """Register a command class for deserialization.

        Args:
            command_type: String name of the command (e.g., "CreateEventCommand")
            command_class: The command class itself
        """
        self._command_registry[command_type] = command_class
        logger.debug(f"Registered command type: {command_type}")

    def _register_default_commands(self) -> None:
        """Register core commands."""
        # This could be called in __init__, or we let the coordinator handle registration.
        # But for reliability, having them known is good.
        from src.commands.composite_command import CompositeCommand

        self.register_command_type("CompositeCommand", CompositeCommand)

    def save_command(
        self,
        command: "BaseCommand",
        description: Optional[str] = None,
        aggregate_id: Optional[str] = None,
        aggregate_type: Optional[str] = None,
    ) -> None:
        """Save a command to the history table.

        Args:
            command: The command to save
            description: Human-readable description (defaults to command.get_description())
            aggregate_id: ID of the affected object (optional)
            aggregate_type: Type of affected object (optional)
        """
        try:
            if not command.persist_to_history:
                logger.debug(
                    "Skipping session-only command: %s",
                    command.__class__.__name__,
                )
                return
            command_type = command.__class__.__name__
            payload = command.to_dict()
            payload["_command_base"] = command.base_state_dict()
            command_data = json.dumps(payload)

            if description is None:
                description = command.get_description()

            with self.db_service.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO command_history 
                    (world_id, session_id, command_type, command_data, description, 
                     timestamp, aggregate_id, aggregate_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.world_id,
                        self.session_id,
                        command_type,
                        command_data,
                        description,
                        time.time(),
                        aggregate_id,
                        aggregate_type,
                    ),
                )
            logger.debug(f"Saved command: {command_type}")
        except Exception as e:
            logger.error(f"Failed to save command {command.__class__.__name__}: {e}")
            # Don't raise - history save failures shouldn't block user actions

    def load_recent_history(self, limit: int = 100) -> List["BaseCommand"]:
        """Load recent commands from history.

        Args:
            limit: Maximum number of commands to load

        Returns:
            List of reconstructed command objects, ordered oldest to newest
        """
        try:
            if not self.db_service._connection:
                logger.warning("No database connection available")
                return []

            cursor = self.db_service._connection.execute(
                """
                SELECT command_type, command_data, description, timestamp
                FROM command_history
                WHERE world_id = ? AND is_executed = 1
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (self.world_id, limit),
            )

            commands = []
            for row in cursor.fetchall():
                command = self._deserialize_command(
                    row["command_type"], row["command_data"], row["timestamp"]
                )
                if command:
                    commands.append(command)

            # Reverse to get oldest first (chronological order)
            commands.reverse()

            logger.info(f"Loaded {len(commands)} commands from history")
            return commands

        except Exception as e:
            logger.error(f"Failed to load command history: {e}")
            return []

    def set_command_executed(self, command_id: str, is_executed: bool) -> None:
        """Mark the matching persistent command as currently applied or undone."""
        try:
            with self.db_service.transaction() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, command_data
                    FROM command_history
                    WHERE world_id = ?
                    ORDER BY id DESC
                    """,
                    (self.world_id,),
                )
                row_id: Optional[int] = None
                for row in cursor.fetchall():
                    payload = json.loads(row["command_data"])
                    stored_id = str(
                        payload.get("_command_base", {}).get("command_id", "")
                    )
                    if stored_id == command_id:
                        row_id = int(row["id"])
                        break
                if row_id is None:
                    logger.warning(
                        "Persistent command not found while changing state: %s",
                        command_id,
                    )
                    return
                conn.execute(
                    "UPDATE command_history SET is_executed = ? WHERE id = ?",
                    (int(is_executed), row_id),
                )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.error("Invalid persistent history payload: %s", exc)
        except Exception as exc:
            logger.error("Failed to update persistent command state: %s", exc)

    def _deserialize_command(
        self, command_type: str, command_data_json: str, timestamp: float = 0.0
    ) -> Optional["BaseCommand"]:
        """Reconstruct a command from stored data.

        Args:
            command_type: Name of the command class
            command_data_json: JSON string containing command data
            timestamp: The timestamp when the command was originally executed

        Returns:
            Reconstructed command or None if deserialization fails
        """
        try:
            # Get command class from registry
            command_class = self._command_registry.get(command_type)
            if not command_class:
                logger.warning(f"Unknown command type: {command_type}")
                return None

            # Deserialize data
            data = json.loads(command_data_json)

            # Reconstruct command
            command = command_class.from_dict(data)
            base_state = dict(data.get("_command_base", {}))
            if timestamp:
                base_state["timestamp"] = timestamp
            command.restore_base_state(base_state)
            return command

        except Exception as e:
            logger.error(f"Failed to deserialize {command_type}: {e}")
            return None

    def clear_history(self, keep_sessions: int = 5) -> int:
        """Clear old command history.

        Args:
            keep_sessions: Number of recent sessions to keep (default: 5)

        Returns:
            Number of commands deleted
        """
        try:
            removed_payloads: list[str] = []
            with self.db_service.transaction() as conn:
                # Get session IDs to keep
                cursor = conn.execute(
                    """
                    SELECT session_id FROM edit_sessions
                    WHERE world_id = ?
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    (self.world_id, keep_sessions),
                )
                keep_session_ids = [row["session_id"] for row in cursor.fetchall()]

                if not keep_session_ids:
                    return 0

                # Delete commands from old sessions
                placeholders = ",".join("?" * len(keep_session_ids))
                cursor = conn.execute(
                    f"""
                    SELECT command_data FROM command_history
                    WHERE world_id = ? AND session_id NOT IN ({placeholders})
                    """,
                    [self.world_id] + keep_session_ids,
                )
                removed_payloads = [row["command_data"] for row in cursor.fetchall()]
                cursor = conn.execute(
                    f"""
                    DELETE FROM command_history
                    WHERE world_id = ? AND session_id NOT IN ({placeholders})
                    """,
                    [self.world_id] + keep_session_ids,
                )
                deleted_count = cursor.rowcount

                # Delete old sessions
                conn.execute(
                    f"""
                    DELETE FROM edit_sessions
                    WHERE world_id = ? AND session_id NOT IN ({placeholders})
                    """,
                    [self.world_id] + keep_session_ids,
                )

            self._discard_command_artifacts(removed_payloads)
            logger.info(f"Cleared {deleted_count} old commands from history")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
            return 0

    def clear_all_history(self) -> int:
        """Clear ALL command history for this world.

        This is a destructive operation that removes all command history
        and session data. Use with caution.

        Returns:
            Number of commands deleted
        """
        try:
            removed_payloads: list[str] = []
            with self.db_service.transaction() as conn:
                cursor = conn.execute(
                    "SELECT command_data FROM command_history WHERE world_id = ?",
                    (self.world_id,),
                )
                removed_payloads = [row["command_data"] for row in cursor.fetchall()]
                deleted_count = len(removed_payloads)

                # Delete all commands for this world
                conn.execute(
                    "DELETE FROM command_history WHERE world_id = ?", (self.world_id,)
                )

                # Delete all sessions for this world (except current)
                conn.execute(
                    "DELETE FROM edit_sessions WHERE world_id = ? AND session_id != ?",
                    (self.world_id, self.session_id),
                )

            self._discard_command_artifacts(removed_payloads)
            logger.info(f"Cleared ALL history: {deleted_count} commands deleted")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to clear all history: {e}")
            return 0

    def _discard_command_artifacts(self, payloads: list[str]) -> None:
        """Remove persistent file artifacts for history rows that were pruned."""
        world_root = Path(self.db_service.get_db_file_path()).resolve().parent
        store = CommandArtifactStore(world_root)
        for payload in payloads:
            try:
                data = json.loads(payload)
                command_id = str(data.get("_command_base", {}).get("command_id", ""))
                if command_id:
                    store.discard(command_id)
            except (TypeError, ValueError, OSError) as exc:
                logger.warning("Could not prune command artifacts: %s", exc)

    def get_history_stats(self) -> Dict[str, int]:
        """Get statistics about command history.

        Returns:
            Dictionary with stats (command_count, session_count, etc.)
        """
        try:
            stats = {}

            if not self.db_service._connection:
                return stats

            # Count total commands
            cursor = self.db_service._connection.execute(
                "SELECT COUNT(*) as count FROM command_history WHERE world_id = ?",
                (self.world_id,),
            )
            stats["command_count"] = cursor.fetchone()["count"]

            # Count sessions
            cursor = self.db_service._connection.execute(
                "SELECT COUNT(*) as count FROM edit_sessions WHERE world_id = ?",
                (self.world_id,),
            )
            stats["session_count"] = cursor.fetchone()["count"]

            return stats

        except Exception as e:
            logger.error(f"Failed to get history stats: {e}")
            return {}
