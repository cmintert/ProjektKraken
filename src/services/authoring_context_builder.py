"""Deterministic authoring-context projections for Events and Entities."""

from __future__ import annotations

import json
import logging
from collections import deque
from pathlib import Path
from typing import Any, Callable

from src.core.authoring_context import (
    ContextAttachment,
    ContextAttribute,
    ContextCoAppearance,
    ContextEvent,
    ContextEventAppearance,
    ContextItem,
    ContextMapAppearance,
    ContextRelation,
    ContextSharedAssociation,
    ContextTag,
    EntityAuthoringContext,
    EventAuthoringContext,
    SpatialAuthoringContext,
    TemporalKind,
)
from src.core.entities import Entity
from src.core.events import Event
from src.core.map import Map
from src.core.temporal_window import TemporalWindowKind, resolve_temporal_window
from src.services.db_service import DatabaseService
from src.services.map_nesting_service import MapNestingService
from src.services.spatial_context_builder import SpatialContextBuilder

logger = logging.getLogger(__name__)

PARTICIPANT_REL_TYPES = frozenset({"involved", "participated_in", "member_of"})
MAX_PARTICIPANTS = 12
MAX_LOCATIONS = 6
MAX_MENTIONS = 12
MAX_CONCURRENT_EVENTS = 12
MAX_SIDE_EVENTS = 2
MAX_DIRECT_RELATIONS = 12
MAX_NEIGHBORHOOD_RELATIONS = 24
MAX_RELATION_HOPS = 2
MAX_SPATIAL_ANCHORS = 3
MAX_ENTITY_ATTRIBUTES = 24
MAX_ENTITY_EVENTS = 24
MAX_ENTITY_MAPS = 12
MAX_ENTITY_TAGS = 24
MAX_LINKED_REFERENCES = 24
MAX_CO_APPEARANCES = 12
MAX_CO_APPEARANCE_EVENTS = 3
MAX_SHARED_ASSOCIATIONS = 12
MAX_ATTACHMENTS = 6
MAX_ATTRIBUTE_VALUE_CHARS = 400
MAX_ATTRIBUTE_TOTAL_CHARS = 2400
MAX_ENTITY_CONTEXT_CHARS = 12000


