"""Worker-owned validation of authored temporal edits."""

from typing import Any

from src.core.calendar import CalendarConverter
from src.core.temporal_anchors import resolve_event_anchors
from src.core.temporal_editing import edit_error
from src.core.temporal_window import resolve_temporal_window
from src.services.db_service import DatabaseService


def validate_temporal_edit(
    db: DatabaseService, attributes: dict[str, Any], source_id: str | None = None
) -> None:
    """Reject impossible edits while allowing explicitly unresolved references."""
    if "temporal" not in attributes:
        return
    config = db.get_active_calendar_config()
    converter = CalendarConverter(config) if config else None
    events = db.get_all_events()
    source = next((event for event in events if event.id == source_id), None)
    window = resolve_temporal_window(
        attributes,
        source.lore_date if source else None,
        source_event_id=source_id,
        source_event_attributes=source.attributes if source else None,
        converter=converter,
        anchors=resolve_event_anchors(events, converter),
    )
    error = edit_error(window)
    if error:
        raise ValueError(error)
