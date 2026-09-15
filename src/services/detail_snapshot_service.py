"""Assemble Event and Entity editor snapshots without per-relation lookups."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from src.core.entities import Entity
    from src.core.events import Event
    from src.services.db_service import DatabaseService

DetailItem = TypeVar("DetailItem", "Event", "Entity")


@dataclass(frozen=True)
class DetailSnapshot(Generic[DetailItem]):
    """One editor item plus enriched outgoing and incoming relations."""

    item: DetailItem | None
    relations: list[dict]
    incoming_relations: list[dict]


class DetailSnapshotService:
    """Build editor detail payloads on the database-owner thread."""

    def __init__(self, db_service: DatabaseService) -> None:
        """Store the worker-thread-owned database facade."""
        self._db_service = db_service

    def load_event(self, event_id: str) -> DetailSnapshot[Event]:
        """Load an Event and enrich all displayed relation endpoints."""
        event = self._db_service.get_event(event_id)
        if event is None:
            return DetailSnapshot(None, [], [])
        relations = self._db_service.get_relations(event_id)
        incoming = self._db_service.get_incoming_relations(event_id)
        metadata = self._resolve_relation_metadata(relations, incoming)
        for relation in relations:
            target = metadata.get(relation["target_id"])
            relation["target_name"] = target["name"] if target else None
            if target is not None:
                relation["target_kind"] = target["kind"]
        for relation in incoming:
            source = metadata.get(relation["source_id"])
            relation["source_name"] = source["name"] if source else None
        return DetailSnapshot(event, relations, incoming)

    def load_entity(self, entity_id: str) -> DetailSnapshot[Entity]:
        """Load an Entity and enrich all displayed relation endpoint names."""
        entity = self._db_service.get_entity(entity_id)
        if entity is None:
            return DetailSnapshot(None, [], [])
        relations = self._db_service.get_relations(entity_id)
        incoming = self._db_service.get_incoming_relations(entity_id)
        metadata = self._resolve_relation_metadata(relations, incoming)
        for relation in relations:
            target = metadata.get(relation["target_id"])
            relation["target_name"] = target["name"] if target else None
        for relation in incoming:
            source = metadata.get(relation["source_id"])
            relation["source_name"] = source["name"] if source else None
        return DetailSnapshot(entity, relations, incoming)

    def _resolve_relation_metadata(
        self, relations: list[dict], incoming: list[dict]
    ) -> dict:
        endpoint_ids = [relation["target_id"] for relation in relations]
        endpoint_ids.extend(relation["source_id"] for relation in incoming)
        return self._db_service.get_object_display_metadata(endpoint_ids)