class AuthoringContextBuilder:
    """Build bounded factual projections around Events and Entities."""

    def __init__(
        self,
        db: DatabaseService,
        *,
        world_root: Path | None = None,
    ) -> None:
        """Initialize the builder with one connected database service."""
        self._db = db
        self._world_root = world_root

    def build_event_context(
        self,
        event_id: str,
        *,
        context_date: float | None = None,
        active_map_id: str | None = None,
    ) -> EventAuthoringContext | None:
        """Return deterministic persisted context around an Event."""
        event = self._db.get_event(event_id)
        if event is None:
            return None
        effective_date = event.lore_date if context_date is None else context_date

        item_cache: dict[str, ContextItem | None] = {}
        event_cache: dict[str, Event | None] = {event.id: event}

        def resolve_item(item_id: str) -> ContextItem | None:
            if item_id in item_cache:
                return item_cache[item_id]
            entity = self._db.get_entity(item_id)
            result: ContextItem | None
            if entity is not None:
                result = ContextItem(entity.id, "entity", entity.name)
            else:
                related_event = self._db.get_event(item_id)
                event_cache[item_id] = related_event
                result = (
                    ContextItem(related_event.id, "event", related_event.name)
                    if related_event is not None
                    else None
                )
            item_cache[item_id] = result
            if result is None:
                logger.warning("Skipping unresolved authoring-context item %s", item_id)
            return result

        relations = sorted(
            self._db.get_relations_for_item(event_id), key=self._relation_key
        )
        participants: list[ContextItem] = []
        locations: list[ContextItem] = []
        mentions: list[ContextItem] = []
        direct: list[ContextRelation] = []

        for relation in relations:
            rel_type = str(relation.get("rel_type", ""))
            is_outgoing = relation.get("source_id") == event_id
            if is_outgoing and rel_type in PARTICIPANT_REL_TYPES:
                self._append_item(participants, resolve_item(str(relation["target_id"])))
                continue
            if is_outgoing and rel_type == "located_at":
                self._append_item(locations, resolve_item(str(relation["target_id"])))
                continue
            if rel_type == "mentions":
                if is_outgoing:
                    self._append_item(mentions, resolve_item(str(relation["target_id"])))
                continue
            resolved = self._resolve_relation(
                relation,
                hop=0,
                context_date=effective_date,
                root_event=event,
                resolve_item=resolve_item,
                event_cache=event_cache,
            )
            if resolved is not None:
                direct.append(resolved)

        participants.sort(key=self._item_key)
        locations.sort(key=self._item_key)
        mentions.sort(key=self._item_key)
        direct.sort(key=self._context_relation_key)

        omitted: dict[str, int] = {}
        participants = self._limit(
            "participants", participants, MAX_PARTICIPANTS, omitted
        )
        locations = self._limit("locations", locations, MAX_LOCATIONS, omitted)
        mentions = self._limit("mentions", mentions, MAX_MENTIONS, omitted)
        direct = self._limit(
            "direct_relations", direct, MAX_DIRECT_RELATIONS, omitted
        )

        previous, concurrent, following = self._event_neighbors(
            event_id, effective_date, omitted
        )
        neighborhood = self._traverse_relations(
            seeds=participants + locations,
            root_event=event,
            context_date=effective_date,
            resolve_item=resolve_item,
            event_cache=event_cache,
        )
        neighborhood = self._limit(
            "neighborhood_relations",
            neighborhood,
            MAX_NEIGHBORHOOD_RELATIONS,
            omitted,
        )
        spatial = self._resolve_spatial(
            event=event,
            locations=locations,
            context_date=effective_date,
            active_map_id=active_map_id,
            resolve_item=resolve_item,
        )

        return EventAuthoringContext(
            event_id=event.id,
            context_date=effective_date,
            participants=tuple(participants),
            locations=tuple(locations),
            mentions=tuple(mentions),
            previous_events=tuple(previous),
            concurrent_events=tuple(concurrent),
            next_events=tuple(following),
            direct_relations=tuple(direct),
            neighborhood_relations=tuple(neighborhood),
            spatial=tuple(spatial),
            omitted_counts=tuple(sorted(omitted.items())),
        )

    def build_entity_context(  # noqa: C901
        self, entity_id: str
    ) -> EntityAuthoringContext | None:
        """Return deterministic durable persisted context around an Entity."""
        entity = self._db.get_entity(entity_id)
        if entity is None:
            return None

        entities_by_id = {item.id: item for item in self._db.get_all_entities()}
        entities_by_id[entity.id] = entity
        events_by_id = {item.id: item for item in self._db.get_all_events()}
        item_cache: dict[str, ContextItem | None] = {}
        event_cache: dict[str, Event | None] = dict(events_by_id)

        def resolve_item(item_id: str) -> ContextItem | None:
            if item_id in item_cache:
                return item_cache[item_id]
            related_entity = entities_by_id.get(item_id)
            result: ContextItem | None
            if related_entity is not None:
                result = ContextItem(
                    related_entity.id, "entity", related_entity.name
                )
            else:
                related_event = events_by_id.get(item_id)
                event_cache[item_id] = related_event
                result = (
                    ContextItem(related_event.id, "event", related_event.name)
                    if related_event is not None
                    else None
                )
            item_cache[item_id] = result
            if result is None:
                logger.warning("Skipping unresolved authoring-context item %s", item_id)
            return result

        omitted: dict[str, int] = {}
        attributes = self._bounded_entity_attributes(entity.attributes, omitted)
        tag_memberships = self._db.get_entity_tag_memberships()
        tags = self._entity_tags(
            entity, tag_memberships.get(entity.id, []), omitted
        )

        appearance_roles: dict[str, set[str]] = {}
        mentions: list[ContextEvent] = []
        linked_references: list[ContextRelation] = []
        direct: list[ContextRelation] = []
        temporal: list[ContextRelation] = []
        seeds: list[ContextItem] = []
        relations_by_item: dict[str, list[dict[str, Any]]] = {}
        all_relations = sorted(self._db.get_all_relations(), key=self._relation_key)
        for relation in all_relations:
            source_id = str(relation.get("source_id", ""))
            target_id = str(relation.get("target_id", ""))
            relations_by_item.setdefault(source_id, []).append(relation)
            if target_id != source_id:
                relations_by_item.setdefault(target_id, []).append(relation)
        for indexed in relations_by_item.values():
            indexed.sort(key=self._relation_key)
        relations = relations_by_item.get(entity_id, [])
        for relation in relations:
            rel_type = str(relation.get("rel_type", ""))
            source_id = str(relation.get("source_id", ""))
            target_id = str(relation.get("target_id", ""))
            source = resolve_item(source_id)
            target = resolve_item(target_id)
            if source is None or target is None:
                if rel_type == "mentions":
                    omitted["linked_references"] = (
                        omitted.get("linked_references", 0) + 1
                    )
                continue
            if source.object_type == "event" and target_id == entity_id:
                event = self._cached_event(source_id, event_cache)
                if event is not None and rel_type == "mentions":
                    self._append_event(mentions, event)
                if event is not None and rel_type in (
                    PARTICIPANT_REL_TYPES | {"located_at"}
                ):
                    appearance_roles.setdefault(event.id, set()).add(rel_type)
                    self._append_item(seeds, source)
                    continue
            if rel_type == "mentions":
                linked = self._resolve_relation_history(
                    relation,
                    hop=0,
                    resolve_item=resolve_item,
                    event_cache=event_cache,
                )
                if linked is not None:
                    linked_references.append(linked)
                continue
            resolved = self._resolve_relation_history(
                relation,
                hop=0,
                resolve_item=resolve_item,
                event_cache=event_cache,
            )
            if resolved is None:
                continue
            if resolved.temporal_kind == "persistent":
                direct.append(resolved)
            else:
                temporal.append(resolved)
            opposite = target if source_id == entity_id else source
            self._append_item(seeds, opposite)

        appearances = [
            ContextEventAppearance(
                event=self._context_event(events_by_id[event_id]),
                roles=tuple(sorted(roles, key=lambda item: (item.casefold(), item))),
            )
            for event_id, roles in appearance_roles.items()
            if event_id in events_by_id
        ]
        appearances.sort(key=lambda item: (item.event.lore_date, item.event.id))
        mentions.sort(key=lambda item: (item.lore_date, item.id))
        linked_references.sort(key=self._context_relation_key)
        direct.sort(key=self._context_relation_key)
        temporal.sort(key=self._context_relation_key)
        appearances = self._limit_recent_appearances(
            "event_appearances", appearances, omitted
        )
        mentions = self._limit_recent_events("mentions", mentions, omitted)
        linked_references = self._limit(
            "linked_references",
            linked_references,
            MAX_LINKED_REFERENCES,
            omitted,
        )
        direct = self._limit(
            "direct_relations", direct, MAX_DIRECT_RELATIONS, omitted
        )
        temporal = self._limit(
            "temporal_history", temporal, MAX_DIRECT_RELATIONS, omitted
        )
        neighborhood = self._traverse_entity_relations(
            root_entity_id=entity_id,
            seeds=seeds,
            resolve_item=resolve_item,
            event_cache=event_cache,
            relations_by_item=relations_by_item,
        )
        neighborhood = self._limit(
            "neighborhood_relations",
            neighborhood,
            MAX_NEIGHBORHOOD_RELATIONS,
            omitted,
        )
        all_map_appearances = self._entity_map_appearances(entity_id)
        map_appearances = list(all_map_appearances)
        map_appearances = self._limit(
            "map_appearances", map_appearances, MAX_ENTITY_MAPS, omitted
        )
        co_appearances = self._entity_co_appearances(
            entity_id,
            appearance_roles,
            all_relations,
            entities_by_id,
            events_by_id,
            omitted,
        )
        shared_tags = self._entity_shared_tags(
            entity_id,
            tags,
            entities_by_id,
            tag_memberships,
            omitted,
        )
        shared_maps = self._entity_shared_maps(
            entity_id, all_map_appearances, entities_by_id, omitted
        )
        attachments = self._entity_attachment_captions(entity_id, omitted)
        self._trim_entity_context(
            attributes=attributes,
            tags=tags,
            appearances=appearances,
            mentions=mentions,
            linked_references=linked_references,
            direct=direct,
            temporal=temporal,
            neighborhood=neighborhood,
            maps=map_appearances,
            co_appearances=co_appearances,
            shared_tags=shared_tags,
            shared_maps=shared_maps,
            attachments=attachments,
            omitted=omitted,
        )
        return EntityAuthoringContext(
            entity_id=entity.id,
            attributes=tuple(attributes),
            tags=tuple(tags),
            event_appearances=tuple(appearances),
            mentions=tuple(mentions),
            linked_references=tuple(linked_references),
            direct_relations=tuple(direct),
            temporal_history=tuple(temporal),
            neighborhood_relations=tuple(neighborhood),
            map_appearances=tuple(map_appearances),
            co_appearances=tuple(co_appearances),
            shared_tags=tuple(shared_tags),
            shared_maps=tuple(shared_maps),
            attachments=tuple(attachments),
            omitted_counts=tuple(sorted(omitted.items())),
        )

    def _resolve_relation_history(
        self,
        relation: dict[str, Any],
        *,
        hop: int,
        resolve_item: Callable[[str], ContextItem | None],
        event_cache: dict[str, Event | None],
    ) -> ContextRelation | None:
        """Resolve a relation without asserting activity at any date."""
        source_id = str(relation.get("source_id", ""))
        source = resolve_item(source_id)
        target = resolve_item(str(relation.get("target_id", "")))
        if source is None or target is None:
            return None
        source_date: float | None = None
        if source.object_type == "event":
            source_event = self._cached_event(source_id, event_cache)
            if source_event is not None:
                source_date = source_event.lore_date
        window = resolve_temporal_window(
            dict(relation.get("attributes") or {}), source_date
        )
        if not window.is_valid:
            logger.warning(
                "Skipping invalid temporal relation %s: %s",
                relation.get("id"),
                window.error,
            )
            return None
        kind: TemporalKind = "persistent"
        if window.kind == TemporalWindowKind.INSTANT:
            kind = "instant"
        elif window.kind != TemporalWindowKind.UNBOUNDED:
            kind = "interval"
        return ContextRelation(
            id=str(relation.get("id", "")),
            source=source,
            target=target,
            rel_type=str(relation.get("rel_type", "related")),
            hop=hop,
            temporal_kind=kind,
            valid_from=window.start,
            valid_to=window.end,
        )

    def _traverse_entity_relations(
        self,
        *,
        root_entity_id: str,
        seeds: list[ContextItem],
        resolve_item: Callable[[str], ContextItem | None],
        event_cache: dict[str, Event | None],
        relations_by_item: dict[str, list[dict[str, Any]]],
    ) -> list[ContextRelation]:
        queue = deque((seed.id, 0) for seed in sorted(seeds, key=self._item_key))
        visited_items = {root_entity_id, *(seed.id for seed in seeds)}
        emitted: set[str] = set()
        results: list[ContextRelation] = []
        while queue:
            item_id, depth = queue.popleft()
            if depth >= MAX_RELATION_HOPS:
                continue
            for relation in relations_by_item.get(item_id, []):
                relation_id = str(relation.get("id", ""))
                source_id = str(relation.get("source_id", ""))
                target_id = str(relation.get("target_id", ""))
                if (
                    relation.get("rel_type") == "mentions"
                    or root_entity_id in {source_id, target_id}
                    or relation_id in emitted
                ):
                    continue
                resolved = self._resolve_relation_history(
                    relation,
                    hop=depth + 1,
                    resolve_item=resolve_item,
                    event_cache=event_cache,
                )
                if resolved is None:
                    continue
                emitted.add(relation_id)
                results.append(resolved)
                opposite_id = target_id if source_id == item_id else source_id
                if opposite_id not in visited_items:
                    visited_items.add(opposite_id)
                    queue.append((opposite_id, depth + 1))
        results.sort(key=self._context_relation_key)
        return results

    def _entity_map_appearances(
        self, entity_id: str
    ) -> list[ContextMapAppearance]:
        all_maps = self._db.get_all_maps()
        maps = {item.id: item for item in all_maps}
        appearances = []
        for marker in self._db.get_markers_for_object(entity_id, "entity"):
            map_item = maps.get(marker.map_id)
            if map_item is None:
                logger.warning("Skipping unresolved map appearance %s", marker.map_id)
                continue
            appearances.append(
                ContextMapAppearance(
                    map_id=map_item.id,
                    map_name=map_item.name,
                    feature_type=str(marker.feature_type or "point"),
                    marker_label=(marker.label.strip() or None),
                    parent_maps=tuple(
                        ContextItem(parent.id, "map", parent.name)
                        for parent in self._safe_map_ancestors(map_item.id, all_maps)
                    ),
                )
            )
        appearances.sort(
            key=lambda item: (item.map_name.casefold(), item.map_id, item.feature_type)
        )
        return appearances

    @staticmethod
    def _safe_map_ancestors(map_id: str, all_maps: list[Map]) -> list[Map]:
        try:
            return list(MapNestingService.iter_ancestors(map_id, all_maps))
        except Exception:
            logger.warning(
                "Skipping malformed map ancestry for %s", map_id, exc_info=True
            )
            return []

    def _entity_tags(
        self,
        entity: Entity,
        stored: list[dict[str, Any]],
        omitted: dict[str, int],
    ) -> list[ContextTag]:
        """Return public tags without exposing private attribute metadata."""
        by_name: dict[str, ContextTag] = {}
        for raw in stored:
            name = str(raw.get("name", "")).strip()
            if name:
                by_name[name.casefold()] = ContextTag(str(raw.get("id", "")), name)
        for raw_name in entity.tags:
            name = str(raw_name).strip()
            if name and name.casefold() not in by_name:
                by_name[name.casefold()] = ContextTag("", name)
        tags = sorted(by_name.values(), key=lambda item: (item.name.casefold(), item.id))
        return self._limit("tags", tags, MAX_ENTITY_TAGS, omitted)

    def _entity_co_appearances(
        self,
        entity_id: str,
        appearance_roles: dict[str, set[str]],
        relations: list[dict[str, Any]],
        entities_by_id: dict[str, Entity],
        events_by_id: dict[str, Event],
        omitted: dict[str, int],
    ) -> list[ContextCoAppearance]:
        shared_events: dict[str, dict[str, Event]] = {}
        relevant_event_ids = set(appearance_roles)
        for relation in relations:
            source_id = str(relation.get("source_id", ""))
            target_id = str(relation.get("target_id", ""))
            if (
                source_id not in relevant_event_ids
                or target_id == entity_id
                or target_id not in entities_by_id
                or str(relation.get("rel_type", ""))
                not in (PARTICIPANT_REL_TYPES | {"located_at"})
            ):
                continue
            event = events_by_id.get(source_id)
            if event is not None:
                shared_events.setdefault(target_id, {})[event.id] = event

        results = []
        for related_id, events in shared_events.items():
            related = entities_by_id[related_id]
            ordered = sorted(events.values(), key=lambda item: (item.lore_date, item.id))
            results.append(
                ContextCoAppearance(
                    item=ContextItem(related.id, "entity", related.name),
                    events=tuple(
                        self._context_event(item)
                        for item in ordered[-MAX_CO_APPEARANCE_EVENTS:]
                    ),
                    event_count=len(ordered),
                )
            )
        results.sort(
            key=lambda item: (-item.event_count, item.item.name.casefold(), item.item.id)
        )
        return self._limit(
            "co_appearances", results, MAX_CO_APPEARANCES, omitted
        )

    def _entity_shared_tags(
        self,
        entity_id: str,
        root_tags: list[ContextTag],
        entities_by_id: dict[str, Entity],
        tag_memberships: dict[str, list[dict[str, Any]]],
        omitted: dict[str, int],
    ) -> list[ContextSharedAssociation]:
        root_by_name = {tag.name.casefold(): tag.name for tag in root_tags}
        results = []
        for related in entities_by_id.values():
            if related.id == entity_id:
                continue
            related_tag_names = {
                str(item.get("name", "")).strip()
                for item in tag_memberships.get(related.id, [])
                if str(item.get("name", "")).strip()
            }
            related_tag_names.update(str(tag).strip() for tag in related.tags)
            shared = sorted(
                {
                    root_by_name[str(tag).strip().casefold()]
                    for tag in related_tag_names
                    if str(tag).strip().casefold() in root_by_name
                },
                key=str.casefold,
            )
            if shared:
                results.append(
                    ContextSharedAssociation(
                        ContextItem(related.id, "entity", related.name),
                        tuple(shared),
                    )
                )
        results.sort(
            key=lambda item: (-len(item.evidence), item.item.name.casefold(), item.item.id)
        )
        return self._limit("shared_tags", results, MAX_SHARED_ASSOCIATIONS, omitted)

    def _entity_shared_maps(
        self,
        entity_id: str,
        root_maps: list[ContextMapAppearance],
        entities_by_id: dict[str, Entity],
        omitted: dict[str, int],
    ) -> list[ContextSharedAssociation]:
        root_map_names = {item.map_id: item.map_name for item in root_maps}
        evidence_by_entity: dict[str, set[str]] = {}
        for map_id, map_name in root_map_names.items():
            for marker in self._db.get_markers_for_map(map_id):
                if (
                    marker.object_type == "entity"
                    and marker.object_id != entity_id
                    and marker.object_id in entities_by_id
                ):
                    evidence_by_entity.setdefault(marker.object_id, set()).add(map_name)
        results = [
            ContextSharedAssociation(
                ContextItem(item_id, "entity", entities_by_id[item_id].name),
                tuple(sorted(evidence, key=str.casefold)),
            )
            for item_id, evidence in evidence_by_entity.items()
        ]
        results.sort(
            key=lambda item: (-len(item.evidence), item.item.name.casefold(), item.item.id)
        )
        return self._limit("shared_maps", results, MAX_SHARED_ASSOCIATIONS, omitted)

    def _entity_attachment_captions(
        self, entity_id: str, omitted: dict[str, int]
    ) -> list[ContextAttachment]:
        attachments = [
            ContextAttachment(item.id, caption)
            for item in self._db.get_attachment_repo().list_by_owner(
                "entity", entity_id
            )
            if (caption := str(item.caption or "").strip())
        ]
        return self._limit("attachments", attachments, MAX_ATTACHMENTS, omitted)

    def _cached_event(
        self, event_id: str, cache: dict[str, Event | None]
    ) -> Event | None:
        if event_id not in cache:
            cache[event_id] = self._db.get_event(event_id)
        return cache[event_id]

    def _bounded_entity_attributes(
        self, raw_attributes: dict[str, Any], omitted: dict[str, int]
    ) -> list[ContextAttribute]:
        values = sorted(
            (
                (str(name), self._json_safe(value))
                for name, value in raw_attributes.items()
                if not str(name).startswith("_")
            ),
            key=lambda item: (item[0].casefold(), item[0]),
        )
        if len(values) > MAX_ENTITY_ATTRIBUTES:
            omitted["attributes"] = len(values) - MAX_ENTITY_ATTRIBUTES
        results: list[ContextAttribute] = []
        remaining = MAX_ATTRIBUTE_TOTAL_CHARS
        truncated = 0
        for name, value in values[:MAX_ENTITY_ATTRIBUTES]:
            rendered = json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            allowed = min(MAX_ATTRIBUTE_VALUE_CHARS, remaining)
            if allowed <= 0:
                omitted["attributes"] = omitted.get("attributes", 0) + 1
                continue
            if len(rendered) > allowed:
                value = rendered[: max(0, allowed - 1)] + "…"
                truncated += 1
                rendered = str(value)
            results.append(ContextAttribute(name, value))
            remaining -= len(rendered)
        if truncated:
            omitted["attribute_details"] = truncated
        return results

    @staticmethod
    def _trim_entity_context(
        *,
        attributes: list[ContextAttribute],
        tags: list[ContextTag],
        appearances: list[ContextEventAppearance],
        mentions: list[ContextEvent],
        linked_references: list[ContextRelation],
        direct: list[ContextRelation],
        temporal: list[ContextRelation],
        neighborhood: list[ContextRelation],
        maps: list[ContextMapAppearance],
        co_appearances: list[ContextCoAppearance],
        shared_tags: list[ContextSharedAssociation],
        shared_maps: list[ContextSharedAssociation],
        attachments: list[ContextAttachment],
        omitted: dict[str, int],
    ) -> None:
        """Enforce one total prompt-size budget by dropping lowest-priority facts."""
        def size() -> int:
            return (
                sum(len(item.name) + len(str(item.value)) for item in attributes)
                + sum(len(item.name) for item in tags)
                + sum(
                    len(item.event.name) + sum(map(len, item.roles)) + 24
                    for item in appearances
                )
                + sum(len(item.name) + 24 for item in mentions)
                + sum(
                len(item.source.name) + len(item.target.name) + len(item.rel_type) + 32
                    for item in (
                        *direct,
                        *temporal,
                        *linked_references,
                        *neighborhood,
                    )
                )
                + sum(
                    len(item.map_name)
                    + len(item.feature_type)
                    + len(item.marker_label or "")
                    + sum(len(parent.name) for parent in item.parent_maps)
                    + 16
                    for item in maps
                )
                + sum(
                    len(item.item.name)
                    + sum(len(event.name) for event in item.events)
                    + 24
                    for item in co_appearances
                )
                + sum(
                    len(item.item.name) + sum(map(len, item.evidence)) + 16
                    for item in (*shared_tags, *shared_maps)
                )
                + sum(len(item.caption) + 16 for item in attachments)
            )

        sections: tuple[tuple[str, list[Any], bool], ...] = (
            ("neighborhood_relations", neighborhood, False),
            ("shared_maps", shared_maps, False),
            ("shared_tags", shared_tags, False),
            ("attachments", attachments, False),
            ("co_appearances", co_appearances, False),
            ("mentions", mentions, True),
            ("linked_references", linked_references, False),
            ("temporal_history", temporal, False),
            ("event_appearances", appearances, True),
            ("map_appearances", maps, False),
            ("direct_relations", direct, False),
            ("tags", tags, False),
            ("attributes", attributes, False),
        )
        while size() > MAX_ENTITY_CONTEXT_CHARS:
            for section, items, remove_oldest in sections:
                if items:
                    items.pop(0 if remove_oldest else -1)
                    omitted[section] = omitted.get(section, 0) + 1
                    break
            else:
                break

    @staticmethod
    def _append_event(items: list[ContextEvent], event: Event) -> None:
        if all(existing.id != event.id for existing in items):
            items.append(AuthoringContextBuilder._context_event(event))

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {
                str(key): AuthoringContextBuilder._json_safe(nested)
                for key, nested in sorted(value.items(), key=lambda item: str(item[0]))
            }
        if isinstance(value, (list, tuple)):
            return [AuthoringContextBuilder._json_safe(item) for item in value]
        return str(value)

    def _resolve_relation(
        self,
        relation: dict[str, Any],
        *,
        hop: int,
        context_date: float,
        root_event: Event,
        resolve_item: Callable[[str], ContextItem | None],
        event_cache: dict[str, Event | None],
    ) -> ContextRelation | None:
        source_id = str(relation.get("source_id", ""))
        target_id = str(relation.get("target_id", ""))
        source = resolve_item(source_id)
        target = resolve_item(target_id)
        if source is None or target is None:
            return None

        source_event_date: float | None = None
        if source_id == root_event.id:
            source_event_date = context_date
        elif source.object_type == "event":
            source_event = event_cache.get(source_id)
            if source_id not in event_cache:
                source_event = self._db.get_event(source_id)
                event_cache[source_id] = source_event
            if source_event is not None:
                source_event_date = source_event.lore_date

        window = resolve_temporal_window(
            dict(relation.get("attributes") or {}), source_event_date
        )
        if window.kind == TemporalWindowKind.UNBOUNDED:
            kind: TemporalKind = "persistent"
        else:
            if not window.is_valid or not window.is_active(context_date):
                if window.error:
                    logger.warning(
                        "Skipping invalid temporal relation %s: %s",
                        relation.get("id"),
                        window.error,
                    )
                return None
            kind = (
                "instant"
                if window.kind == TemporalWindowKind.INSTANT
                else "interval"
            )

        return ContextRelation(
            id=str(relation.get("id", "")),
            source=source,
            target=target,
            rel_type=str(relation.get("rel_type", "related")),
            hop=hop,
            temporal_kind=kind,
            valid_from=window.start,
            valid_to=window.end,
        )

    def _event_neighbors(
        self,
        event_id: str,
        context_date: float,
        omitted: dict[str, int],
    ) -> tuple[list[ContextEvent], list[ContextEvent], list[ContextEvent]]:
        events = sorted(
            (event for event in self._db.get_all_events() if event.id != event_id),
            key=lambda item: (item.lore_date, item.id),
        )
        previous_all = [event for event in events if event.lore_date < context_date]
        concurrent_all = [event for event in events if event.lore_date == context_date]
        next_all = [event for event in events if event.lore_date > context_date]
        if len(previous_all) > MAX_SIDE_EVENTS:
            omitted["previous_events"] = len(previous_all) - MAX_SIDE_EVENTS
        if len(next_all) > MAX_SIDE_EVENTS:
            omitted["next_events"] = len(next_all) - MAX_SIDE_EVENTS
        concurrent = self._limit(
            "concurrent_events",
            concurrent_all,
            MAX_CONCURRENT_EVENTS,
            omitted,
        )
        return (
            [
                self._context_event(item)
                for item in previous_all[-MAX_SIDE_EVENTS:]
            ],
            [self._context_event(item) for item in concurrent],
            [self._context_event(item) for item in next_all[:MAX_SIDE_EVENTS]],
        )

    def _traverse_relations(
        self,
        *,
        seeds: list[ContextItem],
        root_event: Event,
        context_date: float,
        resolve_item: Callable[[str], ContextItem | None],
        event_cache: dict[str, Event | None],
    ) -> list[ContextRelation]:
        queue = deque((seed.id, 0) for seed in sorted(seeds, key=self._item_key))
        visited_items = {seed.id for seed in seeds}
        emitted: set[str] = set()
        results: list[ContextRelation] = []

        while queue:
            item_id, depth = queue.popleft()
            if depth >= MAX_RELATION_HOPS:
                continue
            candidates = sorted(
                self._db.get_relations_for_item(item_id), key=self._relation_key
            )
            for relation in candidates:
                relation_id = str(relation.get("id", ""))
                source_id = str(relation.get("source_id", ""))
                target_id = str(relation.get("target_id", ""))
                if (
                    relation.get("rel_type") == "mentions"
                    or root_event.id in {source_id, target_id}
                    or relation_id in emitted
                ):
                    continue
                resolved = self._resolve_relation(
                    relation,
                    hop=depth + 1,
                    context_date=context_date,
                    root_event=root_event,
                    resolve_item=resolve_item,
                    event_cache=event_cache,
                )
                if resolved is None:
                    continue
                emitted.add(relation_id)
                results.append(resolved)
                opposite_id = target_id if source_id == item_id else source_id
                if opposite_id not in visited_items:
                    visited_items.add(opposite_id)
                    queue.append((opposite_id, depth + 1))

        results.sort(key=self._context_relation_key)
        return results

    def _resolve_spatial(
        self,
        *,
        event: Event,
        locations: list[ContextItem],
        context_date: float,
        active_map_id: str | None,
        resolve_item: Callable[[str], ContextItem | None],
    ) -> list[SpatialAuthoringContext]:
        if not active_map_id:
            return []
        builder = SpatialContextBuilder(
            self._db.map_repo,
            world_root=self._world_root,
            name_lookup=lambda item_id, _item_type: (
                item.name if (item := resolve_item(item_id)) is not None else None
            ),
            nesting_service=MapNestingService(),
            feature_geometry_repo=self._db.feature_geometry_repo,
            trajectory_repo=self._db.trajectory_repo,
        )
        event_item = ContextItem(event.id, "event", event.name)
        direct_text = builder.build(
            event.id, "event", active_map_id, context_date
        )
        if direct_text:
            return [SpatialAuthoringContext(event_item, direct_text)]

        results: list[SpatialAuthoringContext] = []
        for location in locations:
            text = builder.build(
                location.id, location.object_type, active_map_id, context_date
            )
            if text:
                results.append(SpatialAuthoringContext(location, text))
            if len(results) >= MAX_SPATIAL_ANCHORS:
                break
        return results

    @staticmethod
    def _append_item(items: list[ContextItem], item: ContextItem | None) -> None:
        if item is not None and all(existing.id != item.id for existing in items):
            items.append(item)

    @staticmethod
    def _item_key(item: ContextItem) -> tuple[str, str]:
        return item.name.casefold(), item.id

    @staticmethod
    def _relation_key(relation: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            str(relation.get("rel_type", "")).casefold(),
            str(relation.get("source_id", "")),
            str(relation.get("target_id", "")),
            str(relation.get("id", "")),
        )

    @staticmethod
    def _context_relation_key(
        relation: ContextRelation,
    ) -> tuple[int, str, str, str, str]:
        return (
            relation.hop,
            relation.source.name.casefold(),
            relation.rel_type.casefold(),
            relation.target.name.casefold(),
            relation.id,
        )

    @staticmethod
    def _context_event(event: Event) -> ContextEvent:
        return ContextEvent(event.id, event.name, event.lore_date, event.type)

    @staticmethod
    def _limit(
        section: str,
        items: list[Any],
        limit: int,
        omitted: dict[str, int],
    ) -> list[Any]:
        if len(items) > limit:
            omitted[section] = len(items) - limit
        return items[:limit]

    @staticmethod
    def _limit_recent_events(
        section: str,
        items: list[ContextEvent],
        omitted: dict[str, int],
    ) -> list[ContextEvent]:
        if len(items) > MAX_ENTITY_EVENTS:
            omitted[section] = len(items) - MAX_ENTITY_EVENTS
        return items[-MAX_ENTITY_EVENTS:]

    @staticmethod
    def _limit_recent_appearances(
        section: str,
        items: list[ContextEventAppearance],
        omitted: dict[str, int],
    ) -> list[ContextEventAppearance]:
        if len(items) > MAX_ENTITY_EVENTS:
            omitted[section] = len(items) - MAX_ENTITY_EVENTS
        return items[-MAX_ENTITY_EVENTS:]


