"""Retained neighboring-region drafts and acknowledgement-driven creation."""

from __future__ import annotations

import copy
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from src.commands.base_command import BaseCommand, CommandResult
from src.commands.composite_command import CompositeCommand
from src.commands.entity_commands import CreateEntityCommand
from src.commands.event_commands import CreateEventCommand
from src.commands.neighbor_region_command import CreateNeighborRegionCommand
from src.core.feature_geometry_state import (
    FeatureGeometryState,
    resolve_feature_geometry,
)
from src.core.marker import Marker
from src.core.region_geometry import (
    CutResult,
    Geometry,
    RegionPolygon,
    cut_region,
    feature_anchor,
)
from src.gui.dialogs.map_object_picker_dialog import MapObjectChoice
from src.gui.widgets.map.feature_items import RegionItem
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.map.neighbor_region_controls import (
    NeighborRegionControls,
    NeighborStage,
)


@dataclass
class NeighborRegionPorts:
    """Explicit main-thread UI and command dependencies, without a window/service."""

    view: MapGraphicsView
    controls: NeighborRegionControls
    map_id: Callable[[], str | None]
    world_id: Callable[[], str]
    date: Callable[[], float]
    format_date: Callable[[float], str]
    choose_object: Callable[[], MapObjectChoice | None]
    create_entity: Callable[[dict[str, Any]], CreateEntityCommand]
    create_event: Callable[[dict[str, Any]], CreateEventCommand]
    submit: Callable[[BaseCommand], None]
    begin_drawing: Callable[[], None]
    set_date: Callable[[float], None]
    transition: Callable[[str, Callable[[], None]], None]
    reload_map: Callable[[str], None] = lambda _map_id: None
    feedback: Callable[[str], None] = lambda _message: None
    pause_playback: Callable[[], None] = lambda: None
    refresh_source: Callable[[str], None] = lambda _map_id: None


@dataclass
class _Draft:
    map_id: str
    world_id: str
    source_id: str
    object_id: str
    label: str
    date: float
    source: Geometry
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    result: CutResult | None = None
    accepted: Geometry | None = None
    pending: str | None = None
    stale: bool = False


