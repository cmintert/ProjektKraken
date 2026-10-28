"""Deterministic strand identity for authored Follow Event timing references."""

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.events import Event

Endpoint = Literal["start", "end"]
DEPENDENCY_PALETTE_SIZE = 8


@dataclass(frozen=True)
class TimelineDependency:
    """A directed timing reference with an undirected connected-strand identity."""

    source_id: str
    source_endpoint: Endpoint
    target_id: str
    target_endpoint: Endpoint
    strand_id: str

    @property
    def palette_index(self) -> int:
        """Choose a process-independent slot without persisting derived strands."""
        digest = sha256(self.strand_id.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") % DEPENDENCY_PALETTE_SIZE


def _references(event: Event) -> list[tuple[str, Endpoint, str, Endpoint]]:
    try:
        definition = EventTimingDefinition.from_event(event)
    except (ValueError, TypeError, KeyError):
        return []
    references = []
    endpoints: tuple[tuple[Endpoint, EndpointDefinition | None], ...] = (
        ("start", definition.start),
        ("end", definition.end),
    )
    for target_endpoint, endpoint in endpoints:
        if endpoint is not None and endpoint.kind == "event":
            source = (endpoint.anchor_id or "").removeprefix("event:")
            if source != event.id:
                references.append(
                    (source, endpoint.endpoint, event.id, target_endpoint)
                )
    return references


def timeline_dependencies(events: Sequence[Event]) -> tuple[TimelineDependency, ...]:
    """Build components from all accepted events, independent of visible copies."""
    ids = {event.id for event in events}
    references = sorted(
        reference
        for event in events
        for reference in _references(event)
        if reference[0] in ids
    )
    neighbors: dict[str, set[str]] = {}
    for source, _, target, _ in references:
        neighbors.setdefault(source, set()).add(target)
        neighbors.setdefault(target, set()).add(source)
    strands: dict[str, str] = {}
    for identity in sorted(neighbors):
        if identity in strands:
            continue
        pending = [identity]
        strands[identity] = identity
        while pending:
            for neighbor in neighbors[pending.pop()]:
                if neighbor not in strands:
                    strands[neighbor] = identity
                    pending.append(neighbor)
    return tuple(
        TimelineDependency(source, source_end, target, target_end, strands[source])
        for source, source_end, target, target_end in references
    )
