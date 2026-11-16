"""Feature-owned hierarchy authoring orchestration over detached map snapshots."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from PySide6.QtCore import QObject, Signal, Slot

from src.commands.base_command import CommandResult
from src.commands.map_hierarchy_commands import ChangeMapParentCommand
from src.core.map import Map
from src.core.map_hierarchy import HierarchyError, MapHierarchy, hierarchy_attributes
from src.services.map_nesting_service import validate_registration_payload

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView


@dataclass(frozen=True)
class MapHierarchyPorts:
    """Explicit main-thread presentation and intent ports; no window or database."""

    view: "MapGraphicsView"
    maps: Callable[[], list[Map]]
    selected_id: Callable[[], str | None]
    accept_selection: Callable[[str], None]
    request_transition: Callable[[str, Callable[[], None]], None]
    cancel_session: Callable[[], None]
    resolve_image: Callable[[str], str]
    set_status: Callable[[str], None]
    set_breadcrumb: Callable[[list[tuple[str, str]]], None]
    refresh_mode: Callable[[], None]
    activate_pending_edit: Callable[[], None]
    feedback: Callable[[str, str], None]


class MapHierarchyCoordinator(QObject):
    """Own provisional intent, command dispatch and hierarchy presentation refresh."""

    command_requested = Signal(object)
    transition_finished = Signal(dict)

    def __init__(self, ports: MapHierarchyPorts, parent: QObject | None = None) -> None:
        """Connect feature intent without database or window dependencies."""
        super().__init__(parent)
        self.ports = ports
        self._draft: dict | None = None
        self._viewports: dict = {}
        self._displayed_id: str | None = None
        self._world_root = ""
        ports.view.footprint_edit_cancelled.connect(self.cancel_preview)
        ports.view.footprint_edit_started.connect(self._edit_started)

    def before_map_load(self, map_id: str) -> None:
        """Remember viewport context before the existing map loader changes images."""
        view = self.ports.view
        world_root = str(view._world_root)
        if world_root != self._world_root:
            self._viewports.clear()
            self._draft = None
            self._displayed_id = None
            self._world_root = world_root
        if self._displayed_id is not None and self._displayed_id != map_id:
            self._viewports[self._displayed_id] = (
                view.transform(),
                view.mapToScene(view.viewport().rect().center()),
            )
        self._displayed_id = map_id

    def _record(self, map_id: str) -> Map | None:
        return next(
            (record for record in self.ports.maps() if record.id == map_id), None
        )

    def begin_registration(
        self, map_id: str, parent_id: str, registration: dict
    ) -> None:
        """Resolve protected editing before showing any unsaved attachment."""
        proposal = deepcopy(registration)
        self.ports.request_transition(
            "place a map in the hierarchy",
            lambda: self._begin(map_id, parent_id, proposal),
        )

    def _begin(self, map_id: str, parent_id: str, registration: dict) -> None:
        record = self._record(map_id)
        if record is None:
            return
        try:
            MapHierarchy(self.ports.maps()).validate_change_parent(map_id, parent_id)
            validate_registration_payload(registration)
        except ValueError as exc:
            self.ports.feedback("Cannot attach map", str(exc))
            return
        origin = self.ports.selected_id()
        view = self.ports.view
        origin_viewport = (
            view.transform(),
            view.mapToScene(view.viewport().rect().center()),
        )
        self.ports.cancel_session()
        self.ports.accept_selection(parent_id)
        parent_record = self._record(parent_id)
        expected_image = self.ports.resolve_image(
            parent_record.image_path or "" if parent_record is not None else ""
        )
        if self.ports.view.current_image_path != expected_image:
            if origin:
                self.ports.accept_selection(origin)
            self.ports.feedback(
                "Cannot place map",
                "The parent map image could not be loaded.",
            )
            return
        self._draft = {
            "id": map_id,
            "parent": parent_id,
            "origin": origin,
            "expected": hierarchy_attributes(record.attributes),
            "session": str(uuid4()),
            "pending": None,
            "viewport": origin_viewport,
        }
        data = {
            "id": record.id,
            "name": record.name,
            "parent_map_id": parent_id,
            "registration": registration,
            "image_path": self.ports.resolve_image(record.image_path or ""),
        }
        if not self.ports.view.start_provisional_footprint(data):
            self._draft = None
            self.ports.feedback(
                "Cannot place map",
                "The parent map image could not be loaded.",
            )
        else:
            self.ports.set_status(
                f"Place {record.name} on {parent_record.name if parent_record else parent_id}. "
                "Unsaved preview — Apply to save; Cancel to discard."
            )

    def confirm(self, map_id: str, parent_id: str, registration: dict) -> None:
        """Dispatch one snapshot-safe command for the final confirmed placement."""
        record = self._record(map_id)
        if record is None:
            return
        expected = hierarchy_attributes(record.attributes)
        if self._draft is not None:
            if self._draft["pending"]:
                return
            if (map_id, parent_id) != (self._draft["id"], self._draft["parent"]):
                return
            expected = self._draft["expected"]
        command = ChangeMapParentCommand(
            map_id, parent_id, registration, expected_hierarchy=expected
        )
        if self._draft is not None:
            self._draft["pending"] = command.command_id
            self._draft["registration"] = deepcopy(registration)
        self.command_requested.emit(command)

    def _edit_started(self, map_id: str) -> None:
        if self._draft is not None:
            return
        record = self._record(map_id)
        if record is not None:
            self._draft = {
                "id": map_id,
                "parent": (record.attributes or {}).get("parent_map_id"),
                "origin": self.ports.selected_id(),
                "expected": hierarchy_attributes(record.attributes),
                "session": str(uuid4()),
                "pending": None,
                "viewport": (
                    self.ports.view.transform(),
                    self.ports.view.mapToScene(
                        self.ports.view.viewport().rect().center()
                    ),
                ),
            }

    def edit_status(self) -> dict | None:
        """Expose the existing footprint session to the shared transition guard."""
        draft = self._draft
        if draft is None:
            return None
        return {
            "session_id": draft["session"],
            "command_id": draft["pending"],
            "label": "map placement",
            "target_id": draft["id"],
            "dirty": True,
            "new": False,
            "pending": bool(draft["pending"]),
            "can_apply": not draft.get("conflicted", False),
            "explanation": "Cancel and choose the parent again after a hierarchy change."
            if draft.get("conflicted", False)
            else "",
        }

    def apply_for_transition(self) -> None:
        """Apply through the existing footprint editor's one-command path."""
        self.ports.view.finish_footprint_edit()

    def discard_for_transition(self) -> None:
        """Discard through the existing footprint editor's cancellation path."""
        self.ports.view.cancel_footprint_edit()

    @Slot(object)
    def on_command_finished(self, result: CommandResult) -> None:
        """Release only matching acknowledgements; retain rejected previews."""
        draft = self._draft
        if draft is None or not draft["pending"]:
            return
        if result.data.get("command_id") != draft["pending"]:
            return
        completion = {
            "session_id": draft["session"],
            "command_id": draft["pending"],
            "success": result.success,
        }
        self._draft = None
        if not result.success:
            record = self._record(draft["id"])
            if record is not None:
                self._draft = {**draft, "pending": None}
                self.ports.view.start_provisional_footprint(
                    {
                        "id": record.id,
                        "name": record.name,
                        "parent_map_id": draft["parent"],
                        "registration": draft["registration"],
                        "image_path": self.ports.resolve_image(record.image_path or ""),
                    }
                )
                self.ports.set_status(
                    result.message
                    or "Placement could not be saved. The preview is retained."
                )
        self.transition_finished.emit(completion)

    def detach(self, map_id: str) -> None:
        """Make a map independent through the same protected mutation path."""
        self.ports.request_transition(
            "make a map independent", lambda: self._detach(map_id)
        )

    def _detach(self, map_id: str) -> None:
        record = self._record(map_id)
        if record is not None:
            self.command_requested.emit(
                ChangeMapParentCommand(
                    map_id,
                    None,
                    None,
                    expected_hierarchy=hierarchy_attributes(record.attributes),
                )
            )

    def edit_placement(self, map_id: str) -> None:
        """Edit an existing registration without introducing a second edit lifecycle."""
        record = self._record(map_id)
        if record is None:
            return
        attrs = record.attributes or {}
        parent_id, registration = attrs.get("parent_map_id"), attrs.get("registration")
        if parent_id and isinstance(registration, dict):
            self.begin_registration(map_id, parent_id, registration)

    def cancel_preview(self) -> None:
        """Discard provisional intent and restore the navigation origin when available."""
        draft, self._draft = self._draft, None
        if draft is None:
            return
        origin = draft["origin"]
        if origin and self._record(origin) is not None:
            self._viewports[origin] = draft["viewport"]
            self.ports.accept_selection(origin)
        current = self._record(self.ports.selected_id() or "")
        if current is not None:
            self.refresh_footprints(current, self.ports.maps())

    def refresh_footprints(self, current: Map, maps: list[Map]) -> None:
        """Render parent-authoritative children while retaining an active draft."""
        view = self.ports.view
        if self._draft is not None and self._draft["pending"]:
            return
        if self._draft is not None and view.is_editing_footprint:
            source = self._record(self._draft["id"])
            if (
                source
                and hierarchy_attributes(source.attributes) == self._draft["expected"]
            ):
                return
            self._draft["conflicted"] = True
            view.footprint_edit_conflicted = True
            self.ports.set_status(
                "The saved hierarchy changed. Your preview is retained. "
                "Cancel and choose the parent again before applying."
            )
            self.ports.refresh_mode()
            return
        data = []
        for child in MapHierarchy(maps).children(current.id):
            registration = (child.attributes or {}).get("registration")
            if not isinstance(registration, dict):
                continue
            try:
                validate_registration_payload(registration)
            except ValueError:
                continue
            data.append(
                {
                    "id": child.id,
                    "name": child.name,
                    "parent_map_id": current.id,
                    "registration": registration,
                    "image_path": self.ports.resolve_image(child.image_path or ""),
                }
            )
        view.set_footprints(data)
        if current.id in self._viewports:
            transform, center = self._viewports.pop(current.id)
            view.setTransform(transform)
            view.centerOn(center)
        self.ports.activate_pending_edit()

    def refresh_breadcrumb(self, current: Map, maps: list[Map]) -> None:
        """Render only the selected map's connected ancestry."""
        try:
            ancestors = MapHierarchy(maps).ancestors(current.id)
        except HierarchyError:
            ancestors = []
        self.ports.set_breadcrumb(
            [(record.id, record.name) for record in reversed(ancestors)]
            + [(current.id, current.name)]
        )
