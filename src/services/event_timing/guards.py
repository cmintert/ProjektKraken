"""Forward-mutation guards shared by existing command entry points."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from src.core.command import CommandResult
from src.core.event_timing.definitions import EVENT_TIMING_SCHEMA, EventTimingDefinition
from src.core.events import Event
from src.services.db_service import DatabaseService

applying_timing_plan: ContextVar[bool] = ContextVar(
    "applying_timing_plan", default=False
)


def is_applying_plan() -> bool:
    """Read the command-local authorization, never a caller-supplied boolean."""
    return applying_timing_plan.get()


def has_calculated_events(events: list[Event]) -> bool:
    """Whether this world uses the versioned joint timing authoring contract."""
    return any(
        isinstance(event.attributes.get("_temporal_v2"), dict)
        and event.attributes["_temporal_v2"].get("schema") == EVENT_TIMING_SCHEMA
        for event in events
    )


def require_plan(
    db: DatabaseService, current: Event | None, proposed: Event
) -> CommandResult | None:
    """Reject raw timing mutations once dependent timing needs reviewed planning."""
    if is_applying_plan():
        return None
    try:
        changed = current is None or EventTimingDefinition.from_event(
            current
        ) != EventTimingDefinition.from_event(proposed)
    except (ValueError, TypeError, KeyError) as exc:
        if current is None or (
            current.lore_date,
            current.lore_duration,
            current.attributes.get("_temporal_v2"),
        ) != (
            proposed.lore_date,
            proposed.lore_duration,
            proposed.attributes.get("_temporal_v2"),
        ):
            return CommandResult(
                False, f"Invalid Event timing: {exc}", command_name="EventTiming"
            )
        changed = current is None or current.attributes.get(
            "_temporal_v2"
        ) != proposed.attributes.get("_temporal_v2")
    from src.services.temporal_dependency_service import event_temporal_dependencies

    dependencies = event_temporal_dependencies(db, proposed.id) if changed else []
    if changed and (
        has_calculated_events([proposed, *db.get_all_events()]) or dependencies
    ):
        return CommandResult(
            success=False,
            message="Calculate and review the timing changes before applying them.",
            command_name="EventTiming",
            data={"timing_review_required": True},
        )
    return None


def require_world_plan(
    db: DatabaseService, recorded: dict[str, Any] | None = None
) -> CommandResult | None:
    """Guard chronology and calendar changes that can reshape inferred dates."""
    if is_applying_plan():
        return None
    if recorded is not None:
        from src.services.event_timing.history import check_recorded_calendar

        check_recorded_calendar(db, recorded)
        return None
    events = db.get_all_events()
    semantic = has_calculated_events(events) or any(
        isinstance(event.attributes.get("_temporal_v2"), dict)
        and event.attributes["_temporal_v2"].get("expression")
        for event in events
    )
    if not is_applying_plan() and semantic:
        return CommandResult(
            success=False,
            message="This world uses calculated Event dates. Prepare its timing changes first.",
            command_name="EventTiming",
            data={"timing_review_required": True},
        )
    return None


def preserve_chronology(attributes: dict[str, Any], current: Event) -> dict[str, Any]:
    """Merge the worker's independently edited chronology without downgrading schema."""
    from copy import deepcopy

    result = deepcopy(attributes)
    old_metadata = current.attributes.get("_temporal_v2", {})
    if not isinstance(old_metadata, dict):
        return result
    stored = old_metadata.get("constraints", [])
    if stored:
        metadata = result.setdefault("_temporal_v2", {"schema": 1})
        metadata["constraints"] = deepcopy(stored)
    elif isinstance(result.get("_temporal_v2"), dict):
        result["_temporal_v2"].pop("constraints", None)
    return result


def preserve_unchanged_projection(current: Event, proposed: Event) -> Event:
    """A prose save cannot replace derived coordinates with editor placeholders."""
    from dataclasses import replace

    try:
        same = EventTimingDefinition.from_event(
            current
        ) == EventTimingDefinition.from_event(proposed)
    except (ValueError, TypeError, KeyError):
        same = current.attributes.get("_temporal_v2") == proposed.attributes.get(
            "_temporal_v2"
        )
    if same:
        return replace(
            proposed, lore_date=current.lore_date, lore_duration=current.lore_duration
        )
    return proposed
