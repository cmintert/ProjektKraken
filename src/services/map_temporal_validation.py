"""Read-only diagnostics for map presence assertions."""

from src.core.analysis import IssueType, SeverityLevel, ValidationIssue
from src.core.map import VECTOR_LAYER_TYPES, Map, MapLayerNode
from src.core.temporal_context import TemporalResolutionContext
from src.core.temporal_window import resolve_temporal_window


def map_temporal_issues(
    maps: list[Map], context: TemporalResolutionContext
) -> list[ValidationIssue]:
    """Report unresolved and impossible authored map windows with stable identities."""
    anchors, converter = context.anchors(), context.converter()
    issues = []
    for map_obj in maps:
        if map_obj.layers is None:
            continue
        pending: list[MapLayerNode] = list(map_obj.layers.children)
        while pending:
            node = pending.pop()
            pending.extend(node.children)
            if node.layer_type not in VECTOR_LAYER_TYPES | {"group"}:
                continue
            window = resolve_temporal_window(
                {
                    **node.attributes,
                    "valid_from": node.start_date,
                    "valid_to": node.end_date,
                },
                converter=converter,
                anchors=anchors,
            )
            if not window.error and not window.is_empty:
                continue
            issues.append(
                ValidationIssue(
                    severity=SeverityLevel.WARNING,
                    issue_type=IssueType.INVALID_TEMPORAL_WINDOW,
                    object_id=map_obj.id,
                    object_type="map",
                    object_name=f"{map_obj.name}: {node.name}",
                    message=window.error
                    or "The layer's dates describe an empty interval.",
                    suggestion="Open Visibility dates for this map layer and review its event references.",
                    related_ids=[map_obj.id],
                    fingerprint=f"map-window:{map_obj.id}:{node.id}",
                )
            )
    return issues
