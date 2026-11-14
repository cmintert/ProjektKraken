"""Select authored evidence for generation without altering human World Context."""

from dataclasses import replace

from src.core.authoring_context import EntityAuthoringContext


def select_entity_evidence(
    context: EntityAuthoringContext, *, include_undated: bool
) -> EntityAuthoringContext:
    """Keep directed facts; never promote co-placement into a relationship."""
    selected = replace(context, shared_tags=(), shared_maps=(), co_appearances=())
    if context.mode == "all_history" or include_undated:
        return selected
    description = context.effective_description
    if description is not None and not (description.source or {}).get("event_id"):
        description = None
    return replace(
        selected,
        effective_description=description,
        attachments=(),
        map_appearances=(),
        tags=(),
        attributes=tuple(
            item for item in context.attributes if (item.source or {}).get("event_id")
        ),
    )
