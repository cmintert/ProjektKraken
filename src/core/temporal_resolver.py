"""
Temporal Resolver Module.

Responsible for computing the state of an entity at a given point in time
by aggregating and merging relation-driven overrides.
"""

import logging
from typing import Any, Dict, List, Tuple

from src.core.entities import Entity

logger = logging.getLogger(__name__)


class TemporalResolver:
    """
    Computes entity state at time T based on a list of relations.
    """

    def resolve_entity_state(
        self,
        entity: Entity,
        relations: List[Dict[str, Any]],
        time: float,
        include_base_state: bool = True,
    ) -> Dict[str, Any]:
        """
        Computes the merged state of an entity at a specific time.

        Args:
            entity: The base Entity object (contains static/default attributes).
            relations: List of relation dicts targeted at this entity.
                       Must include 'attributes' with 'valid_from', 'payload'.
            time: The timestamp (lore_date) to resolve at.
            include_base_state: If True, starts with entity.attributes.
                                If False, returns only the temporal overrides.

        Returns:
            Dict[str, Any]: The merged dictionary of attributes.
        """
        # 1. Start with base state
        current_state = entity.attributes.copy() if include_base_state else {}

        # 2. Filter applicable relations
        applicable_relations = []
        for rel in relations:
            attrs = rel.get("attributes", {})
            source_event_date = rel.get("source_event_date")

            # Dynamic Timing Logic
            if attrs.get("valid_from_event") is True and source_event_date is not None:
                valid_from = float(source_event_date)
            else:
                valid_from = attrs.get("valid_from")

            if attrs.get("valid_to_event") is True and source_event_date is not None:
                valid_to = float(source_event_date)
            else:
                valid_to = attrs.get("valid_to")

            # Skip if no temporal data
            if valid_from is None:
                continue

            # Check time bounds
            # active if valid_from <= time AND (valid_to is None OR valid_to > time)
            if valid_from <= time:
                if valid_to is None or valid_to > time:
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
            payload = rel.get("attributes", {}).get("payload", {})
            if not payload:
                continue

            self._merge_payload(current_state, payload)

        return current_state

    def _sort_key(self, relation: Dict[str, Any]) -> Tuple[float, int, float, str]:
        """
        Returns a sort key for deterministic application order.
        Tuple order: (ValidFrom, PriorityScore, ModifiedAt, ID)
        """
        attrs = relation.get("attributes", {})

        # 1. Time
        source_event_date = relation.get("source_event_date")
        if attrs.get("valid_from_event") is True and source_event_date is not None:
            valid_from = float(source_event_date)
        else:
            valid_from = attrs.get("valid_from", float("-inf"))

        # 2. Priority
        # event = 1, manual = 2 (Manual wins ties at same time)
        priority_val = attrs.get("priority", "event")
        priority_score = 2 if priority_val == "manual" else 1

        # 3. Modified At (creation/edit time)
        modified_at = attrs.get("modified_at", 0.0)

        # 4. ID
        rel_id = relation.get("id", "")

        return (valid_from, priority_score, modified_at, rel_id)

    def _merge_payload(self, state: Dict[str, Any], payload: Dict[str, Any]) -> None:
        """
        Merges a payload into the state.
        Currently implements a shallow merge (overwrite).
        """
        for key, value in payload.items():
            state[key] = value
