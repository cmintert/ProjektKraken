"""Combine a detached GUI observation with saved worker-owned world time."""

import math
from typing import Any

from src.core.calendar import CalendarConverter
from src.services.db_service import DatabaseService
from src.services.repositories.calendar_repository import CalendarRepository
from src.services.repositories.meta_repository import MetaRepository


def time_context(db: DatabaseService, request: dict[str, Any]) -> dict[str, Any]:
    """Never confuse world Now, a live view coordinate and the system clock."""
    view = request.get("view_context", {})
    connection = db.require_connection()
    config = CalendarRepository(connection).get_active()
    converter = CalendarConverter(config) if config else None

    def coordinate(value: Any, source: str) -> dict[str, Any]:
        valid = type(value) in {int, float} and math.isfinite(value)
        caption = converter.format_datetime(value) if valid and converter else None
        return {
            "lore_day": value if valid else None,
            "available": valid,
            "caption": caption,
            "source": source,
            "calendar_id": config.id if config else None,
            "unavailable_reason": None if valid else "TIME_VALUE_UNAVAILABLE",
        }

    return {
        "world_now": coordinate(
            MetaRepository(connection).get_current_time(), "saved_world"
        ),
        "displayed_world_now": coordinate(view.get("world_now"), "live_view"),
        "playhead": coordinate(view.get("playhead"), "live_view"),
        "view_version": view.get("view_version"),
        "observed_at_utc": view.get("observed_at_utc"),
        "system_time": view.get("system_time"),
        "calendar_available": config is not None,
        "calendar_id": config.id if config else None,
        "calendar_source": "saved_active_calendar",
        "provenance": {"kind": "saved_world_and_observed_view"},
    }
