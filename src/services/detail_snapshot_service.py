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
            relation["source_name"] = event.name
            relation["source_event_date"] = event.lore_date
            relation["source_event_attributes"] = event.attributes
            target = metadata.get(relation["target_id"])
            relation["target_name"] = target["name"] if target else None
            if target is not None:
                relation["target_kind"] = target["kind"]
        for relation in incoming:
            relation["target_name"] = event.name
            source = metadata.get(relation["source_id"])
            relation["source_name"] = source["name"] if source else None
        return DetailSnapshot(event, relations, incoming)

    def load_entity(self, entity_id: str) -> DetailSnapshot[Entity]:
        """Load an Entity and enrich all displayed relation endpoint names."""
        entity = self._db_service.get_entity(entity_id)
        if entity is None:
            return DetailSnapshot(None, [], [])
        relations = self._db_service.get_relations(
            entity_id, include_target_events=True
        )
        incoming = self._db_service.get_incoming_relations(entity_id)
        metadata = self._resolve_relation_metadata(relations, incoming)
        for relation in relations:
            relation["source_name"] = entity.name
            target = metadata.get(relation["target_id"])
            relation["target_name"] = target["name"] if target else None
            if target is not None:
                relation["target_kind"] = target["kind"]
        for relation in incoming:
            relation["target_name"] = entity.name
            source = metadata.get(relation["source_id"])
            relation["source_name"] = source["name"] if source else None
            if source is not None:
                relation["source_kind"] = source["kind"]
        if entity.type.casefold() == "character":
            self._enrich_legacy_event_references(relations, incoming)
        return DetailSnapshot(entity, relations, incoming)

    def _enrich_legacy_event_references(
        self, outgoing: list[dict], incoming: list[dict]
    ) -> None:
        candidates = []
        for direction, rows in (("target", outgoing), ("source", incoming)):
            for row in rows:
                if row.get(f"{direction}_kind") == "event":
                    continue
                key = str(row.get("rel_type", "")).strip().casefold()
                identity = (row.get("attributes") or {}).get("event_id")
                if key in {"birth", "death"} and isinstance(identity, str) and identity:
                    candidates.append((identity, row))
        if not candidates:
            return
        events = self._db_service.get_events_by_ids(
            list(dict.fromkeys(identity for identity, _ in candidates))
        )
        for identity, row in candidates:
            if identity in events:
                row["historical_event"] = events[identity].to_dict()

    def _resolve_relation_metadata(
        self, relations: list[dict], incoming: list[dict]
    ) -> dict:
        endpoint_ids = [relation["target_id"] for relation in relations]
        endpoint_ids.extend(relation["source_id"] for relation in incoming)
        return self._db_service.get_object_display_metadata(endpoint_ids)