def format_event_authoring_context(context: EventAuthoringContext) -> str:
    """Format the complete bounded context for an LLM or preview."""
    lines = ["[Authoritative Context]"]

    if context.previous_events or context.concurrent_events or context.next_events:
        lines.append("Timeline:")
        lines.extend(f"- Before: {item.name}" for item in context.previous_events)
        lines.extend(
            f"- At the same time: {item.name}" for item in context.concurrent_events
        )
        lines.extend(f"- After: {item.name}" for item in context.next_events)
    if context.participants:
        lines.append("Participants: " + ", ".join(x.name for x in context.participants))
    if context.locations:
        lines.append("Locations: " + ", ".join(x.name for x in context.locations))
    if context.direct_relations:
        lines.append("Direct relations:")
        lines.extend(_format_relation(item) for item in context.direct_relations)
    if context.neighborhood_relations:
        lines.append("Relations at this date:")
        lines.extend(_format_relation(item) for item in context.neighborhood_relations)
    if context.mentions:
        lines.append("Mentioned: " + ", ".join(x.name for x in context.mentions))
    for spatial in context.spatial:
        spatial_lines = spatial.text.splitlines()
        if spatial_lines and spatial_lines[0].strip() == "[Spatial Context]":
            spatial_lines = spatial_lines[1:]
        lines.append(f"Map context for {spatial.anchor.name}:")
        lines.extend(spatial_lines)
    for section, count in context.omitted_counts:
        lines.append(f"- {count} additional {section.replace('_', ' ')} omitted.")
    return "\n".join(lines)


