"""Graph mode policies over the shared temporal evaluator."""

from enum import Enum
from typing import Any

from src.core.calendar import CalendarConverter
from src.core.temporal_expression import ResolvedTemporalBounds
from src.core.temporal_window import TemporalValidity, resolve_temporal_window


class GraphTemporalMode(str, Enum):
    """Distinct current-state and historical knowledge views."""

    AT_PLAYHEAD = "at_playhead"
    HISTORY_TO_PLAYHEAD = "history_to_playhead"
    ALL_RELATIONS = "all_relations"


def evaluate_graph_relation(
    relation: dict[str, Any],
    lore_time: float,
    converter: CalendarConverter | None,
    mode: GraphTemporalMode,
    anchors: dict[str, ResolvedTemporalBounds] | None = None,
) -> dict[str, Any] | None:
    """Return an evaluated snapshot or exclude an inapplicable temporal fact."""
    attrs = relation.get("attributes", {})
    spec = attrs.get("temporal", {})
    scoped = "temporal" in attrs or any(
        attrs.get(key) is not None
        for key in (
            "valid_from",
            "valid_to",
            "valid_from_event",
            "valid_to_event",
            "valid_at_event",
        )
    )
    behavior = (
        spec.get(
            "behavior",
            "occurrence"
            if attrs.get("valid_at_event")
            else "stateful"
            if scoped
            else "atemporal",
        )
        if isinstance(spec, dict)
        else "stateful"
    )
    window = resolve_temporal_window(
        attrs,
        relation.get("source_event_date"),
        source_event_attributes=relation.get("source_event_attributes"),
        source_event_id=relation.get("source_id"),
        converter=converter,
        anchors=anchors,
    )
    status = (
        TemporalValidity.DEFINITE
        if behavior == "atemporal"
        else window.status_at(lore_time)
    )
    established = window.start_bounds.hard_end if window.start_bounds else window.start
    historical = (
        behavior in {"historical", "occurrence"}
        and established is not None
        and lore_time >= established
        and not window.error
    )
    if mode == GraphTemporalMode.AT_PLAYHEAD:
        if (
            status == TemporalValidity.INACTIVE
            and not (historical and behavior == "historical")
        ) or behavior == "occurrence":
            return None
    elif mode == GraphTemporalMode.HISTORY_TO_PLAYHEAD:
        if (
            behavior != "atemporal"
            and window.start is not None
            and lore_time < window.start
        ):
            return None
    captions = {
        TemporalValidity.DEFINITE: "Active at the playhead",
        TemporalValidity.POSSIBLE: "May be active; exact date unknown",
        TemporalValidity.INACTIVE: "Not active at the playhead",
        TemporalValidity.INDETERMINATE: "Timing is not yet known",
    }
    summary = captions[status]
    if historical:
        summary = "Historical fact established by the playhead"
    for caption, boundary in (
        ("starts", window.start_bounds),
        ("ends", window.end_bounds),
    ):
        if boundary and boundary.label:
            summary += f"; {caption}: {boundary.label}"
    source_attrs = relation.get("source_event_attributes") or {}
    metadata = source_attrs.get("_temporal_v2", {})
    original = metadata.get("expression", {}).get("original_text")
    if original:
        summary += f"; source event: {original}"
    return {
        **relation,
        "validity_status": status.value,
        "temporal_behavior": behavior,
        "temporal_summary": summary,
        "temporal_diagnostics": [window.error] if window.error else [],
    }
