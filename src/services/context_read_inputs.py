"""Relevant worker-owned inputs for the shared authoring-context projection."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.core.entities import Entity
from src.core.events import Event
from src.core.mcp_access import McpFailure
from src.services.db_service import DatabaseService

MAX_RELEVANT = 5000


@dataclass
class ContextReadInputs:
    """Detached relevant records; projection semantics remain in the shared builder."""

    entities: list[Entity]
    events: list[Event]
    relations: list[dict[str, Any]]
    memberships: dict[str, list[dict[str, Any]]]
    neighbor_omissions: dict[str, int] = field(default_factory=dict)


def checkpoint(expired: Callable[[], bool]) -> None:
    """Release the worker promptly when an investigation is no longer authorized."""
    if expired():
        raise McpFailure("TIMEOUT")


def timing_component_ids(
    db: DatabaseService,
    seeds: set[str],
    expired: Callable[[], bool],
    graph: dict[str, set[str]] | None = None,
) -> set[str]:
    """Include both directions and constraint owners before solving any subset."""
    graph = timing_graph(db, expired) if graph is None else graph
    found, pending = set(seeds), list(seeds)
    while pending:
        checkpoint(expired)
        found_now = graph.get(pending.pop(), set()) - found
        found.update(found_now)
        pending.extend(found_now)
        if len(found) > MAX_RELEVANT:
            raise McpFailure("CONTEXT_LIMIT")
    return found


def timing_graph(
    db: DatabaseService, expired: Callable[[], bool]
) -> dict[str, set[str]]:
    """Discover thin timing references once, without loading unrelated prose."""
    graph: dict[str, set[str]] = {}
    for row in db.require_connection().execute(
        "SELECT id, CASE WHEN json_type(attributes, '$._temporal_v2')='object' "
        "THEN json_extract(attributes, '$._temporal_v2') END timing FROM events"
    ):
        checkpoint(expired)
        refs = _timing_references(json.loads(row["timing"]) if row["timing"] else {})
        for reference in refs:
            graph.setdefault(row["id"], set()).add(reference)
            graph.setdefault(reference, set()).add(row["id"])
    return graph


def _timing_references(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"anchor_id", "anchor_a", "anchor_b"} and isinstance(item, str):
                if item.startswith("event:"):
                    refs.add(item.removeprefix("event:").removesuffix(":end"))
            elif key != "projection":
                refs.update(_timing_references(item))
    elif isinstance(value, list):
        for item in value:
            refs.update(_timing_references(item))
    return refs


def relevant_inputs(
    db: DatabaseService,
    kind: str,
    identifier: str,
    expired: Callable[[], bool],
    *,
    day: float | None = None,
    bounded: bool = True,
) -> ContextReadInputs:
    """Discover associations without materializing unrelated descriptions/models."""
    found, frontier, relations = {identifier}, {identifier}, {}
    for _ in range(3):
        following: set[str] = set()
        for item_id in sorted(frontier):
            checkpoint(expired)
            for relation in db.get_relations_for_item(item_id):
                relations[relation["id"]] = relation
                following.update((relation["source_id"], relation["target_id"]))
        frontier = following - found
        found.update(frontier)
        _check_size(found, relations)
    memberships = (
        _shared_memberships(db, identifier, expired) if kind == "entity" else {}
    )
    if kind == "entity":
        found.update(_association_ids(db, identifier, memberships, expired))
    omissions: dict[str, int] = {}
    if kind == "event" and day is not None:
        neighbors, omissions = _neighbors(db, identifier, day, bounded)
        found.update(neighbors)
    _check_size(found, relations)
    entities, events = [], []
    for item_id in sorted(found):
        checkpoint(expired)
        entity = db.get_entity(item_id)
        if entity is not None:
            entities.append(entity)
        event = db.get_event(item_id)
        if event is not None:
            events.append(event)
    loaded_ids = {event.id for event in events}
    event_ids = set(loaded_ids)
    for relation in relations.values():
        event_ids.update(
            _timing_references(relation.get("attributes", {}).get("temporal", {}))
        )
    component = timing_component_ids(db, event_ids, expired)
    events.extend(
        event
        for item_id in sorted(component - loaded_ids)
        if (event := db.get_event(item_id)) is not None
    )
    return ContextReadInputs(
        entities, events, list(relations.values()), memberships, omissions
    )


def _check_size(found: set[str], relations: dict[str, Any]) -> None:
    if len(found) > MAX_RELEVANT or len(relations) > MAX_RELEVANT:
        raise McpFailure("CONTEXT_LIMIT")


def _association_ids(
    db: DatabaseService,
    identifier: str,
    memberships: dict[str, list[dict[str, Any]]],
    expired: Callable[[], bool],
) -> set[str]:
    root = db.get_entity(identifier)
    if root is None:
        return set()
    names = {str(tag).strip().casefold() for tag in root.tags}
    names.update(
        tag["name"].strip().casefold() for tag in memberships.get(identifier, [])
    )
    found: set[str] = set()
    for row in db.require_connection().execute(
        "SELECT id, json_extract(attributes,'$._tags') tags FROM entities"
    ):
        checkpoint(expired)
        legacy = json.loads(row["tags"]) if row["tags"] else []
        tags = {str(tag).strip().casefold() for tag in legacy}
        tags.update(
            tag["name"].strip().casefold() for tag in memberships.get(row["id"], [])
        )
        if names & tags:
            found.add(row["id"])
    for marker in db.get_markers_for_object(identifier, "entity"):
        found.update(
            item.object_id
            for item in db.get_markers_for_map(marker.map_id)
            if item.object_type == "entity"
        )
    return found


def _shared_memberships(
    db: DatabaseService, identifier: str, expired: Callable[[], bool]
) -> dict[str, list[dict[str, Any]]]:
    """Stream classification discovery; retain only the root's shared tag names."""
    root = db.get_entity(identifier)
    root_tags = db.get_tags_for_entity(identifier)
    names = {str(tag).strip().casefold() for tag in root.tags} if root else set()
    names.update(tag["name"].strip().casefold() for tag in root_tags)
    memberships: dict[str, list[dict[str, Any]]] = {identifier: root_tags}
    if not names:
        return memberships
    for row in db.require_connection().execute(
        "SELECT j.entity_id,t.id,t.name FROM entity_tags j JOIN tags t ON t.id=j.tag_id"
    ):
        checkpoint(expired)
        if row["entity_id"] != identifier and row["name"].strip().casefold() in names:
            memberships.setdefault(row["entity_id"], []).append(
                {"id": row["id"], "name": row["name"]}
            )
    return memberships


def _neighbors(
    db: DatabaseService, identifier: str, day: float, bounded: bool
) -> tuple[set[str], dict[str, int]]:
    found: set[str] = set()
    omitted: dict[str, int] = {}
    for section, operator, order, maximum in (
        ("previous_events", "<", "DESC", 2),
        ("concurrent_events", "=", "ASC", 12),
        ("next_events", ">", "ASC", 2),
    ):
        rows = (
            db.require_connection()
            .execute(
                f"SELECT id FROM events WHERE id != ? AND lore_date {operator} ? "
                f"ORDER BY lore_date {order}, id {order} LIMIT ?",
                (identifier, day, maximum if bounded else MAX_RELEVANT + 1),
            )
            .fetchall()
        )
        if len(rows) > MAX_RELEVANT:
            raise McpFailure("CONTEXT_LIMIT")
        found.update(row["id"] for row in rows)
        count = (
            db.require_connection()
            .execute(
                f"SELECT count(*) FROM events WHERE id != ? AND lore_date {operator} ?",
                (identifier, day),
            )
            .fetchone()[0]
        )
        if count > len(rows):
            omitted[section] = count - len(rows)
    return found, omitted
