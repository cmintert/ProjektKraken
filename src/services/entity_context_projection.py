"""Read-only temporal Entity projection over the existing resolution policies."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from typing import Any

from src.core.authoring_context import (
    ContextAttribute,
    ContextEvent,
    ContextItem,
    ContextRelation,
    EntityAuthoringContext,
)
from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.entities import Entity
from src.core.entity_context_mode import EntityContextMode
from src.core.events import Event
from src.core.temporal_anchors import resolve_event_anchors
from src.core.temporal_manager import TemporalManager
from src.core.temporal_relation_policy import (
    RelationTemporalMode,
    evaluate_temporal_relation,
)
from src.core.temporal_state import ResolvedEntityState
from src.services.db_service import DatabaseService


def public_value(value: Any) -> Any:
    """Copy public JSON values, including nested public structured attributes."""
    if isinstance(value, dict):
        return {
            str(key): public_value(item)
            for key, item in value.items()
            if not str(key).startswith("_")
        }
    if isinstance(value, (list, tuple)):
        return [public_value(item) for item in value]
    return value


def fact_source(source: dict[str, Any] | None) -> dict[str, Any]:
    """Retain source identity without copying source payloads or private fields."""
    source = source or {"kind": "baseline"}
    return {
        key: source[key]
        for key in ("kind", "relation_id", "event_id", "event_name", "event_date")
        if key in source
    }


MAX_DESCRIPTION_CHARS = 2400
MAX_PROJECTION_CHARS = 12000
MAX_POSSIBLE_CHANGES = 24
MAX_TIMING_NOTICES = 12
MAX_DESCRIPTION_CHANGE_CHARS = 400


def bound_projection(context: EntityAuthoringContext) -> EntityAuthoringContext:
    """Budget whole facts with their sources, never separating truth and evidence."""
    omitted = dict(context.omitted_counts)
    sections = (
        "shared_maps",
        "shared_tags",
        "attachments",
        "co_appearances",
        "mentions",
        "linked_references",
        "map_appearances",
        "tags",
        "neighborhood_relations",
        "event_appearances",
        "temporal_history",
        "possible_changes",
        "attributes",
        "temporal_notices",
    )
    while len(json.dumps(context.to_dict(), ensure_ascii=False)) > MAX_PROJECTION_CHARS:
        for name in sections:
            items = getattr(context, name)
            if items:
                omitted[name] = omitted.get(name, 0) + 1
                context = replace(
                    context,
                    **{name: items[:-1]},
                    omitted_counts=tuple(sorted(omitted.items())),
                )
                break
        else:
            if context.effective_description is not None:
                omitted["effective_description"] = 1
                context = replace(
                    context,
                    effective_description=None,
                    omitted_counts=tuple(sorted(omitted.items())),
                )
                continue
            if context.direct_relations:
                omitted["direct_relations"] = omitted.get("direct_relations", 0) + 1
                context = replace(
                    context,
                    direct_relations=context.direct_relations[:-1],
                    omitted_counts=tuple(sorted(omitted.items())),
                )
                continue
            break
    return context


class EntityContextProjectionService:
    """Resolve one query using fresh worker-owned reads; never mutate lore."""

    def __init__(
        self,
        db: DatabaseService,
        mode: EntityContextMode,
        context_date: float,
        events: dict[str, Event],
    ) -> None:
        """Capture the complete calendar and anchor context for one transaction."""
        if not math.isfinite(context_date):
            raise ValueError("Entity context requires a finite viewing date")
        self.mode = mode
        self.date = context_date
        self._db = db
        self._events = events
        config = db.get_active_calendar_config()
        self.converter = (
            CalendarConverter(config) if isinstance(config, CalendarConfig) else None
        )
        self._anchors = resolve_event_anchors(list(events.values()), self.converter)
        self._state: ResolvedEntityState | None = None

    def resolve_entity(self, entity: Entity) -> Entity:
        """Reuse fresh full-context Entity resolution rather than merging changes."""
        self._state = TemporalManager(self._db).get_entity_state_at(
            entity.id, self.date
        )
        attributes = public_value(self._state.attributes)
        # Tags are public classification metadata despite their legacy storage key.
        # Keep baseline classification; dated state never invents tag history.
        attributes["_tags"] = list(entity.tags)
        return replace(entity, attributes=attributes)

    def evaluate(self, relation: dict[str, Any]) -> dict[str, Any] | None:
        """Use graph membership, including source-event occurrence qualification."""
        source = self._events.get(str(relation.get("source_id", "")))
        enriched = dict(relation)
        if source is not None:
            enriched.update(
                source_event_date=source.lore_date,
                source_event_attributes=source.attributes,
            )
        if (
            source is not None
            and relation.get("rel_type")
            in {"mentions", "involved", "participated_in", "member_of", "located_at"}
            and "payload" not in relation.get("attributes", {})
        ):
            # Event appearances and mentions are evidence of an occurrence,
            # never timeless knowledge about an event that has not happened.
            occurrence = {
                "source_id": source.id,
                "source_event_date": source.lore_date,
                "source_event_attributes": source.attributes,
                "attributes": {"valid_at_event": True},
            }
            policy = RelationTemporalMode(self.mode.value)
            if (
                evaluate_temporal_relation(
                    occurrence, self.date, self.converter, policy, self._anchors
                )
                is None
            ):
                return None
        return evaluate_temporal_relation(
            enriched,
            self.date,
            self.converter,
            RelationTemporalMode(self.mode.value),
            self._anchors,
        )

    def relation(
        self,
        relation: dict[str, Any],
        source: ContextItem,
        target: ContextItem,
        hop: int,
    ) -> ContextRelation | None:
        """Keep canonical identity and full evidence for every qualified relation."""
        result = self.evaluate(relation)
        if result is None:
            return None
        evidence = result["temporal_evidence"]
        spec = relation.get("attributes", {}).get("temporal", {})
        spec = spec if isinstance(spec, dict) else {}
        boundaries = {key: spec[key] for key in ("start", "end", "at") if key in spec}
        evidence["authored_boundaries"] = boundaries
        event_ids = {
            str(bound.get("anchor", {}).get("anchor_id", "")).removeprefix("event:")
            for bound in boundaries.values()
            if isinstance(bound, dict)
        }
        if source.object_type == "event":
            event_ids.add(source.id)
        evidence["events"] = [
            {"id": key, "name": self._events[key].name}
            for key in sorted(event_ids)
            if key in self._events
        ]
        kind = evidence["kind"]
        return ContextRelation(
            id=str(relation["id"]),
            source=source,
            target=target,
            rel_type=str(relation.get("rel_type", "related")),
            hop=hop,
            temporal_kind=(
                "persistent"
                if kind == "unbounded"
                else "instant"
                if kind == "instant"
                else "interval"
            ),
            valid_from=evidence["start"],
            valid_to=evidence["end"],
            temporal_status=result["validity_status"],
            temporal_behavior=result["temporal_behavior"],
            temporal_summary=result["temporal_summary"],
            temporal_evidence=evidence,
        )

    def finish(self, context: EntityAuthoringContext) -> EntityAuthoringContext:
        """Attach bounded effective state and source identity after fact selection."""
        assert self._state is not None
        state = self._state
        attributes = tuple(
            replace(
                item,
                source=fact_source((state.attribute_sources or {}).get(item.name)),
                temporal_status=(
                    "possible"
                    if item.name in state.ambiguous_attributes
                    else "definite"
                ),
            )
            for item in context.attributes
        )
        possible = self._possible_changes(state)
        description = ContextAttribute(
            "Description",
            state.description[:MAX_DESCRIPTION_CHARS],
            fact_source(state.description_source),
            "possible" if "description" in state.ambiguous_attributes else "definite",
        )
        omitted = dict(context.omitted_counts)
        if len(state.description) > MAX_DESCRIPTION_CHARS:
            omitted["description_details"] = 1
        if len(possible) > MAX_POSSIBLE_CHANGES:
            omitted["possible_changes"] = len(possible) - MAX_POSSIBLE_CHANGES
        if len(state.temporal_warnings) > MAX_TIMING_NOTICES:
            omitted["temporal_notices"] = (
                len(state.temporal_warnings) - MAX_TIMING_NOTICES
            )
        return bound_projection(
            replace(
                context,
                mode=self.mode.value,
                context_date=self.date,
                date_label=(
                    self.converter.format_datetime(self.date)
                    if self.converter
                    else format(self.date, ".12g")
                ),
                attributes=attributes,
                event_appearances=tuple(
                    replace(item, event=self._qualify_event(item.event))
                    for item in context.event_appearances
                ),
                mentions=tuple(self._qualify_event(item) for item in context.mentions),
                co_appearances=tuple(
                    replace(
                        item,
                        events=tuple(
                            self._qualify_event(event) for event in item.events
                        ),
                    )
                    for item in context.co_appearances
                ),
                effective_description=description,
                possible_changes=tuple(possible[:MAX_POSSIBLE_CHANGES]),
                temporal_notices=tuple(state.temporal_warnings[:MAX_TIMING_NOTICES]),
                omitted_counts=tuple(sorted(omitted.items())),
            )
        )

    def description_changes_for_display(self) -> dict[str, Any]:
        """Project description payloads before budgeting, without attribute facts."""
        assert self._state is not None
        rows = []
        for effect in self._state.possible_effects:
            if "description" not in effect["payload"]:
                continue
            source = fact_source(
                effect["provenance"]
                | {"kind": "relation", "relation_id": effect["relation_id"]}
            )
            rows.append(
                ContextAttribute(
                    "Description",
                    str(effect["payload"]["description"])[:MAX_DESCRIPTION_CHANGE_CHARS]
                    + (
                        "… (shortened; inspect the source Event)"
                        if len(str(effect["payload"]["description"]))
                        > MAX_DESCRIPTION_CHANGE_CHARS
                        else ""
                    ),
                    source,
                    effect["validity"],
                ).to_dict()
            )
        return {
            "rows": rows[:MAX_POSSIBLE_CHANGES],
            "omitted": max(0, len(rows) - MAX_POSSIBLE_CHANGES),
        }

    def _qualify_event(self, event: ContextEvent) -> ContextEvent:
        source = self._events[event.id]
        result = evaluate_temporal_relation(
            {
                "source_id": source.id,
                "source_event_date": source.lore_date,
                "source_event_attributes": source.attributes,
                "attributes": {"valid_at_event": True},
            },
            self.date,
            self.converter,
            RelationTemporalMode.HISTORY_TO_PLAYHEAD,
            self._anchors,
        )
        assert result is not None
        established = result["historical_established"]
        return replace(
            event,
            temporal_status=("definite" if established else result["validity_status"]),
            temporal_label=result["temporal_summary"],
        )

    @staticmethod
    def _possible_changes(state: ResolvedEntityState) -> list[ContextAttribute]:
        results = []
        for effect in state.possible_effects:
            payload = effect["payload"]
            values = dict(public_value(payload.get("attributes", {})))
            values.update(
                {
                    key: "(removed)"
                    for key in payload.get("unset_attributes", [])
                    if not key.startswith("_")
                }
            )
            if "description" in payload:
                values["Description"] = payload["description"]
            source = fact_source(
                effect["provenance"]
                | {"kind": "relation", "relation_id": effect["relation_id"]}
            )
            for key, value in sorted(values.items()):
                text = json.dumps(value, ensure_ascii=False, sort_keys=True)
                results.append(
                    ContextAttribute(key, text[:400], source, effect["validity"])
                )
        return results
