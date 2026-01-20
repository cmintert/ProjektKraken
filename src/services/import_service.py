"""Import Service Module.

Handles importing Entities, Events, and Relations from structured JSON data.
Supports batch operations and single-item imports with recursive relation resolution.
"""

import json
import logging
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from src.core.calendar import CalendarConfig
from src.core.date_parser import DateParser
from src.core.entities import Entity
from src.core.events import Event
from src.services.db_service import DatabaseService
from src.services.import_normalization import normalize_name

logger = logging.getLogger(__name__)


class ImportAction(Enum):
    CREATE = "create"
    UPDATE = "update"
    OVERWRITE = "overwrite"
    SKIP = "skip"
    AMBIGUOUS = "ambiguous"


@dataclass
class ImportResult:
    """Result of an import operation."""

    success: bool
    created_entities: List[str]  # IDs
    created_events: List[str]  # IDs
    created_relations: List[str]  # IDs
    errors: List[str]
    warnings: List[str]
    # New field to track actions taken
    actions: List[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.actions is None:
            self.actions = []


class ImportService:
    """Service for importing data from JSON."""

    def __init__(self, db_service: DatabaseService) -> None:
        """Initialize the ImportService.

        Args:
            db_service: The database service for persistence.
        """
        self._db = db_service
        self._date_parser: Optional[DateParser] = None

    def _get_parser(self) -> Optional[DateParser]:
        """Lazy load parser with active calendar config."""
        if self._date_parser:
            return self._date_parser

        config = self._db.get_active_calendar_config()
        if not config:
            logger.info(
                "No active calendar found in DB. Falling back to default Gregorian."
            )
            config = CalendarConfig.create_default()

        if config:
            self._date_parser = DateParser(config)
            return self._date_parser
        return None

    def _parse_lore_date(
        self, value: Any, result: Optional[ImportResult] = None
    ) -> float:
        """Parse lore date from diverse inputs (float, string, etc)."""
        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            parser = self._get_parser()
            if parser:
                try:
                    parsed = parser.parse_date(value)
                    return parser.calculate_timestamp(parsed)
                except ValueError as e:
                    msg = (
                        f"Failed to parse date string '{value}': {e}. Defaulting to 0.0"
                    )
                    logger.warning(msg)
                    if result:
                        result.warnings.append(msg)
                    return 0.0
            else:
                msg = (
                    f"No active calendar to parse date string '{value}'. "
                    f"Defaulting to 0.0"
                )
                logger.warning(msg)
                if result:
                    result.warnings.append(msg)
                return 0.0

        return 0.0

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

    def import_batch(
        self,
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
    ) -> ImportResult:
        """Imports a batch of data (entities, events, relations).

        Args:
            data: Dictionary containing 'entities', 'events', 'relations'.
            options: Import options (mode, dry_run, source_name, etc.).

        Returns:
            ImportResult object.
        """
        options = options or {}
        # mode = options.get("mode", "update") # defaults within conflict resolver

        result = ImportResult(True, [], [], [], [], [])

        try:
            # Transaction handling:
            # Default: we wrap in transaction for atomic batch.
            # For dry_run, we avoid calling insert methods in the internal helpers.

            with self._db.transaction() as _:
                # ------------------------------------------------------------------
                # PASS 1: Creation (Ignore Relations)
                # ------------------------------------------------------------------
                # 1. Import Entities (Core)
                for entity_data in data.get("entities", []):
                    try:
                        entity_id = self._import_single_entity_internal(
                            entity_data, result, options, skip_relations=True
                        )
                        if entity_id:
                            result.created_entities.append(entity_id)
                    except Exception as e:
                        msg = (
                            f"Failed to create entity '{entity_data.get('name')}': "
                            f"{e}"
                        )
                        result.errors.append(msg)

                # 2. Import Events (Core)
                for event_data in data.get("events", []):
                    try:
                        event_id = self._import_single_event_internal(
                            event_data, result, options, skip_relations=True
                        )
                        if event_id:
                            result.created_events.append(event_id)
                    except Exception as e:
                        result.errors.append(
                            f"Failed to create event '{event_data.get('name')}': {e}"
                        )

                if result.errors:
                    result.success = False
                    # In dry run we might want to see all errors?
                    # Proceeding to allow users to see all potential issues?
                    # Existing logic returns early. Let's keep it safe.
                    return result

                # ------------------------------------------------------------------
                # PASS 2: Linking (Process Nested Relations)
                # ------------------------------------------------------------------
                # 1. Entity Relations
                for entity_data in data.get("entities", []):
                    if "relations" in entity_data:
                        entity_id = entity_data.get(
                            "id"
                        )  # ID might be set/resolved in Pass 1
                        if not entity_id:
                            continue

                        for rel_data in entity_data["relations"]:
                            rel_data["source_id"] = entity_id
                            try:
                                rel_id = self._import_relation_internal(
                                    rel_data, result, options
                                )
                                if rel_id:
                                    result.created_relations.append(rel_id)
                            except Exception as e:
                                msg = (
                                    f"Failed to link entity '{entity_data.get('name')}': "
                                    f"{e}"
                                )
                                result.warnings.append(msg)
                                logger.warning(msg)

                # 2. Event Relations
                for event_data in data.get("events", []):
                    if "relations" in event_data:
                        event_id = event_data.get("id")
                        if not event_id:
                            continue

                        for rel_data in event_data["relations"]:
                            rel_data["source_id"] = event_id
                            try:
                                rel_id = self._import_relation_internal(
                                    rel_data, result
                                )
                                if rel_id:
                                    result.created_relations.append(rel_id)
                            except Exception as e:
                                msg = (
                                    f"Failed to link event '{event_data.get('name')}': "
                                    f"{e}"
                                )
                                result.warnings.append(msg)
                                logger.warning(msg)

                # ------------------------------------------------------------------
                # PASS 3: Top-Level Relations
                # ------------------------------------------------------------------
                for rel_data in data.get("relations", []):
                    try:
                        rel_id = self._import_relation_internal(rel_data, result)
                        if rel_id:
                            result.created_relations.append(rel_id)
                    except Exception as e:
                        msg = f"Failed to import root relation: {e}"
                        result.warnings.append(msg)
                        logger.warning(msg)

        except Exception as e:
            result.success = False
            result.errors.insert(0, f"Fatal import error: {e}")
            logger.error(f"Import failed: {e}")

        return result

    def _import_single_entity_internal(
        self,
        data: Dict[str, Any],
        result: ImportResult,
        options: Optional[Dict[str, Any]] = None,
        skip_relations: bool = False,
    ) -> Optional[str]:
        """Internal helper to import a single entity and its nested relations.

        Args:
            data: Entity data dict.
            result: Result object to append warnings/relations to.
            options: Import options.
            skip_relations: If True, only creates the entity, skipping relations.

        Returns:
            ID of created entity or None.
        """
        options = options or {}
        mode = options.get("mode", "update").lower()
        dry_run = options.get("dry_run", False)
        source_name = options.get("source_name", "import")

        name = data.get("name")
        if not name:
            raise ValueError("Entity missing 'name'")

        # 1. Conflict Resolution / ID Determination
        entity_id = None
        action = ImportAction.CREATE
        match_reason = "new"

        # Check for explicitly provided ID (e.g. self-referential within file)
        provided_id = data.get("id")
        external_id = data.get("external_id")

        existing_entity = None

        # Strategy A: External ID Lookup
        if external_id:
            existing_entity = self._db._entity_repo.find_by_external_id(
                source_name, str(external_id)
            )
            if existing_entity:
                entity_id = existing_entity.id
                match_reason = "external_id_match"

        # Strategy B: Provided ID Lookup (e.g. if re-importing same file with same UUIDs)
        if provided_id:
            existing_entity = self._db.get_entity(provided_id)
            if existing_entity:
                entity_id = provided_id
                match_reason = "uuid_match"

        # Strategy C: Name-based Lookup (if not matched by UUID)
        if not entity_id:
            normalized_search = normalize_name(name)
            # Use Repo optimized search
            candidates = self._db._entity_repo.find_named_entities(str(name).strip())
            # Double check normalization in python to be safe against partial matches if any?
            # Repo does exact case-insensitive match.
            # But let's filter by normalized name to be super strict if needed.
            # "Gandalf" -> "gandalf"
            candidates = [
                c for c in candidates if normalize_name(c.name) == normalized_search
            ]

            if len(candidates) == 1:
                entity_id = candidates[0].id
                existing_entity = candidates[0]
                match_reason = "name_match"
            elif len(candidates) > 1:
                action = ImportAction.AMBIGUOUS
                result.warnings.append(
                    f"Ambiguous '{name}': {len(candidates)} matches. Skipping."
                )
                return None

        # Determine Action
        if entity_id:
            # We found a match. Logic depends on mode.
            # Per-item override?
            item_action = data.get("import_action")
            effective_mode = item_action if item_action else mode

            if effective_mode == "overwrite":
                action = ImportAction.OVERWRITE
            elif effective_mode == "skip":
                action = ImportAction.SKIP
            else:
                action = ImportAction.UPDATE
        else:
            # No match found -> Create
            action = ImportAction.CREATE
            if not provided_id:
                entity_id = str(uuid.uuid4())
            else:
                entity_id = provided_id

        # 2. Execution
        final_id = entity_id

        # Prepare Metadata (Import Sources)
        import_source_entry = {
            "source_name": source_name,
            "external_id": external_id,
            "seen_at": logging.time.time(),
        }

        if action == ImportAction.SKIP:
            pass  # Do nothing

        elif action == ImportAction.CREATE:
            new_entity = Entity(
                id=entity_id,
                name=str(name).strip(),
                type=str(data.get("type", "generic")).strip(),
                description=str(data.get("description", "")).strip(),
                attributes=data.get("attributes", {}),
                created_at=data.get("created_at") or logging.time.time(),
            )
            # Add metadata
            self._update_import_metadata(new_entity, import_source_entry)

            if not dry_run:
                self._db.insert_entity(new_entity)

        elif action == ImportAction.OVERWRITE:
            # Replace fields, preserve ID/Created
            if existing_entity:
                overwritten = Entity(
                    id=entity_id,
                    name=str(name).strip(),
                    type=str(data.get("type", existing_entity.type)).strip(),
                    description=str(data.get("description", "")).strip(),
                    attributes=data.get("attributes", {}),
                    created_at=existing_entity.created_at,  # Preserve creation
                    modified_at=logging.time.time(),
                )
                self._update_import_metadata(overwritten, import_source_entry)

                if not dry_run:
                    self._db.insert_entity(overwritten)  # Upsert

        elif action == ImportAction.UPDATE:
            # Merge fields
            if existing_entity:
                merged = self._merge_entities(existing_entity, data)
                self._update_import_metadata(merged, import_source_entry)

                if not dry_run:
                    self._db.insert_entity(merged)

        # 3. Recording
        result.actions.append(
            {
                "type": "entity",
                "id": final_id,
                "name": name,
                "action": action.value,
                "reason": match_reason,
            }
        )

        # 4. Handle Nested Relations
        # In 2-pass logic, relations are handled in Pass 2.
        # But if we are simulating single-item import via this method...
        if not skip_relations and "relations" in data:
            # This block is creating relations "inline".
            # In 2-pass logic, we usually set skip_relations=True in Pass 1.
            # So this might not be reached in batch import.
            # But for completeness:
            for rel_data in data["relations"]:
                rel_data["source_id"] = final_id
                self._import_relation_internal(rel_data, result, options)

        return final_id

    def _update_import_metadata(self, entity: Entity, entry: Dict[str, Any]) -> None:
        """Updates the _import_sources attribute list."""
        sources = entity.attributes.get("_import_sources", [])
        # Remove existing entry for this source if present
        sources = [s for s in sources if s.get("source_name") != entry["source_name"]]
        sources.append(entry)
        entity.attributes["_import_sources"] = sources

    def _merge_entities(self, existing: Entity, data: Dict[str, Any]) -> Entity:
        """Merges incoming data into existing entity (Last-Write Wins for scalars)."""
        # Name: Update if provided and different?
        # Typically name matches, but casing might differ.
        # Plan: "Incoming non-null value replaces existing value"
        new_name = data.get("name")
        if new_name is not None:
            existing.name = str(new_name).strip()

        new_type = data.get("type")
        if new_type is not None:
            existing.type = str(new_type).strip()

        new_desc = data.get("description")
        if new_desc is not None:
            existing.description = str(new_desc).strip()

        # Attributes: Recursive Merge
        inc_attrs = data.get("attributes", {})
        if inc_attrs:
            # Simple top-level merge for now as per plan "Recursive merge".
            # "Merge non-null fields" is primary.
            for k, v in inc_attrs.items():
                if v is None:
                    existing.attributes.pop(k, None)
                else:
                    existing.attributes[k] = v

        existing.modified_at = logging.time.time()
        return existing

    def _merge_events(self, existing: Event, data: Dict[str, Any]) -> Event:
        """Merges incoming data into existing event (Last-Write Wins for scalars)."""
        new_name = data.get("name")
        if new_name is not None:
            existing.name = str(new_name).strip()

        new_type = data.get("type")
        if new_type is not None:
            existing.type = str(new_type).strip()

        new_desc = data.get("description")
        if new_desc is not None:
            existing.description = str(new_desc).strip()

        new_date = data.get("lore_date")
        if new_date is not None:
            # Already parsed and injected into data before call if updated
            existing.lore_date = float(new_date)

        new_duration = data.get("lore_duration")
        if new_duration is not None:
            existing.lore_duration = float(new_duration)

        inc_attrs = data.get("attributes", {})
        if inc_attrs:
            for k, v in inc_attrs.items():
                if v is None:
                    existing.attributes.pop(k, None)
                else:
                    existing.attributes[k] = v

        existing.modified_at = logging.time.time()
        return existing

    def _import_single_event_internal(
        self,
        data: Dict[str, Any],
        result: ImportResult,
        options: Optional[Dict[str, Any]] = None,
        skip_relations: bool = False,
    ) -> Optional[str]:
        """Internal helper to import a single event and its nested relations.

        Args:
            data: Event data dict.
            result: Result object to append warnings/relations to.
            options: Import options.
            skip_relations: If True, only creates the event, skipping relations.

        Returns:
            ID of created event or None.
        """
        options = options or {}
        mode = options.get("mode", "update").lower()
        dry_run = options.get("dry_run", False)
        source_name = options.get("source_name", "import")

        name = data.get("name")
        if not name:
            raise ValueError("Event missing 'name'")

        # 1. Conflict Resolution / ID Determination
        event_id = None
        action = ImportAction.CREATE
        match_reason = "new"

        provided_id = data.get("id")
        external_id = data.get("external_id")
        existing_event = None

        # Strategy A: External ID Lookup
        if external_id:
            # EventRepo doesn't have find_by_external_id yet?
            # We implemented find_by_external_id in EntityRepository.
            # Skipping for generic Events for now as per plan/time constraints.
            pass

        # Search by name if needed (generic events might not be unique by name?
        # But for dedupe context, we assume name uniqueness for now or skip)
        # Events without dates might be ambiguous.
        # But we align with Entity logic: Unique Name within Type is preferred model?
        # Actually Event names are often not unique. "Battle of X".
        # But we will support name match for now.
        if not event_id:
            # Events in DB are fetched all or we need a repo method?
            # EventRepository doesn't have find_named yet?
            # We can use get_all_events() and filter in python (might be slow)
            # Or add find_named_events to EventRepo.
            # Given we are in TDD and want exhaustive implementation...
            # For now, let's assume no name match for Events unless exact ID match.
            pass
            # but ImportService previously had _resolve_name_to_id using get_events().
            # Let's rely on get_events().
            all_events = self._db.get_events()
            normalized_search = normalize_name(name)
            candidates = [
                e for e in all_events if normalize_name(e.name) == normalized_search
            ]

            if len(candidates) == 1:
                event_id = candidates[0].id
                existing_event = candidates[0]
                match_reason = "name_match"
            elif len(candidates) > 1:
                action = ImportAction.AMBIGUOUS
                result.warnings.append(
                    f"Ambiguous match for event '{name}': found {len(candidates)} candidates. Skipping."
                )
                return None

        # Determine Action
        if event_id:
            item_action = data.get("import_action")
            effective_mode = item_action if item_action else mode

            if effective_mode == "overwrite":
                action = ImportAction.OVERWRITE
            elif effective_mode == "skip":
                action = ImportAction.SKIP
            else:
                action = ImportAction.UPDATE
        else:
            action = ImportAction.CREATE
            if not provided_id:
                event_id = str(uuid.uuid4())
            else:
                event_id = provided_id

        # 2. Execution
        final_id = event_id
        import_source_entry = {
            "source_name": source_name,
            "external_id": external_id,
            "seen_at": logging.time.time(),
        }

        if action == ImportAction.SKIP:
            pass

        elif action == ImportAction.CREATE:
            new_event = Event(
                id=event_id,
                name=str(name).strip(),
                type=str(data.get("type", "generic")).strip(),
                lore_date=self._parse_lore_date(data.get("lore_date"), result),
                lore_duration=float(data.get("lore_duration", 0.0)),
                description=str(data.get("description", "")).strip(),
                attributes=data.get("attributes", {}),
                created_at=data.get("created_at") or logging.time.time(),
            )
            self._update_import_metadata(new_event, import_source_entry)

            if not dry_run:
                self._db.insert_event(new_event)

        elif action == ImportAction.OVERWRITE:
            if existing_event:
                overwritten = Event(
                    id=event_id,
                    name=str(name).strip(),
                    type=str(data.get("type", existing_event.type)).strip(),
                    lore_date=self._parse_lore_date(data.get("lore_date"), result),
                    lore_duration=float(data.get("lore_duration", 0.0)),
                    description=str(data.get("description", "")).strip(),
                    attributes=data.get("attributes", {}),
                    created_at=existing_event.created_at,
                    modified_at=logging.time.time(),
                )
                self._update_import_metadata(overwritten, import_source_entry)

                if not dry_run:
                    self._db.insert_event(overwritten)

        elif action == ImportAction.UPDATE:
            if existing_event:
                # Need _merge_events similar to _merge_entities
                # Or reuse logic? Events have extra fields.
                # Let's duplicate merge logic tailored for Event fields?
                # Or make a generic merge.
                data["lore_date"] = (
                    self._parse_lore_date(data.get("lore_date"), result)
                    if "lore_date" in data
                    else None
                )
                merged = self._merge_events(existing_event, data)
                self._update_import_metadata(merged, import_source_entry)

                if not dry_run:
                    self._db.insert_event(merged)

        # 3. Recording
        result.actions.append(
            {
                "type": "event",
                "id": final_id,
                "name": name,
                "action": action.value,
                "reason": match_reason,
            }
        )

        # 4. Nested Relations
        if not skip_relations and "relations" in data:
            for rel_data in data["relations"]:
                rel_data["source_id"] = final_id
                self._import_relation_internal(rel_data, result, options)

        return final_id

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
