"""Temporal Resolver Module.

Responsible for computing the state of an entity at a given point in time by aggregating
and merging relation-driven overrides.
"""

import logging
from copy import deepcopy
from typing import Any

from src.core.calendar import CalendarConverter
from src.core.entities import Entity
from src.core.temporal_constraints import (
    TemporalConstraint,
    anchor_precedes,
    validate_constraints,
)
from src.core.temporal_expression import ResolvedTemporalBounds
from src.core.temporal_state import ResolvedEntityState, apply_payload, validate_payload
from src.core.temporal_window import (
    TemporalValidity,
    TemporalWindow,
    resolve_temporal_window,
)

logger = logging.getLogger(__name__)


class TemporalResolver:
    """Computes entity state at time T based on a list of relations."""

    def resolve_entity_state(
        self,
        entity: Entity,
        relations: list[dict[str, Any]],
        time: float,
        converter: CalendarConverter | None = None,
        anchors: dict[str, ResolvedTemporalBounds] | None = None,
        constraints: list[TemporalConstraint] | None = None,
    ) -> ResolvedEntityState:
        """Compute the resolved state of an entity at a specific time.

        Args:
            entity: The base Entity object (contains static/default attributes).
            relations: List of relation dicts targeted at this entity.
                       Must include 'attributes' with 'valid_from', 'payload'.
            time: The timestamp (lore_date) to resolve at.
        Returns:
            The resolved description and attributes.

        """
        current_state = ResolvedEntityState(
            entity_id=entity.id,
            description=entity.description,
            attributes=dict(entity.attributes),
            description_source={"kind": "baseline"},
            attribute_sources={
                key: {"kind": "baseline"} for key in entity.attributes
            },
            absent_attribute_sources={},
        )

        # 2. Filter applicable relations
        applicable_relations = []
        windows = {}
        for rel in relations:
            attrs = rel.get("attributes", {})
            source_event_date = rel.get("source_event_date")
            window = resolve_temporal_window(
                attrs,
                source_event_date,
                source_event_attributes=rel.get("source_event_attributes"),
                source_event_id=rel.get("source_id"),
                converter=converter,
                anchors=anchors,
            )
            status = window.status_at(time)
            windows[rel.get("id", "")] = window
            # Unscoped legacy relations never supplied temporal payloads.
            if window.kind.value == "unbounded":
                continue
            if status == TemporalValidity.DEFINITE:
                applicable_relations.append(rel)
            elif status in {TemporalValidity.POSSIBLE, TemporalValidity.INDETERMINATE}:
                self._retain_possible_effect(current_state, rel, status, window.error)

        # Only commuting or chronologically ordered effects become certain state.
        constraints = constraints or []
        constraint_errors = validate_constraints(constraints, anchors)
        current_state.temporal_warnings.extend(constraint_errors)
        ambiguous_ids = (
            {rel["id"] for rel in applicable_relations}
            if constraint_errors
            else self._unordered_effects(applicable_relations, windows, constraints)
        )
        for rel in applicable_relations:
            if rel.get("id") in ambiguous_ids:
                self._retain_possible_effect(
                    current_state,
                    rel,
                    TemporalValidity.POSSIBLE,
                    "The order of dated changes is not known.",
                )
        active_sorted = sorted(
            (rel for rel in applicable_relations if rel.get("id") not in ambiguous_ids),
            key=lambda r: (
                windows[r.get("id", "")].start
                if windows[r.get("id", "")].start is not None
                else float("-inf"),
                self._sort_key(r),
            ),
        )
        active_sorted = self._order_constrained(active_sorted, constraints)

        # 4. Merge payloads
        for rel in active_sorted:
            if rel.get("source_event_date") is None:
                continue

            relation_attributes = rel.get("attributes", {})
            if "payload" not in relation_attributes:
                continue
            payload = relation_attributes["payload"]
            try:
                current_state = apply_payload(current_state, payload)
            except ValueError as exc:
                relation_id = rel.get("id", "<unknown>")
                raise ValueError(
                    f"Invalid temporal payload on relation {relation_id}: {exc}"
                ) from exc

            source = {
                "kind": "relation",
                "relation_id": rel["id"],
                "event_id": rel.get("source_id", ""),
                "event_name": rel.get("source_event_name", ""),
                "event_date": rel["source_event_date"],
            }
            if "description" in payload:
                current_state.description_source = source.copy()
            assert current_state.attribute_sources is not None
            assert current_state.absent_attribute_sources is not None
            for key in payload.get("unset_attributes", []):
                current_state.attribute_sources.pop(key, None)
                current_state.absent_attribute_sources[key] = source.copy()
            for key in payload.get("attributes", {}):
                current_state.attribute_sources[key] = source.copy()
                current_state.absent_attribute_sources.pop(key, None)

        self._refresh_candidate_baselines(current_state)
        return current_state

    @staticmethod
    def _refresh_candidate_baselines(state: ResolvedEntityState) -> None:
        """Candidates start with the resolved certain value, not an obsolete baseline."""
        for key, candidates in state.ambiguous_attributes.items():
            if candidates:
                candidates[0] = (
                    state.description
                    if key == "description"
                    else deepcopy(state.attributes.get(key))
                )

    @staticmethod
    def _order_constrained(
        relations: list[dict[str, Any]],
        constraints: list[TemporalConstraint],
    ) -> list[dict[str, Any]]:
        """Topologically order explicit chronology, retaining stable unrelated order."""
        if not constraints:
            return relations
        dependencies: dict[int, set[int]] = {i: set() for i in range(len(relations))}
        for index, first in enumerate(relations):
            for other, second in enumerate(relations):
                if (
                    index != other
                    and TemporalResolver._compare_constraints(
                        first, second, constraints
                    )
                    > 0
                ):
                    dependencies[index].add(other)
        ordered = []
        while dependencies:
            ready = next(
                (i for i, incoming in dependencies.items() if not incoming), None
            )
            if ready is None:
                raise ValueError("Cyclic chronology cannot produce a certain state")
            ordered.append(relations[ready])
            del dependencies[ready]
            for incoming in dependencies.values():
                incoming.discard(ready)
        return ordered

    @staticmethod
    def _compare_constraints(
        first: dict[str, Any],
        second: dict[str, Any],
        constraints: list[TemporalConstraint],
    ) -> int:
        a, b = f"event:{first.get('source_id')}", f"event:{second.get('source_id')}"
        if anchor_precedes(a, b, constraints):
            return -1
        if anchor_precedes(b, a, constraints):
            return 1
        return 0

    @staticmethod
    def _unordered_effects(
        relations: list[dict[str, Any]],
        windows: dict[str, TemporalWindow],
        constraints: list[TemporalConstraint],
    ) -> set[str]:
        """Do not resolve noncommuting coarse transitions with IDs or edit times."""

        def keys(relation: dict[str, Any]) -> set[str]:
            payload = relation.get("attributes", {}).get("payload", {})
            result = set(payload.get("attributes", {})) | set(
                payload.get("unset_attributes", [])
            )
            if "description" in payload:
                result.add("description")
            return result

        ambiguous: set[str] = set()
        for index, first in enumerate(relations):
            a = windows[first.get("id", "")]
            for second in relations[index + 1 :]:
                b = windows[second.get("id", "")]
                if first.get("attributes", {}).get("payload") == second.get(
                    "attributes", {}
                ).get("payload"):
                    continue
                if not (a.semantic or b.semantic) or not keys(first) & keys(second):
                    continue
                if TemporalResolver._compare_constraints(first, second, constraints):
                    continue
                a_start = a.start_bounds
                b_start = b.start_bounds
                a_min = a_start.hard_start if a_start else a.start
                a_max = a_start.hard_end if a_start else a.start
                b_min = b_start.hard_start if b_start else b.start
                b_max = b_start.hard_end if b_start else b.start
                if (
                    a_max is not None
                    and b_min is not None
                    and a_max <= b_min
                    and (a_min != a_max or a_max < b_min)
                ) or (
                    b_max is not None
                    and a_min is not None
                    and b_max <= a_min
                    and (b_min != b_max or b_max < a_min)
                ):
                    continue
                ambiguous.update((first["id"], second["id"]))
        return ambiguous

    @staticmethod
    def _retain_possible_effect(
        state: ResolvedEntityState,
        rel: dict[str, Any],
        status: TemporalValidity,
        error: str | None,
    ) -> None:
        """Keep uncertain mutations visible without applying them as facts."""
        payload = rel.get("attributes", {}).get("payload", {})
        validate_payload(payload)
        state.possible_effects.append(
            {
                "relation_id": rel.get("id", ""),
                "validity": status.value,
                "payload": deepcopy(payload),
                "provenance": {
                    "event_id": rel.get("source_id"),
                    "event_name": rel.get("source_event_name", ""),
                },
            }
        )
        if error:
            state.temporal_warnings.append(error)
        for key, value in payload.get("attributes", {}).items():
            candidates = state.ambiguous_attributes.setdefault(
                key, [deepcopy(state.attributes.get(key))]
            )
            if value not in candidates:
                candidates.append(deepcopy(value))
        for key in payload.get("unset_attributes", []):
            state.ambiguous_attributes.setdefault(
                key, [deepcopy(state.attributes.get(key))]
            ).append(None)
        if "description" in payload:
            state.ambiguous_attributes.setdefault(
                "description", [state.description]
            ).append(payload["description"])

    def _sort_key(self, relation: dict[str, Any]) -> tuple[float, int, float, str]:
        """Returns a sort key for deterministic application order.

        Tuple order: (ValidFrom, PriorityScore, ModifiedAt, ID)
        """
        attrs = relation.get("attributes", {})

        # 1. Time
        source_event_date = relation.get("source_event_date")
        window = resolve_temporal_window(attrs, source_event_date)
        valid_from = window.start if window.start is not None else float("-inf")

        # 2. Priority
        # event = 1, manual = 2 (Manual wins ties at same time)
        priority_val = attrs.get("priority", "event")
        priority_score = 2 if priority_val == "manual" else 1

        # 3. Modified At (creation/edit time)
        modified_at = attrs.get("modified_at", 0.0)

        # 4. ID
        rel_id = relation.get("id", "")

        return (valid_from, priority_score, modified_at, rel_id)
