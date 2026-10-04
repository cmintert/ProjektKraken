"""Fresh, worker-owned reads for temporal entity verification and save results."""

from copy import deepcopy

from src.core.temporal_entity_checkpoint import TemporalEntityCheckpoint
from src.core.temporal_manager import TemporalManager
from src.services.db_service import DatabaseService


class TemporalEntitySnapshotService:
    """Build comparison checkpoints without using the UI's temporal cache."""

    def __init__(self, db_service: DatabaseService) -> None:
        """Use the caller's database on its owning thread and transaction."""
        self._db = db_service

    def build(self, entity_id: str, lore_time: float) -> TemporalEntityCheckpoint:
        """Read resolved state and baseline metadata from the same transaction."""
        entity = self._db.get_entity(entity_id)
        if entity is None:
            raise ValueError("Entity no longer exists")
        state = (
            TemporalManager(self._db)
            .get_entity_state_at(entity_id, lore_time)
            .to_dict()
        )
        return {
            "entity_id": entity_id,
            "lore_time": lore_time,
            "state": state,
            "baseline_metadata": deepcopy(
                {
                    "name": entity.name,
                    "type": entity.type,
                    "_tags": entity.attributes.get("_tags"),
                    "_sheet_layout": entity.attributes.get("_sheet_layout"),
                    "_summary_data": entity.attributes.get("_summary_data"),
                }
            ),
        }
