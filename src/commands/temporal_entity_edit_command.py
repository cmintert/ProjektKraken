"""Atomic, source-aware edits to the entity state visible at a lore time."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from src.commands.base_command import BaseCommand, CommandResult
from src.core.events import Event
from src.core.temporal_resolver import TemporalResolver
from src.core.temporal_state import validate_payload
from src.core.temporal_window import resolve_temporal_window
from src.services.db_service import DatabaseService


class TemporalEntityEditCommand(BaseCommand):
    """Apply field patches to their actual baseline or relation owner."""

    def __init__(
        self,
        entity_id: str,
        lore_time: float,
        expected: dict[str, Any],
        patches: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
        expected_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Capture the viewed state, requested field patches, and metadata."""
        super().__init__()
        self.entity_id = entity_id
        self.lore_time = lore_time
        self.expected = deepcopy(expected)
        self.patches = deepcopy(patches)
        self.metadata = deepcopy(metadata or {})
        self.expected_metadata = deepcopy(expected_metadata or {})
        self._before_entity: dict[str, Any] | None = None
        self._before_relations: dict[str, dict[str, Any]] = {}
        self._created_event_ids: list[str] = []
        self._created_relation_ids: list[str] = []

    def _current_state(self, db_service: DatabaseService) -> dict[str, Any]:
        entity = db_service.get_entity(self.entity_id)
        if entity is None:
            raise ValueError("Entity no longer exists")
        relations = db_service.get_incoming_relations(self.entity_id)
        return TemporalResolver().resolve_entity_state(
            entity, relations, self.lore_time
        ).to_dict()

    def _verify(self, state: dict[str, Any]) -> None:
        for patch in self.patches:
            if patch["field"] == "description":
                value = state["description"]
                previous = self.expected["description"]
                source = state["description_source"]
                old_source = self.expected["description_source"]
            else:
                key = patch["key"]
                value = state["attributes"].get(key, _MISSING)
                previous = self.expected["attributes"].get(key, _MISSING)
                source = state["attribute_sources"].get(key)
                old_source = self.expected["attribute_sources"].get(key)
                if previous is _MISSING and (
                    state.get("absent_attribute_sources", {}).get(key)
                    != self.expected.get("absent_attribute_sources", {}).get(key)
                ):
                    raise ValueError("The attribute's hidden source changed. Reload first.")
            if value != previous or source != old_source:
                raise ValueError(
                    "The visible value or its source changed. Reload before saving."
                )

    def execute(self, db_service: DatabaseService) -> CommandResult:  # noqa: C901
        """Verify the viewed sources and apply all patches in one transaction."""
        try:
            self._verify(self._current_state(db_service))
            entity = db_service.get_entity(self.entity_id)
            if entity is None:
                raise ValueError("Entity no longer exists")
            for key in ("name", "type"):
                if key in self.metadata and getattr(entity, key) != self.expected_metadata.get(key):
                    raise ValueError(f"Entity {key} changed. Reload before saving.")
            for key in self.metadata.get("hidden_attributes", {}):
                if entity.attributes.get(key) != self.expected_metadata.get(key):
                    raise ValueError(f"Entity {key} changed. Reload before saving.")
            self._before_entity = entity.to_dict()
            self._before_relations = {}
            self._created_event_ids = []
            self._created_relation_ids = []
            base_attrs = deepcopy(entity.attributes)
            base_desc = entity.description
            for key, value in self.metadata.get("hidden_attributes", {}).items():
                if key not in {"_tags", "_sheet_layout", "_summary_data"}:
                    raise ValueError(f"Unsupported baseline metadata: {key}")
                if value is None:
                    base_attrs.pop(key, None)
                else:
                    base_attrs[key] = value
            relation_updates: dict[str, dict[str, Any]] = {}
            dated_updates: dict[tuple[str, str], dict[str, Any]] = {}

            for patch in self.patches:
                field = patch["field"]
                field_key = patch.get("key")
                action = patch["action"]
                scope = patch.get("scope", "source")
                owner = (
                    self.expected["description_source"]
                    if field == "description"
                    else self.expected["attribute_sources"].get(field_key)
                )
                if scope == "source":
                    if owner is None:
                        raise ValueError("A new field needs a baseline or dated scope")
                    if owner["kind"] == "baseline":
                        scope = "baseline"
                    else:
                        scope = "relation"
                        relation_id = owner["relation_id"]
                if scope == "baseline":
                    if field == "description":
                        base_desc = patch["value"]
                    else:
                        assert isinstance(field_key, str)
                        if action in {"unset", "remove_override"}:
                            base_attrs.pop(field_key, None)
                        else:
                            base_attrs[field_key] = patch["value"]
                elif scope == "relation":
                    if relation_id not in relation_updates:
                        relation = db_service.get_relation(relation_id)
                        if relation is None or relation["target_id"] != self.entity_id:
                            raise ValueError("The source relation no longer exists")
                        self._before_relations[relation_id] = deepcopy(relation)
                        relation_updates[relation_id] = deepcopy(relation)
                    rel_attrs = relation_updates[relation_id]["attributes"]
                    payload = rel_attrs.setdefault("payload", {})
                    self._apply_payload_patch(payload, patch)
                elif scope == "dated":
                    event_id = patch.get("event_id", "")
                    event_name = patch.get("event_name", "")
                    if not event_id and not event_name.strip():
                        raise ValueError("Choose an event or enter a new event name")
                    bucket = dated_updates.setdefault(
                        (event_id, event_name),
                        {"attributes": {}, "unset_attributes": []},
                    )
                    self._apply_payload_patch(bucket, patch)
                else:
                    raise ValueError(f"Unknown edit scope: {scope}")

            updates = {"name": entity.name, "type": entity.type}
            updates.update(self.metadata)
            if (
                base_desc != entity.description
                or base_attrs != entity.attributes
                or updates["name"] != entity.name
                or updates["type"] != entity.type
            ):
                db_service.insert_entity(
                    replace(
                        entity,
                        name=updates["name"],
                        type=updates["type"],
                        description=base_desc,
                        attributes=base_attrs,
                    )
                )
                if "_tags" in self.metadata.get("hidden_attributes", {}):
                    self._sync_tags(
                        db_service, self.entity_id, set(base_attrs.get("_tags", [])),
                        "entity",
                    )
            for relation in relation_updates.values():
                validate_payload(relation["attributes"]["payload"])
                db_service.update_relation(
                    relation["id"],
                    relation["target_id"],
                    relation["rel_type"],
                    relation["attributes"],
                )
            for (event_id, event_name), payload in dated_updates.items():
                validate_payload(payload)
                if event_id:
                    event = db_service.get_event(event_id)
                    if event is None or event.lore_date != self.lore_time:
                        raise ValueError("Selected event is not at the viewed time")
                else:
                    event = Event(name=event_name.strip(), lore_date=self.lore_time)
                    db_service.insert_event(event)
                    self._created_event_ids.append(event.id)
                competing = db_service.get_incoming_relations(self.entity_id)
                same_time = [
                    r["attributes"].get("modified_at", 0.0)
                    for r in competing
                    if resolve_temporal_window(
                        r["attributes"], r.get("source_event_date")
                    ).start == self.lore_time
                ]
                modified_at = max([0.0, *same_time]) + 1.0
                relation_id = db_service.insert_relation(
                    event.id,
                    self.entity_id,
                    "involved",
                    {
                        "valid_from_event": True,
                        "priority": "manual",
                        "modified_at": modified_at,
                        "payload": payload,
                    },
                )
                self._created_relation_ids.append(relation_id)
            self._is_executed = True
            return CommandResult(
                success=True,
                message="Entity state updated.",
                command_name="TemporalEntityEditCommand",
                data={"entity_id": self.entity_id},
            )
        except (KeyError, TypeError, ValueError) as exc:
            return CommandResult(
                success=False,
                message=str(exc),
                command_name="TemporalEntityEditCommand",
            )

    @staticmethod
    def _apply_payload_patch(
        payload: dict[str, Any], patch: dict[str, Any]
    ) -> None:
        """Change only the requested payload field."""
        if patch["field"] == "description":
            if patch["action"] == "remove_override":
                payload.pop("description", None)
            else:
                payload["description"] = patch["value"]
            return
        key = patch["key"]
        attrs = payload.setdefault("attributes", {})
        unsets = payload.setdefault("unset_attributes", [])
        if patch["action"] == "set":
            attrs[key] = patch["value"]
            if key in unsets:
                unsets.remove(key)
        else:
            attrs.pop(key, None)
            if patch["action"] == "unset" and key not in unsets:
                unsets.append(key)

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the exact records captured before execution."""
        if not self._is_executed or self._before_entity is None:
            return
        for relation_id in reversed(self._created_relation_ids):
            db_service.delete_relation(relation_id)
        for event_id in reversed(self._created_event_ids):
            db_service.delete_event(event_id)
        for relation in self._before_relations.values():
            db_service.update_relation(
                relation["id"],
                relation["target_id"],
                relation["rel_type"],
                relation["attributes"],
            )
        from src.core.entities import Entity

        db_service.insert_entity(Entity.from_dict(self._before_entity))
        self._sync_tags(
            db_service,
            self.entity_id,
            set(self._before_entity.get("attributes", {}).get("_tags", [])),
            "entity",
        )
        self._is_executed = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize intent and undo snapshots."""
        return {
            "entity_id": self.entity_id,
            "lore_time": self.lore_time,
            "expected": self.expected,
            "patches": self.patches,
            "metadata": self.metadata,
            "expected_metadata": self.expected_metadata,
            "before_entity": self._before_entity,
            "before_relations": self._before_relations,
            "created_event_ids": self._created_event_ids,
            "created_relation_ids": self._created_relation_ids,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemporalEntityEditCommand:
        """Restore a command from history."""
        command = cls(
            data["entity_id"],
            data["lore_time"],
            data["expected"],
            data["patches"],
            data.get("metadata"),
            data.get("expected_metadata"),
        )
        command._before_entity = data.get("before_entity")
        command._before_relations = data.get("before_relations", {})
        command._created_event_ids = data.get("created_event_ids", [])
        command._created_relation_ids = data.get("created_relation_ids", [])
        command._is_executed = data.get("is_executed", False)
        return command


_MISSING = object()
