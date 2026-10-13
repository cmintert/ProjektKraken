"""Authored relation policy and preparation over worker-owned repositories.

Connections and transactions belong to callers. Generated wikilink mentions use
their existing repository reconciliation path, outside this authored capability.
"""

import logging
import sqlite3
import time
import uuid
from collections.abc import Callable
from typing import Any

from src.core.entities import Entity
from src.core.events import Event
from src.services.repositories.entity_repository import EntityRepository
from src.services.repositories.event_repository import EventRepository
from src.services.repositories.relation_repository import RelationRepository

logger = logging.getLogger(__name__)


class AuthoredRelationService:
    """Validate forward mutations and restore exact relation snapshots.

    Lookup callbacks preserve the facade's lazy connection behavior and injected
    repositories. This service neither opens connections nor begins transactions.
    Repository writes join an outer transaction, or own a standalone transaction.
    """

    def __init__(
        self,
        relation_repo: RelationRepository,
        get_entity: Callable[[str], Entity | None],
        get_event: Callable[[str], Event | None],
    ) -> None:
        """Accept only the persistence and endpoint lookup capabilities needed.

        Args:
            relation_repo: Mutation repository on the caller's connection.
            get_entity: Entity lookup on the same connection and owning thread.
            get_event: Event lookup on the same connection and owning thread.
        """
        self._relation_repo = relation_repo
        self._get_entity = get_entity
        self._get_event = get_event

    @classmethod
    def from_connection(
        cls, connection: sqlite3.Connection
    ) -> "AuthoredRelationService":
        """Bind repositories to an already-open, owning-thread connection.

        Commands obtain this connection through ``require_connection()``. Nothing
        is opened or committed here; the caller retains lifecycle ownership.

        Args:
            connection: Already-open SQLite connection owned by the calling thread.

        Returns:
            Authored relation service bound to that connection's repositories.
        """
        return cls(
            RelationRepository(connection),
            EntityRepository(connection).get,
            EventRepository(connection).get,
        )

    @staticmethod
    def is_system_managed_type(rel_type: str) -> bool:
        """Identify relation types whose mutations belong to generated wikilinks."""
        return rel_type == "mentions"

    @classmethod
    def require_authored_type(
        cls,
        rel_type: str,
        *,
        message: str = "The 'mentions' relation type is system-managed by wikilinks.",
    ) -> None:
        """Reject a generated relation type, retaining caller-specific feedback."""
        if cls.is_system_managed_type(rel_type):
            raise ValueError(message)

    def validate_endpoint(self, endpoint_id: str, role: str | None = None) -> None:
        """Require a canonical UUID identifying an existing entity or event.

        UUID errors precede lookup callbacks. Omitting the role retains commands'
        historical missing-endpoint wording; facade adapters supply their role.

        Args:
            endpoint_id: Existing entity or event's canonical UUID.
            role: Optional source/target label for compatibility error messages.

        Raises:
            ValueError: If the ID is noncanonical or the endpoint is missing.
        """
        label = role or "endpoint"
        try:
            canonical = str(uuid.UUID(endpoint_id))
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError(
                f"Relation {label} must be a canonical UUID: {endpoint_id!r}"
            ) from exc
        if endpoint_id != canonical:
            raise ValueError(
                f"Relation {label} must be a canonical UUID: {endpoint_id!r}"
            )
        if (
            self._get_entity(endpoint_id) is None
            and self._get_event(endpoint_id) is None
        ):
            prefix = f"{role} endpoint" if role else "endpoint"
            raise ValueError(f"Relation {prefix} does not exist: {endpoint_id}")

    def create(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        attributes: dict[str, Any] | None = None,
        *,
        relation_id: str | None = None,
        created_at: float | None = None,
    ) -> str:
        """Create a relation, retaining supplied history identity and timestamp.

        Endpoint IDs are rejected rather than normalized. Supplied relation IDs
        and timestamps are used verbatim; their allocation belongs to the caller.

        Args:
            source_id: Existing source entity/event UUID.
            target_id: Existing target entity/event UUID.
            rel_type: Authored relation type, excluding generated mentions.
            attributes: Authored metadata, defaulting to an empty dictionary.
            relation_id: Recorded identity, or None to allocate a new UUID.
            created_at: Recorded timestamp, or None to use the current time.

        Returns:
            The persisted relation ID.

        Raises:
            ValueError: If the type or endpoints violate authored policy.
            sqlite3.Error: If persistence fails.
        """
        self.require_authored_type(rel_type)
        self.validate_endpoint(source_id, "source")
        self.validate_endpoint(target_id, "target")
        if relation_id is None:
            relation_id = str(uuid.uuid4())
        if created_at is None:
            created_at = time.time()
        self._relation_repo.insert(
            relation_id,
            source_id,
            target_id,
            rel_type,
            attributes if attributes is not None else {},
            created_at,
        )
        logger.info(
            "DB: Inserted relation %s: %s -> %s (%s)",
            relation_id,
            source_id,
            target_id,
            rel_type,
        )
        return relation_id

    def update(
        self,
        relation_id: str,
        target_id: str,
        rel_type: str,
        attributes: dict[str, Any] | None = None,
        *,
        source_id: str | None = None,
    ) -> None:
        """Update authored state, validating every supplied replacement endpoint.

        Identity and creation time are untouched. The facade's existing no-op for
        a missing relation is retained by the repository update.

        Args:
            relation_id: Identity of the relation to update.
            target_id: Existing replacement target entity/event UUID.
            rel_type: Authored replacement type, excluding generated mentions.
            attributes: Complete replacement metadata, defaulting to empty.
            source_id: Optional existing replacement source entity/event UUID.

        Raises:
            ValueError: If the type or supplied endpoints violate authored policy.
            sqlite3.Error: If persistence fails.
        """
        self.require_authored_type(rel_type)
        if source_id is not None:
            self.validate_endpoint(source_id, "source")
        self.validate_endpoint(target_id, "target")
        self._relation_repo.update(
            relation_id,
            rel_type,
            attributes if attributes is not None else {},
            target_id=target_id,
            source_id=source_id,
        )

    def restore_snapshot(self, relation_id: str, snapshot: dict[str, Any]) -> None:
        """Restore captured state for undo without forward-policy validation.

        Legacy endpoint IDs are preserved exactly. SQLite still enforces endpoint
        existence; failure propagates to the caller's transaction for rollback.

        Args:
            relation_id: Identity of the existing relation to restore.
            snapshot: Captured source_id, target_id, rel_type and attributes.

        Raises:
            sqlite3.Error: If persistence or an endpoint-existence constraint fails.
        """
        self._relation_repo.update(
            relation_id,
            snapshot["rel_type"],
            snapshot["attributes"],
            target_id=snapshot["target_id"],
            source_id=snapshot["source_id"],
        )