def format_entity_authoring_context(context: EntityAuthoringContext) -> str:
    """Format the complete bounded durable Entity context."""
    lines = ["[Authoritative Context]"]
    if context.attributes:
        lines.append("Structured attributes:")
        lines.extend(
            f"- {item.name}: {_format_attribute_value(item.value)}"
            for item in context.attributes
        )
    if context.tags:
        lines.append("Tags: " + ", ".join(item.name for item in context.tags))
    if context.event_appearances:
        lines.append("Event appearances and roles:")
        lines.extend(
            f"- {item.event.name}: {', '.join(item.roles)}"
            for item in context.event_appearances
        )
    if context.direct_relations:
        lines.append("Durable direct relations:")
        lines.extend(_format_relation(item) for item in context.direct_relations)
    if context.temporal_history:
        lines.append("Temporal relation history (do not state as timeless):")
        lines.extend(_format_relation_with_window(item) for item in context.temporal_history)
    if context.linked_references:
        lines.append("Explicit linked references:")
        lines.extend(_format_relation(item) for item in context.linked_references)
    if context.neighborhood_relations:
        lines.append("Surrounding relations:")
        lines.extend(
            _format_relation_with_window(item)
            for item in context.neighborhood_relations
        )
    if context.mentions:
        lines.append("Mentioned in Events:")
        lines.extend(f"- {item.name}" for item in context.mentions)
    if context.map_appearances:
        lines.append("Durable map appearances:")
        lines.extend(
            f"- Placed on {item.map_name}"
            + (
                f" as a {item.feature_type}"
                if item.feature_type.strip().casefold() not in {"", "point"}
                else ""
            )
            + (f" as {item.marker_label}" if item.marker_label else "")
            + (
                " within " + " > ".join(parent.name for parent in item.parent_maps)
                if item.parent_maps
                else ""
            )
            for item in context.map_appearances
        )
    if context.co_appearances:
        lines.append("Appears with in Events (evidence, not an inferred relation):")
        lines.extend(
            f"- {item.item.name}: {item.event_count} shared Event(s)"
            + (
                " (" + ", ".join(event.name for event in item.events) + ")"
                if item.events
                else ""
            )
            for item in context.co_appearances
        )
    if context.attachments:
        lines.append("Authored attachment captions:")
        lines.extend(f"- {item.caption}" for item in context.attachments)
    if context.shared_tags:
        lines.append("Shares tags (classification only):")
        lines.extend(
            f"- {item.item.name}: {', '.join(item.evidence)}"
            for item in context.shared_tags
        )
    if context.shared_maps:
        lines.append("Also placed on map (not necessarily contemporaneous):")
        lines.extend(
            f"- {item.item.name}: {', '.join(item.evidence)}"
            for item in context.shared_maps
        )
    for section, count in context.omitted_counts:
        lines.append(f"- {count} additional {section.replace('_', ' ')} omitted.")
    return "\n".join(lines)


