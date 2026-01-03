"""
Temporal Manager Module.

Acts as the coordinator between the Database, signals, and the TemporalResolver.
Manages caching of resolved states to ensure performance.
"""

import logging
from typing import Any, Dict, Tuple

from PySide6.QtCore import QObject, Slot

from src.core.temporal_resolver import TemporalResolver

logger = logging.getLogger(__name__)


class TemporalManager(QObject):
    """
    Manages temporal state resolution, catching, and invalidation.
    """

    def __init__(self, db_service: Any) -> None:
        """
        Args:
            db_service: Reference to DatabaseService to fetch entities/relations.
        """
        super().__init__()
        self._db = db_service
        self._resolver = TemporalResolver()

        # Cache structure: { (entity_id, time): state_dict }
        # This is a naive cache. In reality, state is valid for a RANGE.
        # But for MVP playhead scrubbing, exact match or simple LRU is
        # a starting point.
        self._cache: Dict[Tuple[str, float], Dict[str, Any]] = {}

    def get_entity_state_at(self, entity_id: str, time: float) -> Dict[str, Any]:
        """
        Returns the resolved state of an entity at a specific time.
        Uses cache if available.
        """
        # 1. Check Cache
        cache_key = (entity_id, time)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 2. Fetch Data
        entity = self._db.get_entity(entity_id)
        if not entity:
            logger.warning(f"TemporalManager: Entity {entity_id} not found.")
            return {}

        # Fetch ALL incoming relations for this entity
        # Optimization Todo: Fetch only relations relevant to time window?
        # For now, fetching all is safer for correctness.
        relations = self._db.get_incoming_relations(entity_id)

        # 3. Resolve
        state = self._resolver.resolve_entity_state(entity, relations, time)

        # 4. Cache and Return
        self._cache[cache_key] = state
        return state

    @Slot(str, str, str)
    def on_relation_changed(self, rel_id: str, source_id: str, target_id: str) -> None:
        """
        Slot to handle relation changes (add/edit/delete).
        Invalidates cache for the target entity.
        """
        self.invalidate_entity(target_id)

    @Slot(str)
    def on_event_changed(self, event_id: str) -> None:
        """
        Slot to handle event changes (e.g., date moved, event deleted).

        When an event changes, all entities linked via relations from that
        event need their caches invalidated, as their resolved states may
        have changed.

        Args:
            event_id: ID of the event that changed.
        """
        # Query all relations where this event is the source
        try:
            relations = self._db.get_relations(event_id)

            # Extract unique target entities
            affected_entities = {rel["target_id"] for rel in relations}

            # Invalidate cache for each affected entity
            for entity_id in affected_entities:
                self.invalidate_entity(entity_id)

            if affected_entities:
                logger.debug(
                    f"Event {event_id} changed: invalidated {len(affected_entities)} "
                    f"entities"
                )
        except Exception as e:
            logger.error(f"Error invalidating on event change {event_id}: {e}")

    def invalidate_entity(self, entity_id: str) -> None:
        """
        Clears all cached states for a specific entity.

        Args:
            entity_id: ID of the entity to invalidate.
        """
        # Remove all keys where entity_id matches
        keys_to_remove = [k for k in self._cache.keys() if k[0] == entity_id]
        for k in keys_to_remove:
            del self._cache[k]

        logger.debug(
            f"Invalidated cache for entity {entity_id} ({len(keys_to_remove)} entries)"
        )

    def clear_all_cache(self) -> None:
        """
        Nuclear option: Clears ALL cached states.

        Useful for global changes that might affect many entities
        (e.g., changing calendar system, bulk date adjustments).
        """
        cache_size = len(self._cache)
        self._cache.clear()
        logger.info(f"Nuclear cache clear: removed {cache_size} entries")
