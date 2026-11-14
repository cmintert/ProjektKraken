"""Capture experiment inputs on the live database owner's thread."""

from typing import Any

from src.core.ai_generation import AIGenerationPreferences
from src.core.mcp_access import McpFailure
from src.core.temporal_presentation import event_temporal_presentation
from src.services.db_service import DatabaseService
from src.services.mcp_contracts import check_preconditions
from src.services.mcp_read_service import McpReadService, read_guard
from src.services.mcp_temporal import calendar_converter


def capture_experiment(
    db: DatabaseService,
    request: dict[str, Any],
) -> dict[str, Any]:
    """Read saved subject/preferences without exporting private database paths."""
    args = request["arguments"]
    if args.get("_verify"):
        return {"revision": McpReadService.revision(db)}
    kind = args.get("kind")
    if kind not in {"entity", "event"}:
        raise McpFailure("INVALID_INPUT")
    with read_guard(db.require_connection(), lambda: False):
        revision = McpReadService.revision(db)
        check_preconditions(args, request, revision)
        subject = (
            db.get_entity(args["target_id"])
            if kind == "entity"
            else db.get_event(args["target_id"])
        )
        if subject is None:
            raise McpFailure("NOT_FOUND")
        preferences = AIGenerationPreferences.from_dict(
            db.get_ai_generation_preferences() or {}
        )
        calendar = db.get_active_calendar_config()
        caption = ""
        if kind == "event":
            event = db.get_event(args["target_id"])
            if event is not None:
                caption = event_temporal_presentation(
                    event, calendar_converter(db)
                ).start.caption
        return {
            "revision": revision,
            "subject": subject.to_dict(),
            "preferences": preferences.to_dict(),
            "lore_date_caption": caption,
            "month_names": [month.name for month in calendar.months]
            if calendar
            else [],
        }
