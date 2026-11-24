"""Read the world vocabulary through the existing settings repository."""

from dataclasses import replace
from sqlite3 import Connection

from src.core.authoring_context import ContextRelation
from src.core.relation_vocabulary import (
    VOCABULARY_KEY,
    Vocabulary,
    parse_vocabulary,
    resolve_wording,
)
from src.services.repositories.settings_repository import SettingsRepository


def read_vocabulary(connection: Connection) -> dict[str, dict[str, str]]:
    """Return detached wording without initializing or repairing the setting."""
    return parse_vocabulary(SettingsRepository(connection).raw(VOCABULARY_KEY))


def with_display_text(
    relation: ContextRelation, root_id: str, vocabulary: Vocabulary
) -> ContextRelation:
    """Add configured wording to an otherwise unchanged context relation."""
    if relation.rel_type not in vocabulary:
        return relation
    wording = resolve_wording(
        {
            "id": relation.id,
            "rel_type": relation.rel_type,
            "source_id": relation.source.id,
            "target_id": relation.target.id,
            "source_name": relation.source.name,
            "target_name": relation.target.name,
        },
        vocabulary,
        incoming=root_id == relation.target.id and root_id != relation.source.id,
    )
    return replace(relation, display_text=wording.sentence or wording.assertion)
