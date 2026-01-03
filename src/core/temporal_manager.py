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
        Slot to handle event changes.
        Harder to know which entities are affected without querying.
        For Stage 0, we might leave this as a placeholder or
        implement a 'nuclear' option if needed.
        """
        # Placeholder for future logic
        pass

    def invalidate_entity(self, entity_id: str) -> None:
        """
        Clears all cached states for a specific entity.
        """
        # Remove all keys where entity_id matches
        keys_to_remove = [k for k in self._cache.keys() if k[0] == entity_id]
        for k in keys_to_remove:
            del self._cache[k]

        logger.debug(
            f"Invalidated cache for entity {entity_id} ({len(keys_to_remove)} entries)"
        )