def _format_relation(relation: ContextRelation) -> str:
    return (
        f"- {relation.source.name} --{relation.rel_type}--> "
        f"{relation.target.name}"
    )


def _format_relation_with_window(relation: ContextRelation) -> str:
    line = _format_relation(relation)
    if relation.temporal_kind == "persistent":
        return line
    start = "?" if relation.valid_from is None else format(relation.valid_from, ".12g")
    end = "?" if relation.valid_to is None else format(relation.valid_to, ".12g")
    return f"{line} [{relation.temporal_kind}: {start} to {end}]"


def _format_attribute_value(value: Any) -> str:
    if isinstance(value, dict):
        return ", ".join(
            f"{key}={_format_attribute_value(nested)}"
            for key, nested in value.items()
        )
    if isinstance(value, list):
        return ", ".join(_format_attribute_value(item) for item in value)
    return str(value)


def lookup_event_authoring_context(
    db_path: str,
    event_id: str,
    *,
    context_date: float | None = None,
    active_map_id: str | None = None,
) -> EventAuthoringContext | None:
    """Build Event context using one short-lived read-only connection."""
    db: DatabaseService | None = None
    try:
        db = DatabaseService(db_path, read_only=True)
        db.connect()
        with db.transaction():
            return AuthoringContextBuilder(
                db, world_root=Path(db_path).parent
            ).build_event_context(
                event_id,
                context_date=context_date,
                active_map_id=active_map_id,
            )
    except Exception:
        logger.error("Event authoring-context lookup failed", exc_info=True)
        return None
    finally:
        if db is not None:
            db.close()


def lookup_entity_authoring_context(
    db_path: str,
    entity_id: str,
) -> EntityAuthoringContext | None:
    """Build Entity context using one short-lived read-only connection."""
    db: DatabaseService | None = None
    try:
        db = DatabaseService(db_path, read_only=True)
        db.connect()
        with db.transaction():
            return AuthoringContextBuilder(
                db, world_root=Path(db_path).parent
            ).build_entity_context(entity_id)
    except Exception:
        logger.error("Entity authoring-context lookup failed", exc_info=True)
        return None
    finally:
        if db is not None:
            db.close()
