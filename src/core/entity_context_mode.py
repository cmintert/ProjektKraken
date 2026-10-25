"""Read-only Entity context modes, independent of presentation and storage."""

from enum import Enum


class EntityContextMode(str, Enum):
    """Select current knowledge, bounded history, or the durable overview."""

    AT_PLAYHEAD = "at_playhead"
    HISTORY_TO_PLAYHEAD = "history_to_playhead"
    ALL_HISTORY = "all_history"


ENTITY_CONTEXT_LABELS = {
    EntityContextMode.AT_PLAYHEAD: "At playhead",
    EntityContextMode.HISTORY_TO_PLAYHEAD: "History to playhead",
    EntityContextMode.ALL_HISTORY: "All history",
}
