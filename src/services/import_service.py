"""Import Service Module.

Handles importing Entities, Events, and Relations from structured JSON data.
Supports batch operations and single-item imports with recursive relation resolution.
"""

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from src.core.entities import Entity
from src.core.events import Event
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """Result of an import operation."""

    success: bool
    created_entities: List[str]  # IDs
    created_events: List[str]  # IDs
    created_relations: List[str]  # IDs
    errors: List[str]
    warnings: List[str]


class ImportService:
    """Service for importing data from JSON."""

    def __init__(self, db_service: DatabaseService) -> None:
        """Initialize the ImportService.

        Args:
            db_service: The database service for persistence.
        """
        self._db = db_service

    @staticmethod
    def parse_only(json_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Parses and validates JSON structure without persisting.

        Args:
            json_data: JSON string or dictionary.

        Returns:
            Dict containing 'entities', 'events', 'relations' lists.

        Raises:
            ValueError: If JSON is invalid or schema is violated.
        """
        if isinstance(json_data, str):
            try:
                data = json.loads(json_data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON: {e}")
        else:
            data = json_data

        # Normalize structure
        result = {"entities": [], "events": [], "relations": []}

        # Case 1: Batch format (root keys 'entities', 'events')
        if "entities" in data or "events" in data:
            result["entities"] = data.get("entities", [])
            result["events"] = data.get("events", [])
            # Relations might be at root or nested; we'll handle root here
            result["relations"] = data.get("relations", [])

        # Case 2: Single Entity
        elif "type" in data and "name" in data and "lore_date" not in data:
            # Likely an entity
            result["entities"] = [data]

        # Case 3: Single Event
        elif "name" in data and ("lore_date" in data or "type" in data):
            # Likely an event (checking lore_date is strong hint)
            result["events"] = [data]

        return result

    def import_batch(self, data: Dict[str, Any]) -> ImportResult:
        """Imports a batch of data (entities, events, relations).

        Args:
            data: Dictionary containing 'entities', 'events', 'relations'.

        Returns:
            ImportResult object.
        """
        result = ImportResult(True, [], [], [], [], [])

        try:
            with self._db.transaction() as _:
                # 1. Import Entities
                for entity_data in data.get("entities", []):
                    try:
                        entity_id = self._import_single_entity_internal(
                            entity_data, result
                        )
                        if entity_id:
                            result.created_entities.append(entity_id)
                    except Exception as e:
                        result.errors.append(
                            f"Failed to import entity '{entity_data.get('name')}': {e}"
                        )

                # 2. Import Events
                for event_data in data.get("events", []):
                    try:
                        event_id = self._import_single_event_internal(
                            event_data, result
                        )
                        if event_id:
                            result.created_events.append(event_id)
                    except Exception as e:
                        result.errors.append(
                            f"Failed to import event '{event_data.get('name')}': {e}"
                        )

                # 3. Import Root Relations (if any)
                for rel_data in data.get("relations", []):
                    try:
                        rel_id = self._import_relation_internal(rel_data, result)
                        if rel_id:
                            result.created_relations.append(rel_id)
                    except Exception as e:
                        result.errors.append(f"Failed to import relation: {e}")

        except Exception as e:
            result.success = False
            result.errors.insert(0, f"Fatal import error: {e}")
            logger.error(f"Import failed: {e}")

        return result

    def _import_single_entity_internal(
        self, data: Dict[str, Any], result: ImportResult
    ) -> Optional[str]:
        """Internal helper to import a single entity and its nested relations.

        Args:
            data: Entity data dict.
            result: Result object to append warnings/relations to.

        Returns:
            ID of created entity or None.
        """
        name = data.get("name")
        if not name:
            raise ValueError("Entity missing 'name'")

        # Handle ID: use provided or generate new
        entity_id = data.get("id", str(uuid.uuid4()))

        # Check if ID exists -> Upsert logic (here we proceed to overwrite/update)
        # Note: Input sanitation for strings
        entity = Entity(
            id=entity_id,
            name=str(name).strip(),
            type=str(data.get("type", "generic")).strip(),
            description=str(data.get("description", "")).strip(),
            attributes=data.get("attributes", {}),
            created_at=data.get("created_at") or logging.time.time(),
        )

        self._db.insert_entity(entity)

        # Handle Nested Relations
        if "relations" in data:
            for rel_data in data["relations"]:
                # Inject source_id as validation expects parsing from external dict
                rel_data["source_id"] = entity_id
                # Logic for name-based lookup happens in relation import
                rel_id = self._import_relation_internal(rel_data, result)
                if rel_id:
                    result.created_relations.append(rel_id)

        return entity_id

    def _import_single_event_internal(
        self, data: Dict[str, Any], result: ImportResult
    ) -> Optional[str]:
        """Internal helper to import a single event and its nested relations.

        Args:
            data: Event data dict.
            result: Result object to append warnings/relations to.

        Returns:
            ID of created event or None.
        """
        name = data.get("name")
        if not name:
            raise ValueError("Event missing 'name'")

        event_id = data.get("id", str(uuid.uuid4()))

        event = Event(
            id=event_id,
            name=str(name).strip(),
            type=str(data.get("type", "generic")).strip(),
            lore_date=float(data.get("lore_date", 0.0)),
            lore_duration=float(data.get("lore_duration", 0.0)),
            description=str(data.get("description", "")).strip(),
            attributes=data.get("attributes", {}),
            created_at=data.get("created_at") or logging.time.time(),
        )

        self._db.insert_event(event)

        # Handle Nested Relations
        if "relations" in data:
            for rel_data in data["relations"]:
                rel_data["source_id"] = event_id
                rel_id = self._import_relation_internal(rel_data, result)
                if rel_id:
                    result.created_relations.append(rel_id)

        return event_id

    def _import_relation_internal(
        self, data: Dict[str, Any], result: ImportResult
    ) -> Optional[str]:
        """Internal helper to import a relation, resolving names to IDs.

        Args:
            data: Relation data dict. Must have source_id/source_name and target_id/target_name.
            result: Result object.

        Returns:
            ID of created relation or None.
        """
        source_id = data.get("source_id")
        target_id = data.get("target_id")

        # Name-based resolution
        if not source_id and data.get("source_name"):
            source_id = self._resolve_name_to_id(data["source_name"], result)

        if not target_id and data.get("target_name"):
            target_id = self._resolve_name_to_id(data["target_name"], result)

        if not source_id or not target_id:
            msg = f"Skipping relation: Unresolved source '{data.get('source_name')}' or target '{data.get('target_name')}'"
            result.warnings.append(msg)
            logger.warning(msg)
            return None

        rel_type = data.get("rel_type", "related")
        attributes = data.get("attributes", {})

        return self._db.insert_relation(source_id, target_id, rel_type, attributes)

    def _resolve_name_to_id(self, name: str, result: ImportResult) -> Optional[str]:
        """Resolves a name to an ID by querying Entities and Events.

        Args:
            name: Name to resolve.
            result: Result object to log ambiguity warnings.

        Returns:
            Resolved ID or None.
        """
        # Search DB for Entities
        entities = (
            self._db.get_entities()
        )  # This might be slow if DB is huge, but fine for now
        matching_entities = [e for e in entities if e.name == name]

        # Search DB for Events
        events = self._db.get_events()
        matching_events = [e for e in events if e.name == name]

        candidates = matching_entities + matching_events  # type: ignore

        if len(candidates) == 0:
            return None

        if len(candidates) > 1:
            result.warnings.append(
                f"Ambiguous name '{name}': Found {len(candidates)} matches. "
                "Using first."
            )
            # For now, simplistic approach: take first.
            # In strict mode we might want to fail.

        return candidates[0].id
