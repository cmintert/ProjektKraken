"""Pure inspector projections of saved assertions; never mutate their snapshots."""

from dataclasses import dataclass
from typing import Any

from src.core.calendar import CalendarConverter
from src.core.graph_temporal import GraphTemporalMode, evaluate_graph_relation
from src.core.relation_presentation import overview_caption
from src.gui.widgets.relation_snapshots import distinct_relation_directions

ENTITY_GROUPS = (
    "Membership & roles",
    "Personal & family",
    "Places & possessions",
    "Events & actions",
    "Other connections",
    "References",
)
EVENT_GROUPS = (
    "Participants",
    "Locations",
    "Causes & consequences",
    "Other connections",
    "References",
)
BUILTIN_GROUPS = {
    "entity": {
        "member_of": "Membership & roles",
        "parent_of": "Personal & family",
        "owns": "Places & possessions",
        "located_at": "Places & possessions",
        "involved": "Events & actions",
        "participated_in": "Events & actions",
        "caused": "Events & actions",
    },
    "event": {
        "involved": "Participants",
        "participated_in": "Participants",
        "located_at": "Locations",
        "caused": "Causes & consequences",
    },
}


@dataclass(frozen=True)
class ConnectionRow:
    """Read-only rendering metadata beside the unmodified command snapshot."""

    snapshot: dict[str, Any]
    group: str
    direction: str
    other_id: str
    title: str
    meaning: str
    assertion: str
    timing: str

    @property
    def text(self) -> str:
        """Return one-line, accessible row text including all relevant status."""
        return " ".join(f"{self.assertion} · {self.timing}".split())


def connection_timing(
    snapshot: dict[str, Any], time: float | None, calendar: CalendarConverter | None
) -> str:
    """Reuse temporal evaluation without imposing graph visibility filters."""
    attrs = snapshot.get("attributes") or {}
    timed = "temporal" in attrs or any(key.startswith("valid_") for key in attrs)
    if not timed:
        summary = "Timing: not specified"
    elif time is None or calendar is None:
        summary = "Timing unknown"
    else:
        evaluated = evaluate_graph_relation(
            snapshot, time, calendar, GraphTemporalMode.ALL_RELATIONS
        )
        summary = str((evaluated or {}).get("temporal_summary", "Timing unknown"))
    payload = attrs.get("payload") or {}
    if isinstance(payload, dict) and (
        payload.get("attributes")
        or payload.get("unset_attributes")
        or "description" in payload
    ):
        summary += " · State changes"
    return summary


def project_connections(
    outgoing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    kind: str,
    object_id: str,
    name: str,
    time: float | None = None,
    calendar: CalendarConverter | None = None,
    categories: dict[str, str] | None = None,
) -> list[ConnectionRow]:
    """Classify only explicit meanings; target object kinds do not imply meaning.

    Categories are optional presentation inputs, not a vocabulary storage schema.
    Unknown explicit categories deliberately fall back to Other connections.
    """
    groups = EVENT_GROUPS if kind == "event" else ENTITY_GROUPS
    rows = []
    directions = distinct_relation_directions(outgoing, incoming)
    for direction, snapshots in zip(("outgoing", "incoming"), directions):
        for snapshot in snapshots:
            predicate = snapshot.get("rel_type", "related")
            source = snapshot.get("source_name") or (
                name if direction == "outgoing" else snapshot.get("source_id", "?")
            )
            target = snapshot.get("target_name") or (
                name if direction == "incoming" else snapshot.get("target_id", "?")
            )
            other_id = snapshot.get(
                "target_id" if direction == "outgoing" else "source_id", object_id
            )
            category = (categories or {}).get(
                predicate, BUILTIN_GROUPS[kind].get(predicate, "Other connections")
            )
            group = category if category in groups else "Other connections"
            if predicate == "mentions":
                group = "References"
            meaning = overview_caption(predicate)
            rows.append(
                ConnectionRow(
                    snapshot,
                    group,
                    direction,
                    other_id,
                    str(target if direction == "outgoing" else source),
                    meaning,
                    f"{source} → {meaning} → {target}",
                    connection_timing(snapshot, time, calendar),
                )
            )
    return rows
