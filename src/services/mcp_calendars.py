"""Exact, paged saved calendar definitions from the worker-owned world."""

from typing import Any

from src.core.calendar import CalendarConfig
from src.core.mcp_access import McpFailure
from src.services.db_service import DatabaseService
from src.services.mcp_sections import Continuation, page_limit, section_page
from src.services.repositories.calendar_repository import CalendarRepository


def calendar_read(
    db: DatabaseService,
    request: dict[str, Any],
    revision: str,
    resume: Continuation,
    remember: Continuation,
) -> dict[str, Any]:
    """Read only calendars in this world, with the standard cursor binding."""
    args = request["arguments"]
    limit = page_limit(args)
    after = resume(args, request, revision)
    data: dict[str, Any]
    if request["tool"] == "list_calendars":
        rows = list(
            db.require_connection().execute(
                "SELECT id,name,is_active,created_at,modified_at FROM calendar_config "
                "WHERE id>? ORDER BY id LIMIT ?",
                (after or "", limit + 1),
            )
        )
        more, rows = len(rows) > limit, rows[:limit]
        data = {
            "rows": [{**dict(row), "is_active": bool(row["is_active"])} for row in rows]
        }
        continuation = rows[-1]["id"] if more else None
    else:
        config = selected_calendar(db, args.get("calendar_id"))
        value = _section(config, args)
        data, continuation = section_page(value, after or 0, limit)
        data["calendar_id"] = config.id
    data.update(
        done=continuation is None,
        partial=continuation is not None,
        next_cursor=remember(continuation, args, request, revision)
        if continuation is not None
        else None,
        provenance={
            "kind": "saved_calendar",
            "section": args.get("section", "inventory"),
        },
    )
    return data


def selected_calendar(db: DatabaseService, identifier: Any = None) -> CalendarConfig:
    """Default only to an explicitly active saved calendar, never a fallback."""
    repository = CalendarRepository(db.require_connection())
    if identifier is not None and (not isinstance(identifier, str) or not identifier):
        raise McpFailure("INVALID_INPUT")
    config = (
        repository.get(identifier)
        if identifier is not None
        else repository.get_active()
    )
    if config is None:
        raise McpFailure(
            "NOT_FOUND",
            "NO_ACTIVE_CALENDAR" if identifier is None else "CALENDAR_NOT_FOUND",
        )
    return config


def _section(config: CalendarConfig, args: dict[str, Any]) -> Any:
    """Expose authored definitions and explicit index/precedence conventions."""
    section = args.get("section", "summary")
    if section == "summary":
        return {
            "id": config.id,
            "name": config.name,
            "epoch_name": config.epoch_name,
            "is_active": config.is_active,
            "month_count": len(config.months),
            "year_variant_count": len(config.year_variants),
            "leap_rule_count": len(config.leap_year_rules),
            "month_index_base": 0,
            "calendar_date_month_day_base": 1,
            "rule_precedence": "first_matching_year_variant_replaces_months_and_skips_leap_rules; otherwise_add_all_applicable_leap_rules",
        }
    values = config.to_dict()
    if section in {"months", "week", "leap_year_rules", "year_variants"}:
        return values[section]
    if section in {"week_day_names", "week_day_abbreviations"}:
        return values["week"][section.removeprefix("week_")]
    if section == "year_variant_summaries":
        return [
            {
                "variant_index": index,
                "year": variant.year,
                "month_count": len(variant.months),
            }
            for index, variant in enumerate(config.year_variants)
        ]
    if section == "year_variant_months":
        index = args.get("variant_index")
        if type(index) is not int or not 0 <= index < len(config.year_variants):
            raise McpFailure("INVALID_INPUT")
        return [month.to_dict() for month in config.year_variants[index].months]
    raise McpFailure("INVALID_INPUT")
