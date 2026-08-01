"""Map Nesting Mixin.

Provides the dialog-and-signal workflow for marking a map as the
world's master map and for registering other maps as detail children.
The mixin is intentionally thin: business logic stays in services and
commands; this layer only collects user intent and emits widget-level
signals that ``MapHandler`` translates into commands.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import SignalInstance, Slot
from PySide6.QtWidgets import QComboBox, QDialog, QInputDialog, QMessageBox, QWidget

from src.app.constants import MAP_ROLE_DETAIL, MAP_ROLE_MASTER
from src.gui.dialogs.register_detail_map_dialog import RegisterDetailMapDialog

if TYPE_CHECKING:
    from src.core.map import Map

logger = logging.getLogger(__name__)


class MapNestingMixin:
    """Mixin providing master / detail-map workflow slots.

    Requires the host class to expose:
        - ``self.map_selector``: ``QComboBox``
        - ``self.maps_data`` property → list of ``Map``
        - ``self.set_master_map_requested``: ``Signal(str)``
        - ``self.register_detail_map_requested``: ``Signal(str, str, dict)``
        - ``self.edit_footprint_requested``: ``Signal(str)``
        - ``self.get_selected_map_id()`` method
    """

    if TYPE_CHECKING:
        map_selector: QComboBox
        @property
        def maps_data(self) -> list[Map]: ...
        set_master_map_requested: SignalInstance
        register_detail_map_requested: SignalInstance
        edit_footprint_requested: SignalInstance
        _pending_footprint_edit_id: str | None

        def get_selected_map_id(self) -> str | None: ...

        def _update_mode_indicator(self) -> None: ...

    @Slot()
    def _on_set_master_map_clicked(self) -> None:
        """Emit ``set_master_map_requested`` for the active map.

        The handler decides whether to confirm with the user or show a
        warning if a previous master is being replaced — this slot
        intentionally fires without prompting so the experience matches
        the existing single-step workflow used for scale calibration.

        """
        map_id = self.get_selected_map_id()
        if not map_id:
            return
        self.set_master_map_requested.emit(map_id)

    @Slot()
    def _on_register_detail_map_clicked(self) -> None:
        """Open the parent-picker dialog and emit a registration signal.

        Phase 1 generates a default centred footprint; Phase 3 will
        replace the dialog-driven default with a canvas placement
        tool.

        """
        detail_map_id = self.get_selected_map_id()
        if not detail_map_id:
            return
        maps = list(self.maps_data or [])
        detail_map = next((m for m in maps if m.id == detail_map_id), None)
        if detail_map is None:
            return
        candidates = RegisterDetailMapDialog.filter_candidate_parents(
            maps, detail_map_id
        )
        if not candidates:
            QMessageBox.information(
                cast(QWidget, self),
                "No Parent Available",
                "Designate a master map before registering a detail map.",
            )
            return

        resolver = getattr(self, "_resolve_world_image_path", None)
        dialog = RegisterDetailMapDialog(
            detail_map=detail_map,
            candidate_parents=candidates,
            resolve_image_path=resolver,
            parent=cast(QWidget, self),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        parent_id = dialog.selected_parent_id()
        registration = dialog.registration()
        if not parent_id or registration is None:
            return
        self.register_detail_map_requested.emit(
            detail_map_id, parent_id, registration
        )

    @Slot()
    def _on_edit_footprint_clicked(self) -> None:
        """Enter canvas footprint-edit mode for a detail map.

        Two cases:
        - Footprints are already visible (parent map is loaded): show a
          picker when there are multiple footprints, then enter edit mode.
        - The current map is a detail map (parent not yet loaded): navigate
          to the parent map and store a pending edit that activates once
          footprints are rendered.

        """
        view = getattr(self, "view", None)
        if view is None:
            return
        if not getattr(view, "footprints_visible", True):
            QMessageBox.information(
                cast(QWidget, self),
                "Footprints Hidden",
                "Footprints are currently hidden. Enable Show Footprints "
                "to edit placements.",
            )
            return

        footprint_items = view._footprint_items
        if footprint_items:
            # Footprints are visible — pick one and enter edit mode directly.
            if len(footprint_items) == 1:
                fid = next(iter(footprint_items))
            else:
                id_list = list(footprint_items.keys())
                display = [
                    f"{footprint_items[k]._name} ({k[:8]})"
                    for k in id_list
                ]
                chosen, ok = QInputDialog.getItem(
                    cast(QWidget, self),
                    "Edit Footprint",
                    "Select a footprint to edit:",
                    display,
                    editable=False,
                )
                if not ok:
                    return
                fid = id_list[display.index(chosen)]
            view.start_footprint_edit(fid)
            self._update_mode_indicator()
            self.edit_footprint_requested.emit(fid)
            return

        # No footprints in view — navigate to the detail map's parent first.
        map_id = self.get_selected_map_id()
        if not map_id:
            return
        active_map = next(
            (m for m in (self.maps_data or []) if m.id == map_id), None
        )
        if active_map is None:
            return
        if (active_map.attributes or {}).get("map_role") != MAP_ROLE_DETAIL:
            return
        parent_id = (active_map.attributes or {}).get("parent_map_id")
        if not parent_id:
            return
        self._pending_footprint_edit_id = map_id
        index = self.map_selector.findData(parent_id)
        if index >= 0:
            self.map_selector.setCurrentIndex(index)

    def _try_activate_pending_footprint_edit(self) -> None:
        """Activate a deferred footprint edit once the parent map has loaded.

        Called by ``MapHandler`` after footprint overlays are set on the
        view.  If a pending edit was stored by ``_on_edit_footprint_clicked``
        and the footprint item now exists, enter edit mode immediately.

        """
        fid = getattr(self, "_pending_footprint_edit_id", None)
        if fid is None:
            return
        view = getattr(self, "view", None)
        if view is None:
            return
        if fid not in view._footprint_items:
            return
        self._pending_footprint_edit_id = None
        view.start_footprint_edit(fid)
        self._update_mode_indicator()
        self.edit_footprint_requested.emit(fid)

    # ------------------------------------------------------------------
    # Helpers used by the overflow menu to gate visibility of actions
    # ------------------------------------------------------------------

    def _active_map_role(self) -> str | None:
        """Return the active map's ``map_role`` attribute, or ``None``."""
        map_id = self.get_selected_map_id()
        if not map_id:
            return None
        for m in self.maps_data or []:
            if m.id == map_id:
                role = (m.attributes or {}).get("map_role")
                return role if isinstance(role, str) else None
        return None

    def _world_has_master_map(self) -> bool:
        """Return True iff some map in the world is flagged master."""
        for m in self.maps_data or []:
            if (m.attributes or {}).get("map_role") == MAP_ROLE_MASTER:
                return True
        return False

    def _resolve_world_image_path(self, image_path: str) -> str:
        """Turn a stored map image path into an absolute filesystem path.

        Stored ``image_path`` values are relative to the active world's
        directory.  The view tracks the world root once a map has been
        loaded; we reuse it here so the registration dialog can read
        the detail map's intrinsic dimensions without reaching outside
        the widget.

        Args:
            image_path: Path as stored in :class:`Map.image_path`.

        Returns:
            An absolute path string.  Returns ``image_path`` unchanged
            if no world root is known yet (the dialog will fall back to
            an aspect ratio of 1.0).

        """
        from pathlib import Path

        if not image_path:
            return image_path
        path = Path(image_path)
        if path.is_absolute():
            return image_path
        view = getattr(self, "view", None)
        world_root = getattr(view, "_world_root", None)
        if world_root:
            return str(Path(world_root) / path)
        return image_path
