"""Worker-local component previews; a preview never authorizes a database write."""

from __future__ import annotations

import json
from dataclasses import replace
from time import perf_counter
from typing import Any

from src.core.event_timing.compiler import fingerprint
from src.core.event_timing.constraints import Cancel, checkpoint
from src.core.event_timing.presentation import endpoint_caption
from src.core.event_timing.projection import endpoint_signature, project_event
from src.core.event_timing.solver import resolve_world
from src.core.events import Event
from src.core.temporal_references import referenced_endpoints
from src.services.event_timing.affine_preview import (
    supports_translation,
    translated_preview,
)
from src.services.event_timing.movement import (
    MovementIndex,
    describe_offsets,
    movement_errors,
    movement_updates,
)
from src.services.event_timing.planning import converter_from_snapshot


def component_events(events: list[Event], identity: str) -> list[Event]:
    """Close whole Event owners over references and chronology, including rule owners."""
    neighbours: dict[str, set[str]] = {event.id: set() for event in events}
    for event in events:
        references = {
            node.removeprefix("event:").removesuffix(":end")
            for node in referenced_endpoints(event.attributes)
        }
        for reference in references:
            neighbours[event.id].add(reference)
            neighbours.setdefault(reference, set()).add(event.id)
    found, pending = set(), [identity]
    while pending:
        current = pending.pop()
        if current not in found:
            found.add(current)
            pending.extend(neighbours.get(current, set()) - found)
    return [event for event in events if event.id in found]


class MovementPreviewSession:
    """Cache baseline and indexes once; calculate only the complete affected component."""

    def __init__(self, payload: dict[str, Any], cancel: Cancel | None = None) -> None:
        """Decode full sources once on the calculation thread, never on a pointer event."""
        self.session = payload["session"]
        self.generation = payload["generation"]
        self.world_id = payload["world_id"]
        self.identity = payload["event_id"]
        self.converter = converter_from_snapshot(payload)
        events = [Event.from_dict(row) for row in json.loads(payload["events_json"])]
        checkpoint(cancel)
        if fingerprint(events, self.converter) != self.generation:
            raise ValueError("Timing changed since dragging began. Try again.")
        self.events = component_events(events, self.identity)
        self.before = resolve_world(self.events, self.converter, cancel)
        self.index = MovementIndex(self.events)
        self.baseline = {
            event.id: project_event(event, self.before).to_dict()
            for event in self.events
        }
        self.affine = not self.before.issues and supports_translation(
            self.events, self.index
        )

    def calculate(
        self, request: dict[str, Any], cancel: Cancel | None = None
    ) -> dict[str, Any]:
        """Return changed snapshots and a bounded caption, without plans or review payloads."""
        started = perf_counter()
        if (request["session"], request["generation"], request["world_id"]) != (
            self.session,
            self.generation,
            self.world_id,
        ):
            raise ValueError("Obsolete movement preview.")
        intent = {**request, "generation": self.before.fingerprint}
        updates = movement_updates(
            self.events, self.before, self.converter, intent, index=self.index
        )
        checkpoint(cancel)
        if self.affine:
            rows, date = translated_preview(
                self.index, self.baseline, updates, self.identity, request["mode"]
            )
            selected = self.index.originals[self.identity]
            if self.identity in updates:
                selected = replace(
                    selected, attributes=updates[self.identity]["attributes"]
                )
            return {
                "updated": _render_rows(rows),
                "caption": (
                    self.converter.format_datetime(date)
                    if self.converter
                    else f"{date:g} days"
                )
                + "\n"
                + describe_offsets(selected, self.events),
                "component_size": len(self.events),
                "calculation_ms": (perf_counter() - started) * 1000,
            }
        candidates = [
            replace(event, attributes=updates[event.id]["attributes"])
            if event.id in updates
            else event
            for event in self.events
        ]
        after = resolve_world(candidates, self.converter, cancel)
        errors = [issue.message for issue in after.issues]
        errors.extend(movement_errors(self.before, after, self.events))
        if errors:
            raise ValueError(next(iter(dict.fromkeys(errors))))
        rows = {}
        for event in candidates:
            row = project_event(event, after).to_dict()
            # Provenance is generation-specific, even on unaffected endpoints.
            old = self.baseline[event.id]
            if (row["lore_date"], row["lore_duration"], event.id in updates) != (
                old["lore_date"],
                old["lore_duration"],
                False,
            ):
                rows[event.id] = {
                    "lore_date": row["lore_date"],
                    "lore_duration": row["lore_duration"],
                    "temporal": row["attributes"].get("_temporal_v2"),
                }
        selected = next(event for event in candidates if event.id == self.identity)
        date_caption = endpoint_caption(
            endpoint_signature(after.endpoints[f"event:{self.identity}"]),
            self.converter,
            include_time=True,
        )
        caption = date_caption + "\n" + describe_offsets(selected, candidates)
        return {
            "updated": _render_rows(rows),
            "caption": caption,
            "component_size": len(self.events),
            "calculation_ms": (perf_counter() - started) * 1000,
        }


def _render_rows(rows: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Render snapshots carry geometry, never a cached joint-model capability."""
    for row in rows.values():
        metadata = row.get("temporal") or {}
        projection = metadata.get("projection", {})
        for side in ("start", "end"):
            endpoint = projection.get(side)
            if endpoint is not None:
                endpoint.pop("root", None)
                endpoint.pop("network", None)
    return rows