class NeighborRegionCoordinator(QObject):
    """Own a frozen source and keep the drawing until the worker accepts it."""

    transition_finished = Signal(dict)

    def __init__(
        self, ports: NeighborRegionPorts, parent: QObject | None = None
    ) -> None:
        """Bind local actions; application composition supplies saved snapshots."""
        super().__init__(parent)
        self.ports = ports
        self._draft: _Draft | None = None
        self._stage: NeighborStage = "closed"
        self._time_transition_pending = False
        self._choosing_object = False
        self._markers: dict[str, list[dict[str, Any]]] = {}
        self._states: dict[str, list[FeatureGeometryState]] = {}
        ports.view.neighbor_region_requested.connect(self.start)
        ports.view.drawing_proposed.connect(self.preview)
        ports.controls.preview_requested.connect(self.preview)
        ports.controls.accept_requested.connect(self.accept_result)
        ports.controls.back_requested.connect(self.back_to_drawing)
        ports.controls.save_requested.connect(self.save)
        ports.controls.cancel_requested.connect(self.discard_for_transition)

    def guard_playhead(self, date: float) -> bool:
        """Restore the draft's date before asking the shared transition guard."""
        d = self._draft
        if d is None or date == d.date:
            return True
        self.ports.pause_playback()
        self.ports.set_date(d.date)
        if not self._time_transition_pending:
            self._time_transition_pending = True
            choosing_object = self._choosing_object

            def resolve() -> None:
                self._time_transition_pending = False
                if self._draft is not d:
                    return
                # Raw timeline fanout has now finished; restore every view before
                # opening a modal decision, rather than leaving mixed dates.
                self.ports.set_date(d.date)
                if choosing_object:
                    return
                self.ports.transition(
                    "change the viewing date",
                    lambda: self.ports.set_date(date),
                )

            QTimer.singleShot(0, self, resolve)
        return False

    @Slot(str, list)
    def on_markers_ready(self, map_id: str, markers: list[dict[str, Any]]) -> None:
        """Retain serializable authoritative input without querying the database."""
        self._markers[map_id] = copy.deepcopy(markers)
        self._check_source()

    @Slot(str, list)
    def on_states_ready(self, map_id: str, states: list[dict[str, Any]]) -> None:
        """Update dated source geometry without silently accepting a new preview."""
        self._states[map_id] = [FeatureGeometryState.from_dict(s) for s in states]
        self._check_source()

    def _source(
        self, map_id: str, object_id: str, date: float
    ) -> tuple[Marker, Geometry] | None:
        snapshot = next(
            (
                s
                for s in self._markers.get(map_id, [])
                if s["object_id"] == object_id and s.get("feature_type") == "region"
            ),
            None,
        )
        if snapshot is None:
            return None
        marker = Marker.from_dict(snapshot)
        states = [s for s in self._states.get(map_id, []) if s.marker_id == marker.id]
        return marker, resolve_feature_geometry(marker, states, date).geometry

    @Slot(str)
    def start(self, object_id: str) -> None:
        """Capture the displayed source after the shared feature guard accepts."""
        p = self.ports
        if self._draft is not None or not p.map_id():
            return
        item = p.view.feature_items.get(object_id)
        if (
            not isinstance(item, RegionItem)
            or not item.isVisible()
            or item.is_temporal_ghost
        ):
            return
        source = self._source(str(p.map_id()), object_id, p.date())
        if source is None:
            return
        marker, geometry = source
        try:
            RegionPolygon.from_geometry(geometry).validated()
        except ValueError as exc:
            p.feedback(f"Cannot use this source region: {exc}")
            return
        p.begin_drawing()
        self._draft = _Draft(
            str(p.map_id()),
            p.world_id(),
            marker.id,
            object_id,
            marker.label or "Region",
            p.date(),
            copy.deepcopy(geometry),
        )
        p.view._drawing_tool.retain_draft = True
        self._present(
            "drawing", "Draw an outline overlapping the source, then preview."
        )
        p.view.setFocus()

    def _present(
        self, stage: NeighborStage, message: str, *, ready: bool = False
    ) -> None:
        self._stage = stage
        d = self._draft
        context = (
            f"Neighbor of {d.label} · {self.ports.format_date(d.date)} · "
            "Source unchanged"
            if d
            else ""
        )
        self.ports.controls.present(stage, context, message, ready=ready)

    @Slot()
    @Slot(object)
    def preview(self, _geometry: object = None) -> None:
        """Explicitly refresh the source and calculate drawing minus source."""
        d, p = self._draft, self.ports
        if (
            d is None
            or d.pending
            or d.world_id != p.world_id()
            or d.map_id != p.map_id()
            or p.view._drawing_tool.trace.active
        ):
            return
        source = self._source(d.map_id, d.object_id, d.date)
        if source is None:
            self._invalidate(
                "The source region was removed. Cancel or keep the outline."
            )
            return
        _, d.source = source
        d.source = copy.deepcopy(d.source)
        d.stale = False
        points = p.view._drawing_tool.draft_points()
        outline = RegionPolygon(points)
        d.result = cut_region(outline, RegionPolygon.from_geometry(d.source))
        d.accepted = None
        polygons = tuple(part.to_geometry() for part in d.result.polygons)
        p.view._drawing_tool.show_retained_preview(polygons)
        message = (
            d.result.explanation or "Previewing the new region. Use result to keep it."
        )
        if d.result.status == "unchanged":
            message = (
                "No overlap removed. Back to drawing to overlap the source border."
            )
        self._present("preview", message, ready=d.result.status == "ready")

    @Slot()
    def accept_result(self) -> None:
        """Accept exact overlay coordinates locally; do not persist yet."""
        d = self._draft
        if (
            d is None
            or d.pending
            or d.stale
            or d.result is None
            or d.result.status != "ready"
        ):
            return
        self._check_source()
        if d.stale:
            return
        d.accepted = d.result.polygons[0].to_geometry()
        self._present(
            "accepted",
            "Confirm to link and save the new region; Back to drawing keeps the outline.",
        )

    @Slot()
    def back_to_drawing(self) -> None:
        """Discard only the calculated result and restore every drawn point."""
        if self._draft is None or self._draft.pending:
            return
        self._draft.result = None
        self._draft.accepted = None
        self.ports.view._drawing_tool.show_retained_preview(None)
        self._present(
            "drawing", "Continue the outline, then preview the new region again."
        )
        self.ports.view.setFocus()

    def _invalidate(self, message: str) -> None:
        d = self._draft
        if d is None or d.pending:
            return
        d.stale = True
        d.accepted = None
        d.result = None
        self.ports.view._drawing_tool.show_retained_preview(None)
        self._present("drawing", message)

    def _check_source(self) -> None:
        d = self._draft
        if d is None or d.pending or d.stale:
            return
        current = self._source(d.map_id, d.object_id, d.date)
        if current is None or current[1] != d.source:
            self._invalidate(
                "The source border changed or was removed. Your outline is retained; preview again."
            )

    @Slot()
    def save(self) -> None:
        """Choose identity without mutating, then submit one atomic creation."""
        d, p = self._draft, self.ports
        if d is None or d.pending or d.accepted is None or self._choosing_object:
            return
        self._check_source()
        if d.stale:
            return
        self._choosing_object = True
        try:
            choice = p.choose_object()
        finally:
            self._choosing_object = False
        if choice is None or self._draft is not d:
            return
        self._check_source()
        if d.stale or p.map_id() != d.map_id or p.world_id() != d.world_id:
            return
        command = self._creation_command(choice, d)
        d.pending = command.command_id
        self._present("pending", "Saving the new region…")
        p.submit(command)

    def _creation_command(self, choice: MapObjectChoice, d: _Draft) -> BaseCommand:
        assert d.accepted is not None
        x, y = feature_anchor(d.accepted)
        object_id = (
            choice.object_id if choice.action == "existing" else str(uuid.uuid4())
        )
        marker = CreateNeighborRegionCommand(
            {
                "map_id": d.map_id,
                "object_id": object_id,
                "object_type": choice.object_type,
                "label": choice.name,
                "feature_type": "region",
                "geometry": copy.deepcopy(d.accepted),
                "x": x,
                "y": y,
            },
            d.source_id,
            d.date,
            d.source,
        )
        if choice.action == "existing":
            return marker
        data = {"id": object_id, "name": choice.name}
        if choice.object_type == "event":
            create: CreateEntityCommand | CreateEventCommand = self.ports.create_event(
                {**data, "lore_date": d.date}
            )
        else:
            create = self.ports.create_entity(
                {**data, "type": choice.entity_type or "Location"}
            )
        create.select_after_create = False
        return CompositeCommand([create, marker], "Create Neighboring Region")

    @Slot(object)
    def on_command_finished(self, result: CommandResult) -> None:
        """Release the draft only for the matching successful acknowledgement."""
        if result.success and result.command_name in {
            "Undo_CreateNeighborRegionCommand",
            "Redo_CreateNeighborRegionCommand",
        }:
            state = result.data.get("command_state")
            if isinstance(state, dict):
                data = state.get("data", {})
                marker = data.get("marker_data", {})
                if marker.get("map_id"):
                    self.ports.reload_map(str(marker["map_id"]))
        d = self._draft
        if d is None or not d.pending or result.data.get("command_id") != d.pending:
            return
        completion = {
            "session_id": d.session_id,
            "command_id": d.pending,
            "success": result.success,
        }
        if result.success:
            self._close()
        else:
            d.pending = None
            self._present(
                "accepted",
                result.message or "Save failed. The draft is retained; try again.",
            )
            self.ports.refresh_source(d.map_id)
        self.transition_finished.emit(completion)

    def edit_status(self) -> dict[str, Any] | None:
        """Describe this draft for the shared map/world transition guard."""
        d = self._draft
        if d is None:
            return None
        return {
            "session_id": d.session_id,
            "command_id": d.pending,
            "object_id": d.object_id,
            "target_id": d.source_id,
            "label": f"Neighbor of {d.label}",
            "dirty": True,
            "new": True,
            "pending": bool(d.pending),
            "conflicted": d.stale,
            "can_apply": d.accepted is not None and not d.stale and not d.pending,
            "explanation": "Preview and use the result before saving, or discard the neighboring-region draft.",
        }

    def apply_for_transition(self) -> None:
        """Save through the same object choice and acknowledgement path."""
        self.save()

    @Slot()
    def discard_for_transition(self) -> None:
        """Discard the entire draft only when a save is not in flight."""
        if self._draft is not None and not self._draft.pending:
            self._close()

    def _close(self) -> None:
        self._draft = None
        self.ports.view._drawing_tool.cancel_drawing()
        self._present("closed", "")
