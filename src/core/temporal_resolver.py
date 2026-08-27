"""Temporal Resolver Module.

Responsible for computing the state of an entity at a given point in time by aggregating
and merging relation-driven overrides.
"""

import logging
from typing import Any

from src.core.entities import Entity
from src.core.temporal_state import ResolvedEntityState, apply_payload
from src.core.temporal_window import resolve_temporal_window

logger = logging.getLogger(__name__)


class TemporalResolver:
    """Computes entity state at time T based on a list of relations."""

    def resolve_entity_state(
        self,
        entity: Entity,
        relations: list[dict[str, Any]],
        time: float,
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
        )

        # 2. Filter applicable relations
        applicable_relations = []
        for rel in relations:
            attrs = rel.get("attributes", {})
            source_event_date = rel.get("source_event_date")
            window = resolve_temporal_window(attrs, source_event_date)
            if window.is_active(time):
                applicable_relations.append(rel)

        # 3. Sort relations to determine application order
        # Sort keys:
        # 1. ValidFrom (Ascending) - History builds up
        # 2. Priority (Ascending) - Custom tie-breaker?
        #    Wait, in test we decided Manual (2) > Event (1).
        #    So (Time, Priority) works if we want Manual to win *at same time*.
        #    What if Manual is earlier? (10, 2) vs (20, 1).
        #    (10, 2) < (20, 1). So Event (20) applies LAST.
        #    This means later Events override earlier Manual fixes.
        #    This is consistent with "Time moves forward".
        active_sorted = sorted(applicable_relations, key=lambda r: self._sort_key(r))

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

        return current_state

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
