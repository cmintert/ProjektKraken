"""Coordinate cached dated geometry playback for vector map features."""

from __future__ import annotations

import copy
import time
import uuid
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Q_ARG, QObject, Qt, Signal, Slot

from src.app.qt_invocation import invoke_queued
from src.commands.base_command import BaseCommand, CommandResult
from src.commands.feature_geometry_commands import (
    ReplaceFeatureGeometryStatesCommand,
    UpdateFeatureBaseGeometryCommand,
)
from src.core.feature_geometry_state import (
    FeatureGeometryState,
    calculate_feature_anchor,
    resolve_feature_geometry,
    validate_feature_geometry,
)
from src.core.marker import FEATURE_TYPE_PATH, FEATURE_TYPE_REGION, Marker

if TYPE_CHECKING:
    from src.app.main_window import MainWindow


class FeatureGeometryCoordinator(QObject):
    """Own map-scoped geometry caches and resolve them at the playhead."""

    transition_finished = Signal(dict)

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize feature-geometry edit coordination."""
        super().__init__(main_window)
        self._window = main_window
        self._markers_by_map: dict[str, dict[str, dict[str, Any]]] = {}
        self._states_by_map: dict[str, dict[str, list[FeatureGeometryState]]] = {}
        self._bound = False
        self._session: dict[str, Any] | None = None
        self._pending_command_id: str | None = None

    @property
    def is_active(self) -> bool:
        """Whether an unfinished geometry working copy needs resolution."""
        return self._session is not None

    def edit_status(self) -> dict[str, Any] | None:
        """Expose independent dirty and validation state for transition decisions."""
        session = self._session
        if session is None:
            return None
        valid = True
        try:
            validate_feature_geometry(
                session["feature_type"], session["working_geometry"]
            )
        except ValueError:
            valid = False
        pending = self._pending_command_id is not None
        return {
            "session_id": session["session_id"],
            "world_id": str(
                getattr(getattr(self._window, "current_world", None), "id", "")
            ),
            "map_id": session["map_id"],
            "target_id": session["marker_id"],
            "object_id": session["object_id"],
            "label": session["label"],
            "dirty": session["working_geometry"] != session["original_geometry"],
            "new": session["target_type"] == "new_state",
            "pending": pending,
            "conflicted": session["conflicted"],
            "command_id": self._pending_command_id,
            "can_apply": valid and not session["conflicted"] and not pending,
            "explanation": "Resolve invalid geometry or discard and reload "
            "changes made elsewhere before applying.",
        }

    def apply_for_transition(self) -> None:
        """Persist the retained working geometry."""
        self.apply_edit()

    def discard_for_transition(self) -> None:
        """Deliberately restore authoritative geometry."""
        self.cancel_edit()

    @Slot(str, list)
    def on_preview_changed(self, object_id: str, geometry: list) -> None:
        """Retain copied preview vertices without persistence."""
        if (
            self._session is not None
            and self._pending_command_id is None
            and self._session["object_id"] == object_id
        ):
            self._session["working_geometry"] = copy.deepcopy(geometry)

    def _completion(self, success: bool) -> dict[str, Any]:
        return {
            "session_id": self._session["session_id"] if self._session else "",
            "command_id": self._pending_command_id,
            "success": success,
        }

    def _notify_transition(self, success: bool) -> None:
        self.transition_finished.emit(self._completion(success))

    def _check_and_rebind(self, map_id: str) -> None:
        session = self._session
        if (
            session is None
            or session["map_id"] != map_id
            or self._pending_command_id is not None
        ):
            return
        marker = self._markers_by_map.get(map_id, {}).get(session["marker_id"])
        if marker is None:
            session["conflicted"] = True
        elif session["target_type"] == "base":
            base = {"geometry": marker["geometry"], "x": marker["x"], "y": marker["y"]}
            session["conflicted"] |= base != session["before_base"]
        elif map_id in self._states_by_map:
            session["conflicted"] |= (
                self.states_for_marker(map_id, session["marker_id"])
                != session["before_states"]
            )
        self._rebind_preview()

    def _rebind_preview(self) -> None:
        session = self._session
        if session is None or self._pending_command_id is not None:
            return
        widget = self._window.map_widget
        if session["conflicted"]:
            widget.show_feature_geometry_edit(
                f"Geometry — {session['label']}",
                "Changed elsewhere — draft retained; discard and reload to continue",
            )
        widget.set_feature_geometry_edit_available(
            not session["conflicted"],
            "Discard and reload changes made elsewhere."
            if session["conflicted"]
            else "",
        )
        item = widget.view.feature_items.get(session["object_id"])
        if item is None:
            return
        editor = widget.view._vertex_editor
        if (
            session.get("scene_item_id") == id(item)
            and getattr(editor, "editing_feature_id", None) == session["object_id"]
        ):
            return
        session["scene_item_id"] = id(item)
        session["pixmap_id"] = id(widget.view.pixmap_item)
        editor.finish_vertex_editing(emit_geometry_change=False)
        geometry = copy.deepcopy(session["working_geometry"])
        x, y = calculate_feature_anchor(geometry)
        item.set_geometry(geometry, x, y)
        editor.start_vertex_editing(item, managed_session=True)

    def bind_ui(self) -> None:
        """Connect main-thread snapshots, playhead changes, and command effects."""
        if self._bound:
            return
        handler = self._window.data_handler
        handler.markers_ready.connect(self.on_markers_ready)
        handler.feature_geometry_states_ready.connect(self.on_states_ready)
        self._window.timeline.playhead_time_changed.connect(self.on_playhead_changed)
        self._window.worker.command_finished.connect(
            self.on_command_finished, Qt.ConnectionType.QueuedConnection
        )
        widget = self._window.map_widget
        widget.feature_geometry_edit_requested.connect(self.start_edit_at_playhead)
        widget.feature_geometry_manage_requested.connect(self.manage_states)
        widget.feature_geometry_apply_requested.connect(self.apply_edit)
        widget.feature_geometry_cancel_requested.connect(self.cancel_edit)
        widget.view.feature_geometry_preview_changed.connect(self.on_preview_changed)
        widget.marker_scene_updated.connect(self._check_and_rebind)
        self._bound = True

    @Slot(str)
    def on_map_selected(self, map_id: str) -> None:
        """Accepted navigation has already resolved the active draft."""

    @Slot(str, list)
    def on_markers_ready(self, map_id: str, markers: list[dict[str, Any]]) -> None:
        """Cache independent base snapshots and reapply the current playhead."""
        self._markers_by_map[map_id] = {
            str(marker["id"]): copy.deepcopy(marker)
            for marker in markers
            if marker.get("feature_type") in {FEATURE_TYPE_PATH, FEATURE_TYPE_REGION}
        }
        self._check_and_rebind(map_id)
        self._apply_for_map(map_id, self._window.timeline.get_playhead_time())

    @Slot(str, list)
    def on_states_ready(self, map_id: str, states: list[dict[str, Any]]) -> None:
        """Cache dated states grouped by marker and reapply the playhead."""
        grouped: dict[str, list[FeatureGeometryState]] = defaultdict(list)
        for snapshot in states:
            state = FeatureGeometryState.from_dict(snapshot)
            grouped[state.marker_id].append(state)
        for marker_states in grouped.values():
            marker_states.sort(key=lambda state: state.effective_date)
        self._states_by_map[map_id] = dict(grouped)
        self._check_and_rebind(map_id)
        self._apply_for_map(map_id, self._window.timeline.get_playhead_time())

    @Slot(float)
    def on_playhead_changed(self, lore_date: float) -> None:
        """Resolve cached geometry immediately without worker-thread traffic."""
        map_id = self._window.map_widget.get_selected_map_id()
        if map_id:
            self._apply_for_map(map_id, lore_date)

    @Slot(CommandResult)
    def on_command_finished(self, result: CommandResult) -> None:
        """Reload the affected map after a geometry-state command or undo."""
        command_id = str(result.data.get("command_id", ""))
        pending_matches = self._pending_command_id is not None and (
            command_id == self._pending_command_id
        )
        if not result.success:
            if pending_matches:
                self._notify_transition(False)
                self._pending_command_id = None
                self._window.map_widget.set_feature_geometry_edit_pending(False)
                self._rebind_preview()
            return
        effects = result.data.get("effects", [])
        for effect in effects if isinstance(effects, list) else []:
            if not isinstance(effect, dict):
                continue
            if effect.get("kind") not in {
                "feature_geometry_states_changed",
                "feature_base_geometry_changed",
            }:
                continue
            map_id = str(effect.get("map_id", ""))
            if map_id:
                invoke_queued(
                    self._window.worker,
                    (
                        "load_markers"
                        if effect["kind"] == "feature_base_geometry_changed"
                        else "load_feature_geometry_states"
                    ),
                    Q_ARG(str, map_id),
                )
        if self._pending_command_id is None:
            return
        if command_id != self._pending_command_id:
            return
        if self._session is not None and self._session["target_type"] == "base":
            snapshot = self._markers_by_map.get(self._session["map_id"], {}).get(
                self._session["marker_id"]
            )
            pending_base = self._session.get("pending_base")
            if snapshot is not None and isinstance(pending_base, dict):
                snapshot["geometry"] = copy.deepcopy(pending_base["geometry"])
                snapshot["x"] = float(pending_base["x"])
                snapshot["y"] = float(pending_base["y"])
        if self._session is not None and self._session["target_type"] != "base":
            command_state = result.data.get("command_state", {})
            data = (
                command_state.get("data", {}) if isinstance(command_state, dict) else {}
            )
            after = data.get("after_snapshot") if isinstance(data, dict) else None
            if isinstance(after, list):
                self._states_by_map.setdefault(self._session["map_id"], {})[
                    self._session["marker_id"]
                ] = [FeatureGeometryState.from_dict(row) for row in after]
        completion = self._completion(True)
        self._finish_edit_session(restore_playhead=False)
        self.transition_finished.emit(completion)

    @Slot(str)
    def start_edit_at_playhead(self, object_id: str) -> None:
        """Edit an exact state or clone the resolved geometry at the playhead."""
        located = self._find_marker(object_id)
        if located is None:
            return
        map_id, marker_id, snapshot = located
        playhead = float(self._window.timeline.get_playhead_time())
        before = self.states_for_marker(map_id, marker_id)
        exact = next(
            (state for state in before if float(state["effective_date"]) == playhead),
            None,
        )
        if exact is not None:
            self._start_session(
                map_id,
                marker_id,
                snapshot,
                "state",
                exact,
                before,
            )
            return
        marker = Marker.from_dict(snapshot)
        states = [FeatureGeometryState.from_dict(state) for state in before]
        resolved = resolve_feature_geometry(marker, states, playhead)
        target = FeatureGeometryState(
            marker_id=marker_id,
            effective_date=playhead,
            geometry=resolved.geometry,
            anchor_x=resolved.anchor_x,
            anchor_y=resolved.anchor_y,
        ).to_dict()
        self._start_session(
            map_id,
            marker_id,
            snapshot,
            "new_state",
            target,
            before,
        )

    @Slot(str)
    def manage_states(self, object_id: str) -> None:
        """Open the calendar-aware Base and dated-state management dialog."""
        located = self._find_marker(object_id)
        if located is None:
            return
        map_id, marker_id, snapshot = located
        from src.gui.dialogs.feature_geometry_states_dialog import (
            FeatureGeometryStatesDialog,
        )

        states = self.states_for_marker(map_id, marker_id)
        presenter = getattr(self._window.map_widget, "feature_actions", None)
        guard = presenter.capture_guard(object_id, "history") if presenter else None
        dialog = FeatureGeometryStatesDialog(
            str(snapshot.get("label") or "Map feature"),
            states,
            getattr(self._window, "calendar_converter", None),
            self._window.map_widget,
        )
        if (
            dialog.exec() != dialog.DialogCode.Accepted
            or dialog.selected_action is None
            or (guard is not None and not guard())
        ):
            return
        action, state_id, date = dialog.selected_action
        if action == "edit_base":
            base_target = {
                "geometry": copy.deepcopy(snapshot.get("geometry") or []),
                "anchor_x": float(snapshot["x"]),
                "anchor_y": float(snapshot["y"]),
            }
            self._start_session(
                map_id, marker_id, snapshot, "base", base_target, states
            )
            return
        selected = next(
            (state for state in states if str(state["id"]) == state_id), None
        )
        if selected is None:
            return
        if action == "edit_state":
            self._start_session(map_id, marker_id, snapshot, "state", selected, states)
        elif action == "move_state" and date is not None:
            if any(
                str(state["id"]) != state_id
                and float(state["effective_date"]) == float(date)
                for state in states
            ):
                self._window.statusBar().showMessage(
                    "A geometry state already exists on that date.", 5000
                )
                return
            replacement = copy.deepcopy(states)
            for state in replacement:
                if str(state["id"]) == state_id:
                    state["effective_date"] = float(date)
                    state["modified_at"] = time.time()
            self._submit_state_command(
                map_id, marker_id, states, replacement, "Move Geometry State"
            )
        elif action == "delete_state":
            replacement = [state for state in states if str(state["id"]) != state_id]
            self._submit_state_command(
                map_id, marker_id, states, replacement, "Delete Geometry State"
            )

    @Slot()
    def apply_edit(self) -> None:
        """Validate the preview and persist it as one undoable operation."""
        session = self._session
        if session is None or self._pending_command_id is not None:
            return
        if session["conflicted"]:
            self._window.statusBar().showMessage(
                "Geometry changed elsewhere. Discard and reload to continue.", 5000
            )
            return
        geometry = copy.deepcopy(session["working_geometry"])
        try:
            validate_feature_geometry(session["feature_type"], geometry)
            anchor_x, anchor_y = calculate_feature_anchor(geometry)
        except ValueError as exc:
            self._window.statusBar().showMessage(str(exc), 5000)
            return
        self._window.map_widget.view._vertex_editor.finish_vertex_editing(
            emit_geometry_change=False
        )
        if session["target_type"] == "base":
            session["pending_base"] = {
                "geometry": copy.deepcopy(geometry),
                "x": anchor_x,
                "y": anchor_y,
            }
            command: BaseCommand = UpdateFeatureBaseGeometryCommand(
                session["marker_id"],
                session["before_base"],
                {"geometry": geometry, "x": anchor_x, "y": anchor_y},
            )
        else:
            replacement = copy.deepcopy(session["before_states"])
            target = copy.deepcopy(session["target"])
            target["geometry"] = geometry
            target["anchor_x"] = anchor_x
            target["anchor_y"] = anchor_y
            target["modified_at"] = time.time()
            if session["target_type"] == "new_state":
                replacement.append(target)
                description = "Create Geometry State"
            else:
                replacement = [
                    target if state["id"] == target["id"] else state
                    for state in replacement
                ]
                description = "Edit Geometry State"
            command = ReplaceFeatureGeometryStatesCommand(
                session["map_id"],
                session["marker_id"],
                session["before_states"],
                replacement,
                description,
            )
        self._pending_command_id = command.command_id
        self._window.map_widget.set_feature_geometry_edit_pending(True)
        self._window.command_requested.emit(command)

    @Slot()
    def cancel_edit(self) -> None:
        """Discard the working copy and render the authoritative playhead state."""
        if self._pending_command_id is not None:
            return
        self._window.map_widget.view._vertex_editor.finish_vertex_editing(
            emit_geometry_change=False
        )
        self._finish_edit_session()

    def _start_session(
        self,
        map_id: str,
        marker_id: str,
        marker_snapshot: dict[str, Any],
        target_type: str,
        target: dict[str, Any],
        before_states: list[dict[str, Any]],
    ) -> None:
        if self._session is not None:
            current = self._session
            same = (
                current["map_id"] == map_id
                and current["marker_id"] == marker_id
                and current["target_type"] == target_type
                and current["target"].get("id") == target.get("id")
                and current["target"].get("effective_date")
                == target.get("effective_date")
            )
            if same:
                return
        app = getattr(self._window, "app_coordinator", None)
        guard = getattr(app, "map_edits", None)
        if guard is not None:
            guard.request_transition(
                "edit another geometry target",
                lambda: self._begin_session(
                    map_id,
                    marker_id,
                    marker_snapshot,
                    target_type,
                    target,
                    before_states,
                ),
            )
            return
        self.cancel_edit()
        self._begin_session(
            map_id, marker_id, marker_snapshot, target_type, target, before_states
        )

    def _begin_session(
        self,
        map_id: str,
        marker_id: str,
        marker_snapshot: dict[str, Any],
        target_type: str,
        target: dict[str, Any],
        before_states: list[dict[str, Any]],
    ) -> None:
        """Install a fresh snapshot after the guard accepts replacement."""
        if self._window.map_widget.get_selected_map_id() != map_id:
            return
        latest = self.marker_snapshot(map_id, marker_id)
        if latest is None:
            return
        marker_snapshot = latest
        before_states = self.states_for_marker(map_id, marker_id)
        if target_type == "base":
            target = {
                "geometry": copy.deepcopy(latest["geometry"]),
                "anchor_x": latest["x"],
                "anchor_y": latest["y"],
            }
        elif target_type == "new_state":
            exact = next(
                (
                    row
                    for row in before_states
                    if row["effective_date"] == target["effective_date"]
                ),
                None,
            )
            if exact is not None:
                target_type, target = "state", exact
            else:
                resolved = resolve_feature_geometry(
                    Marker.from_dict(latest),
                    [FeatureGeometryState.from_dict(row) for row in before_states],
                    float(target["effective_date"]),
                )
                target = {
                    **target,
                    "geometry": resolved.geometry,
                    "anchor_x": resolved.anchor_x,
                    "anchor_y": resolved.anchor_y,
                }
        elif target_type == "state":
            selected = next(
                (row for row in before_states if row["id"] == target["id"]), None
            )
            if selected is None:
                return
            target = selected
        object_id = str(marker_snapshot["object_id"])
        item = self._window.map_widget.view.feature_items.get(object_id)
        geometry = copy.deepcopy(target.get("geometry") or [])
        if item is None or not geometry:
            return
        item.set_geometry(
            geometry,
            float(target.get("anchor_x", marker_snapshot["x"])),
            float(target.get("anchor_y", marker_snapshot["y"])),
        )
        self._session = {
            "session_id": str(uuid.uuid4()),
            "scene_item_id": id(item),
            "pixmap_id": id(self._window.map_widget.view.pixmap_item),
            "original_geometry": copy.deepcopy(geometry),
            "working_geometry": copy.deepcopy(geometry),
            "before_base": {
                "geometry": copy.deepcopy(marker_snapshot["geometry"]),
                "x": marker_snapshot["x"],
                "y": marker_snapshot["y"],
            },
            "conflicted": False,
            "label": str(marker_snapshot.get("label") or "this feature"),
            "map_id": map_id,
            "marker_id": marker_id,
            "object_id": object_id,
            "feature_type": str(marker_snapshot["feature_type"]),
            "target_type": target_type,
            "target": copy.deepcopy(target),
            "before_states": copy.deepcopy(before_states),
        }
        self._window.map_widget.view.set_temporal_authoring_override(object_id, True)
        self._window.map_widget.set_feature_geometry_edit_available(True)
        source = self._source_label(target_type, target)
        self._window.map_widget.show_feature_geometry_edit(
            f"Geometry — {marker_snapshot.get('label', 'Feature')}", source
        )
        self._window.map_widget.view._vertex_editor.start_vertex_editing(
            item, managed_session=True
        )

    def _submit_state_command(
        self,
        map_id: str,
        marker_id: str,
        before: list[dict[str, Any]],
        after: list[dict[str, Any]],
        description: str,
    ) -> None:
        command = ReplaceFeatureGeometryStatesCommand(
            map_id, marker_id, before, after, description
        )
        self._window.command_requested.emit(command)

    def _finish_edit_session(self, *, restore_playhead: bool = True) -> None:
        map_id = self._session["map_id"] if self._session else None
        object_id = self._session["object_id"] if self._session else None
        if object_id:
            self._window.map_widget.view.set_temporal_authoring_override(
                object_id, False
            )
        self._session = None
        self._pending_command_id = None
        self._window.map_widget.hide_feature_geometry_edit()
        if map_id and restore_playhead:
            self._apply_for_map(map_id, self._window.timeline.get_playhead_time())

    def _find_marker(self, object_id: str) -> tuple[str, str, dict[str, Any]] | None:
        map_id = self._window.map_widget.get_selected_map_id()
        if not map_id:
            return None
        for marker_id, snapshot in self._markers_by_map.get(map_id, {}).items():
            if str(snapshot.get("object_id")) == object_id:
                return map_id, marker_id, copy.deepcopy(snapshot)
        return None

    def _source_label(self, target_type: str, target: dict[str, Any]) -> str:
        if target_type == "base":
            return "Base Geometry"
        date = float(target["effective_date"])
        converter = getattr(self._window, "calendar_converter", None)
        formatted = converter.format_date(date) if converter else f"Lore day {date:g}"
        return (
            f"New state at {formatted}"
            if target_type == "new_state"
            else f"State from {formatted}"
        )

    def states_for_marker(self, map_id: str, marker_id: str) -> list[dict[str, Any]]:
        """Return an independent authoritative state snapshot for editing."""
        return [
            state.to_dict()
            for state in self._states_by_map.get(map_id, {}).get(marker_id, [])
        ]

    def marker_snapshot(self, map_id: str, marker_id: str) -> dict[str, Any] | None:
        """Return one cached base marker snapshot."""
        marker = self._markers_by_map.get(map_id, {}).get(marker_id)
        return copy.deepcopy(marker) if marker is not None else None

    def _apply_for_map(self, map_id: str, lore_date: float) -> None:
        if self._window.map_widget.get_selected_map_id() != map_id:
            return
        states_by_marker = self._states_by_map.get(map_id, {})
        for marker_id, snapshot in self._markers_by_map.get(map_id, {}).items():
            if (
                self._session is not None
                and self._session["map_id"] == map_id
                and self._session["marker_id"] == marker_id
            ):
                continue
            marker = Marker.from_dict(snapshot)
            resolved = resolve_feature_geometry(
                marker,
                states_by_marker.get(marker_id, []),
                lore_date,
            )
            self._window.map_widget.update_feature_geometry(
                str(snapshot["object_id"]),
                resolved.geometry,
                resolved.anchor_x,
                resolved.anchor_y,
            )
