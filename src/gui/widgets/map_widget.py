"""
Map Widget Module.

Main entry point for map visualization. Provides MapWidget wrapper
that combines MapGraphicsView with map management controls.

The map components have been refactored into separate modules for better
maintainability:
- map/marker_item.py - MarkerItem rendering
- map/map_graphics_view.py - Main view with zoom/pan and interaction
- map/icon_picker_dialog.py - Icon selection dialog
"""

import logging
import os
from typing import Iterator, List, Optional, Tuple

from PySide6.QtCore import QSettings, Qt, Signal, Slot
from PySide6.QtGui import QKeyEvent, QResizeEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.core.paths import get_resource_path
from src.core.trajectory import KEYFRAME_TIME_EPSILON, interpolate_position
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.map.marker_item import MarkerItem

logger = logging.getLogger(__name__)

# Path to marker icons
MARKER_ICONS_PATH = get_resource_path(os.path.join("assets", "icons", "markers"))


def get_available_icons() -> List[str]:
    """
    Returns a list of available marker icon filenames.

    Returns:
        List[str]: List of .svg filenames in the markers folder.
    """
    if not os.path.exists(MARKER_ICONS_PATH):
        return []
    return [f for f in os.listdir(MARKER_ICONS_PATH) if f.endswith(".svg")]


class MapWidget(QWidget):
    """
    Container widget for the map view.

    Provides a clean interface to the map system with signal routing.

    Signals:
        marker_position_changed: Emitted when a marker is moved by the user.
                                Args: (marker_id: str, x: float, y: float)
                                Coordinates are normalized [0.0, 1.0].
    """

    marker_position_changed = Signal(str, float, float)
    marker_clicked = Signal(str, str)
    create_map_requested = Signal()
    delete_map_requested = Signal()
    map_selected = Signal(str)  # map_id
    create_marker_requested = Signal(float, float)  # x, y normalized
    delete_marker_requested = Signal(str)  # marker_id
    change_marker_icon_requested = Signal(str, str)  # marker_id, new_icon
    change_marker_color_requested = Signal(str, str)  # marker_id, new_color_hex
    marker_drop_requested = Signal(str, str, str, float, float)  # id, type, name, x, y
    add_keyframe_requested = Signal(
        str, str, float, float, float
    )  # map_id, marker_id, t, x, y
    update_keyframe_time_requested = Signal(
        str, str, float, float
    )  # map_id, marker_id, old_t, new_t
    delete_keyframe_requested = Signal(str, str, float)  # map_id, marker_id, t
    jump_to_time_requested = Signal(float)  # target_time
    show_onboarding_requested = Signal()  # To trigger animation or hints

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initializes the MapWidget.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)

        # Create view
        self.view = MapGraphicsView(self)

        # Clock Mode state
        self._pinned_marker_id: Optional[str] = None
        self._pinned_original_t: Optional[float] = None

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Toolbar
        self.toolbar = QToolBar(self)
        self.toolbar.setStyleSheet("QToolBar { spacing: 10px; padding: 5px; }")
        layout.addWidget(self.toolbar)

        # Map Selector
        self.map_selector = QComboBox()
        self.map_selector.setMinimumWidth(200)
        self.map_selector.currentIndexChanged.connect(self._on_map_selected)
        self.toolbar.addWidget(self.map_selector)

        # Buttons
        self.btn_new_map = QPushButton("New Map")
        self.btn_new_map.clicked.connect(self.create_map_requested.emit)
        self.toolbar.addWidget(self.btn_new_map)

        self.btn_delete_map = QPushButton("Delete Map")
        self.btn_delete_map.clicked.connect(self.delete_map_requested.emit)
        self.toolbar.addWidget(self.btn_delete_map)

        # Spacer or Separator could go here, but Longform doesn't use standard
        # separator widget with buttons often using a simple label or just spacing

        self.btn_fit_view = QPushButton("Fit to View")
        self.btn_fit_view.clicked.connect(self.view.fit_to_view)
        self.toolbar.addWidget(self.btn_fit_view)

        self.btn_settings = QPushButton("Settings")
        self.btn_settings.setToolTip("Configure Map Properties (Scale)")
        self.btn_settings.clicked.connect(self._configure_map_width)
        self.toolbar.addWidget(self.btn_settings)

        self.btn_add_keyframe = QPushButton("Add Keyframe")
        self.btn_add_keyframe.setToolTip("Save current marker position at current time")
        self.btn_add_keyframe.clicked.connect(self._on_add_keyframe)
        self.toolbar.addWidget(self.btn_add_keyframe)

        # Mode Indicator (right side)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)

        self.mode_indicator = QLabel("Normal Mode")
        self.mode_indicator.setStyleSheet(
            """
            QLabel {
                background: #2ecc71;
                color: white;
                padding: 5px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
        """
        )
        self.toolbar.addWidget(self.mode_indicator)

        # Add View (after toolbar)
        layout.addWidget(self.view)

        # Overlay Banner (Child of view, positioned at top)
        self.overlay_banner = QLabel(self.view)
        self.overlay_banner.setAlignment(Qt.AlignCenter)
        self.overlay_banner.setStyleSheet(
            """
            QLabel {
                background-color: rgba(0, 0, 0, 180);
                color: white;
                padding: 12px;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                font-size: 13px;
                font-weight: 500;
            }
        """
        )
        self.overlay_banner.hide()

        # Coordinate Label
        self.coord_label = QLabel("Ready")
        self.coord_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.coord_label.setStyleSheet(
            "color: #888888; font-size: 10px; padding: 2px 5px;"
        )
        layout.addWidget(self.coord_label)

        # Connect signals
        self.view.marker_moved.connect(self._on_marker_moved)
        self.view.marker_clicked.connect(self.marker_clicked.emit)
        self.view.marker_clicked.connect(self._on_marker_clicked_internal)
        self.view.keyframe_moved.connect(self._on_keyframe_moved)
        self.view.keyframe_clock_mode_requested.connect(self._on_clock_mode_requested)
        self.view.keyframe_delete_requested.connect(self._on_keyframe_delete_requested)
        self.view.keyframe_edit_requested.connect(self._emit_keyframe_upsert)
        self.view.add_marker_requested.connect(self.create_marker_requested.emit)
        self.view.delete_marker_requested.connect(self.delete_marker_requested.emit)
        self.view.change_marker_icon_requested.connect(
            self.change_marker_icon_requested.emit
        )
        self.view.change_marker_color_requested.connect(
            self.change_marker_color_requested.emit
        )
        self.view.marker_drop_requested.connect(self.marker_drop_requested.emit)
        self.view.mouse_coordinates_changed.connect(self._on_mouse_coordinates_changed)
        self.view.scene.selectionChanged.connect(self._on_selection_changed)

        self._maps_data = []  # List of maps for selector
        self._playhead_time: float = 0.0  # Current playhead time from Timeline
        self._current_time: float = 0.0  # Story's "Now" time from Timeline

        self._active_trajectories: dict[str, list] = {}  # marker_id -> list[Keyframe]
        self._selected_marker_id: Optional[str] = None

        # Update all markers with active trajectories
        self._update_trajectory_positions()

    def _on_selection_changed(self) -> None:
        """Updates UI state based on selection."""
        selected_items = self.view.scene.selectedItems()
        should_enable = False
        if selected_items:
            item = selected_items[0]
            if isinstance(item, MarkerItem):
                # EVENTS cannot have keyframes (trajectories)
                should_enable = item.object_type != "event"

        self.btn_add_keyframe.setEnabled(should_enable)
        if hasattr(self, "btn_add_keyframe"):
            # Update tooltip to explain why disabled if needed
            if (
                not should_enable
                and selected_items
                and isinstance(selected_items[0], MarkerItem)
            ):
                self.btn_add_keyframe.setToolTip("Events cannot have trajectories")
            else:
                self.btn_add_keyframe.setToolTip(
                    "Save current marker position at current time"
                )

    def set_trajectories(self, trajectories: list) -> None:
        """
        Sets the active trajectories for the current map.

        Args:
            trajectories: List of (marker_id, trajectory_id, keyframes) tuples.
        """
        self._active_trajectories.clear()
        count = 0
        for marker_id, _, keyframes in trajectories:
            self._active_trajectories[marker_id] = keyframes
            count += 1

        # Detect first trajectory use for animation
        settings = QSettings()
        is_first_trajectories = not settings.value(
            "map/trajectories_initialized", False, type=bool
        )
        logger.debug(
            f"set_trajectories: count={count}, is_first={is_first_trajectories}"
        )
        if is_first_trajectories and count > 0:
            logger.info(
                "First trajectory display detected - enabling pulsing animation"
            )
            settings.setValue("map/trajectories_initialized", True)
            self.view.trigger_first_use_animation = True

        logger.debug(f"Loaded {count} temporal trajectories for map")
        # Force an update immediately so markers jump to correct spot for current time
        self._update_trajectory_positions()

        # Update visualization if selection exists
        if self._selected_marker_id:
            self._update_trajectory_visualization(self._selected_marker_id)

    # Note: Skipping unrelated methods to reach _on_add_keyframe

    @Slot()
    def _on_add_keyframe(self) -> None:
        """
        Captures the current position of the selected marker and saves it as a keyframe.
        """
        selected_items = self.view.scene.selectedItems()
        if not selected_items:
            logger.warning("Cannot add keyframe: No marker selected.")
            return

        # Assuming single selection for now
        item = selected_items[0]
        if not isinstance(item, MarkerItem):
            logger.warning("Selected item is not a marker.")
            return

        if item.object_type == "event":
            logger.warning(f"Cannot add keyframe for event marker {item.marker_id}")
            return

        marker_id = item.marker_id
        t = self._playhead_time

        # Get position in normalized coordinates
        pos = item.pos()
        norm_pos = self.view.coord_system.to_normalized(pos)
        x, y = norm_pos

        logger.info(f"Adding keyframe for {marker_id} at t={t}: ({x:.3f}, {y:.3f})")
        self._emit_keyframe_upsert(marker_id, t, x, y, is_add=True)

    def _iter_trajectory_positions(self) -> Iterator[Tuple[str, float, float]]:
        """Yield (marker_id, x, y) for markers with trajectories at current time."""
        for marker_id, keyframes in self._active_trajectories.items():
            position = interpolate_position(keyframes, self._playhead_time)
            if position:
                x, y = position
                yield marker_id, x, y

    def _update_trajectory_positions(self) -> None:
        """Updates all trajectory-based markers for the current playhead time."""
        for marker_id, x, y in self._iter_trajectory_positions():
            self.view.update_marker_position(marker_id, x, y)

    @Slot(float)
    def on_time_changed(self, time: float) -> None:
        """
        Receives playhead time updates from the Timeline.

        Updates the internal time state, refreshes the status display,
        and updates any trajectory-based markers.

        Args:
            time: Current playhead time in lore_date units.
        """
        # Round to 4 decimal places to prevent float precision drift
        # during rapid playhead scrubbing
        time = round(time, 4)

        self._playhead_time = time
        self.view._current_time = time
        self._update_time_display()

        # In Clock Mode: don't update positions, just track time for later commit
        if self._pinned_marker_id:
            logger.debug(
                f"Clock Mode: playhead={time:.1f}, "
                f"pinned={self._pinned_marker_id} "
                f"at orig_t={self._pinned_original_t:.1f}"
            )
            # Live update of the keyframe date label
            if self._pinned_original_t is not None:
                self.view.update_keyframe_label(
                    self._pinned_marker_id, self._pinned_original_t, time
                )
        else:
            # Normal Mode: update marker positions along trajectories
            self._update_trajectory_positions()

        logger.debug(f"Map playhead time updated to {time:.2f}")

    @Slot(float)
    def on_current_time_changed(self, time: float) -> None:
        """
        Receives current time ("Now") updates from the Timeline.

        This represents the story's current moment, distinct from the playhead.

        Args:
            time: Current time in lore_date units.
        """
        self._current_time = time
        self._update_time_display()
        logger.debug(f"Map current time (Now) updated to {time:.2f}")

    def _update_time_display(self) -> None:
        """Updates the coord_label to include playhead and current time."""
        # Get existing coordinate text or default
        current_text = self.coord_label.text()

        # Remove any existing time suffix
        if " | T:" in current_text:
            current_text = current_text.split(" | T:")[0]

        # Append time (Playhead and Now)
        time_str = f"T: {self._playhead_time:.1f} | Now: {self._current_time:.1f}"
        self.coord_label.setText(f"{current_text} | {time_str}")

    def set_maps(self, maps: list) -> None:
        """
        Populates the map selector with available maps.

        Args:
            maps: List of Map objects.
        """
        self.map_selector.blockSignals(True)
        self.map_selector.clear()
        self._maps_data = maps

        for m in maps:
            self.map_selector.addItem(m.name, m.id)

        self.map_selector.setCurrentIndex(-1)
        self.map_selector.blockSignals(False)

    def select_map(self, map_id: str) -> None:
        """Selects the map with the given ID in the dropdown."""
        index = self.map_selector.findData(map_id)
        if index >= 0:
            logger.debug(f"Selecting map index {index} for id {map_id}")
            self.map_selector.setCurrentIndex(index)
        else:
            logger.warning(f"Map ID {map_id} not found in selector")

    @Slot(int)
    def _on_map_selected(self, index: int) -> None:
        """Handle map selection change."""
        if index >= 0:
            map_id = self.map_selector.itemData(index)
            self.map_selected.emit(map_id)

    def get_selected_map_id(self) -> Optional[str]:
        """
        Returns the currently selected map ID.

        Returns:
            Optional[str]: The map ID, or None if no map is selected.
        """
        index = self.map_selector.currentIndex()
        return self.map_selector.itemData(index) if index >= 0 else None

    @Slot(str, float, float)
    def _on_marker_moved(self, marker_id: str, x: float, y: float) -> None:
        """
        Handles marker movement from the view.

        Updates the widget's marker position and emits signal for persistence.

        Args:
            marker_id: ID of the moved marker.
            x: New normalized X coordinate.
            y: New normalized Y coordinate.
        """
        # Update marker position in widget
        self.update_marker_position(marker_id, x, y)

        # Emit signal so app layer can persist the change
        self.marker_position_changed.emit(marker_id, x, y)

        logger.debug(f"MapWidget: marker {marker_id} moved to ({x:.3f}, {y:.3f})")

    @Slot(float, float, bool)
    def _on_mouse_coordinates_changed(
        self, x: float, y: float, in_bounds: bool
    ) -> None:
        """
        Updates the coordinate label.

        Args:
            x: Normalized X [0-1]
            y: Normalized Y [0-1]
            in_bounds: True if cursor is over the map image.
        """
        # Time suffix (always shown)
        time_str = f"T: {self._playhead_time:.1f} | Now: {self._current_time:.1f}"

        if not in_bounds:
            self.coord_label.setText(f"Ready | {time_str}")
            return

        # 1. Format Normalized
        norm_str = f"N: ({x:.4f}, {y:.4f})"

        # 2. Format Real World (KM)
        width_meters = self.view.map_width_meters

        # Calculate Aspect Ratio to find Height
        # Prefer the underlying map image bounds so that Y scaling
        # is tied to the actual map, not to dynamic scene extents.
        height_meters = width_meters  # Default fallback: square
        aspect_ratio = None

        pixmap_item = getattr(self.view, "pixmap_item", None)
        if pixmap_item is not None:
            img_rect = pixmap_item.boundingRect()
            if img_rect.width() > 0 and img_rect.height() > 0:
                aspect_ratio = img_rect.width() / img_rect.height()
        else:
            # Fallback: use sceneRect for aspect ratio if no pixmap is available
            scene_rect = self.view.sceneRect()
            if scene_rect.width() > 0 and scene_rect.height() > 0:
                aspect_ratio = scene_rect.width() / scene_rect.height()

        if aspect_ratio:
            height_meters = width_meters / aspect_ratio

        km_x = (x * width_meters) / 1000.0
        km_y = (y * height_meters) / 1000.0

        km_str = f"RW: {km_x:.2f} km, {km_y:.2f} km"

        self.coord_label.setText(f"{norm_str} | {km_str} | {time_str}")

    def load_map(self, image_path: str) -> bool:
        """
        Loads a map image.

        Args:
            image_path: Path to the image file.

        Returns:
            bool: True if successful, False otherwise.
        """
        return self.view.load_map(image_path)

    def add_marker(
        self,
        marker_id: str,
        object_type: str,
        label: str,
        x: float,
        y: float,
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """
        Adds a marker to the map.

        Args:
            marker_id: Unique identifier for the marker.
            object_type: Type of object ('entity' or 'event').
            label: Marker label text.
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].
            icon: Optional icon filename.
            color: Optional color hex string.
            description: Optional description for tooltip.
        """
        self.view.add_marker(
            marker_id, object_type, label, x, y, icon, color, description
        )

    def update_marker_position(self, marker_id: str, x: float, y: float) -> None:
        """
        Updates a marker's position.

        Args:
            marker_id: Unique identifier for the marker.
            x: Normalized X coordinate.
            y: Normalized Y coordinate.
        """
        self.view.update_marker_position(marker_id, x, y)

    def remove_marker(self, marker_id: str) -> None:
        """
        Removes a marker from the map.

        Args:
            marker_id: ID of the marker to remove.
        """
        self.view.remove_marker(marker_id)

    def clear_markers(self) -> None:
        """Removes all markers from the map."""
        self.view.clear_markers()

    def _configure_map_width(self) -> None:
        """Opens a dialog to configure the real-world width of the map."""
        if not self.view.pixmap_item:
            logger.warning("Ignoring request to configure map width: no map loaded.")
            return

        current_width = int(self.view.map_width_meters)
        width, ok = QInputDialog.getInt(
            self,
            "Map Scale Base",
            "Enter the real-world width of this map image (in meters):",
            current_width,
            100,  # Min 100m
            100_000_000,  # Max 100,000 km
            1000,  # Step
        )
        if ok:
            self.view.set_map_width_meters(float(width))
            logger.info(f"Map width set to {width} meters")

    def _emit_keyframe_upsert(
        self, marker_id: str, t: float, x: float, y: float, is_add: bool = False
    ) -> None:
        """Emits signal to upsert (add/update) a keyframe."""
        map_id = self.get_selected_map_id()
        if map_id:
            self.add_keyframe_requested.emit(map_id, marker_id, t, x, y)

            # Onboarding check - Only on new creation
            if is_add:
                settings = QSettings()
                if not settings.value(
                    "map/onboarding_keyframe_created", False, type=bool
                ):
                    self._show_onboarding_dialog()
                    settings.setValue("map/onboarding_keyframe_created", True)

    def _show_onboarding_dialog(self) -> None:
        """Shows the onboarding dialog for first-time keyframe creation."""
        dialog = OnboardingDialog(self)
        dialog.exec()

    @Slot(str, str)
    def _on_marker_clicked_internal(self, marker_id: str, object_type: str) -> None:
        """Internal handler for marker click to update visualization."""
        self._selected_marker_id = marker_id
        self._update_trajectory_visualization(marker_id)

    def _update_trajectory_visualization(self, marker_id: str) -> None:
        """Updates the view to show the trajectory for the given marker."""
        keyframes = self._active_trajectories.get(marker_id, [])
        if keyframes:
            self.view.show_trajectory(marker_id, keyframes)
        else:
            self.view.clear_trajectory()

    @Slot(str, float, float, float)
    def _on_keyframe_moved(self, marker_id: str, t: float, x: float, y: float) -> None:
        """Handle drag-to-edit of keyframes."""
        self._emit_keyframe_upsert(marker_id, t, x, y, is_add=False)

    def _enter_clock_mode(self, marker_id: str, t: float) -> None:
        """Transition: Default -> Clock Mode."""
        if self._pinned_marker_id:
            self._cancel_clock_mode()  # clear previous without commit
        logger.info(f"Clock Mode activated for marker {marker_id} at t={t}")
        self._pinned_marker_id = marker_id
        self._pinned_original_t = t
        self.view.set_keyframe_pinned(marker_id, t, True)

        # Update UI state
        self._update_mode_indicator("clock", marker_id)

        # Jump playhead to keyframe time
        self.jump_to_time_requested.emit(t)

    def _commit_clock_mode(self) -> None:
        """Transition: Clock Mode -> Default (Committing change)."""
        if not (self._pinned_marker_id and self._pinned_original_t is not None):
            return

        # Check if time actually changed and playhead checks pass
        map_id = self.get_selected_map_id()
        if (
            map_id
            and self._playhead_time is not None
            and abs(self._playhead_time - self._pinned_original_t)
            > KEYFRAME_TIME_EPSILON
        ):
            logger.info(
                f"Unpinning {self._pinned_marker_id}: "
                f"{self._pinned_original_t:.1f} → {self._playhead_time:.1f}"
            )
            self.update_keyframe_time_requested.emit(
                map_id,
                self._pinned_marker_id,
                self._pinned_original_t,
                self._playhead_time,
            )

        self._clear_clock_mode_visuals()

    def _cancel_clock_mode(self) -> None:
        """Transition: Clock Mode -> Default (Aborting change)."""
        logger.info("Clock Mode cancelled")
        self._clear_clock_mode_visuals()

    def _update_mode_indicator(
        self, mode: str, marker_id: Optional[str] = None
    ) -> None:
        """Updates the toolbar status and map overlay."""
        if mode == "clock":
            # Toolbar Widget
            self.mode_indicator.setText(f'🔴 CLOCK MODE: Editing "{marker_id}"')
            self.mode_indicator.setStyleSheet(
                """
                QLabel {
                    background: #e74c3c;
                    color: white;
                    padding: 5px 12px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 11px;
                }
            """
            )

            # Overlay Banner
            banner_text = (
                "⏱ <b>CLOCK MODE ACTIVE</b><br/>"
                "Scrub timeline to adjust keyframe timestamp<br/>"
                "<small>[Esc to Cancel] [Enter to Commit]</small>"
            )
            self.overlay_banner.setText(banner_text)
            self.overlay_banner.show()
            self._update_overlay_position()

            # Cursor Change
            self.view.setCursor(Qt.CursorShape.WaitCursor)
        else:
            # Toolbar Widget
            self.mode_indicator.setText("Normal Mode")
            self.mode_indicator.setStyleSheet(
                """
                QLabel {
                    background: #2ecc71;
                    color: white;
                    padding: 5px 12px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 11px;
                }
            """
            )

            # Overlay Banner
            self.overlay_banner.hide()

            # Reset Cursor
            self.view.unsetCursor()

    def _clear_clock_mode_visuals(self) -> None:
        """Resets visual pinned state and internal tracking."""
        if self._pinned_marker_id and self._pinned_original_t is not None:
            self.view.set_keyframe_pinned(
                self._pinned_marker_id, self._pinned_original_t, False
            )
        self._pinned_marker_id = None
        self._pinned_original_t = None
        self._update_mode_indicator("normal")

    def _handle_clock_mode_time_change(self, time: float) -> None:
        """Log or process time changes while in Clock Mode (without moving marker)."""
        logger.debug(
            f"Clock Mode: playhead={time:.1f}, "
            f"pinned={self._pinned_marker_id} "
            f"at orig_t={self._pinned_original_t:.1f}"
        )

    @Slot(str, float)
    def _on_clock_mode_requested(self, marker_id: str, t: float) -> None:
        """Enter/Exit Clock Mode - toggle pin/unpin for temporal editing."""
        if self._pinned_marker_id == marker_id:
            logger.info(f"Clock Mode: Committing changes for {marker_id}")
            self._commit_clock_mode()
        else:
            if self._pinned_marker_id:
                logger.info(
                    f"Clock Mode: Switching from "
                    f"{self._pinned_marker_id} to {marker_id}"
                )
            self._enter_clock_mode(marker_id, t)

    def set_calendar_converter(self, converter: object) -> None:
        """Sets the calendar converter for formatting keyframe date labels."""
        self.view.set_calendar_converter(converter)

    @Slot(str, float)
    def _on_keyframe_delete_requested(self, marker_id: str, t: float) -> None:
        """
        Handle keyframe delete request from gizmo.

        Args:
            marker_id: The ID of the marker (object_id).
            t: The timestamp of the keyframe to delete.
        """
        map_id = self.map_selector.currentData()
        if not map_id:
            logger.warning("Cannot delete keyframe: no map selected")
            return

        logger.info(f"Requesting keyframe delete: marker={marker_id}, t={t}")
        self.delete_keyframe_requested.emit(map_id, marker_id, t)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard shortcuts for MapWidget."""
        if self._pinned_marker_id:
            if event.key() == Qt.Key_Escape:
                self._cancel_clock_mode()
                event.accept()
                return
            elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._commit_clock_mode()
                event.accept()
                return

        super().keyPressEvent(event)

    def _update_overlay_position(self) -> None:
        """Centers the overlay banner at the top of the view."""
        if hasattr(self, "overlay_banner") and self.overlay_banner.isVisible():
            view_width = self.view.width()
            banner_width = self.overlay_banner.sizeHint().width()
            x = (view_width - banner_width) // 2
            self.overlay_banner.move(x, 0)
            self.overlay_banner.setFixedWidth(banner_width)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Handle resize to keep overlay centered."""
        super().resizeEvent(event)
        self._update_overlay_position()


class OnboardingDialog(QDialog):
    """Onboarding dialog shown when the first keyframe is created."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("✨ Keyframe Created!")
        self.setFixedWidth(400)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #2c3e50;
                color: white;
            }
            QLabel {
                color: white;
                font-size: 13px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("✨ Keyframe Created!")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        body = QLabel(
            "Hover over yellow dots to reveal editing tools:<br/>"
            "• <b>Drag</b> to adjust position<br/>"
            "• Click 🕐 to adjust <b>timing</b> (Clock Mode)<br/>"
            "• Click ✕ to <b>delete</b>"
        )
        body.setWordWrap(True)
        layout.addWidget(body)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_got_it = QPushButton("Got it!")
        self.btn_got_it.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_got_it)

        self.btn_tutorial = QPushButton("Show Tutorial Video")
        self.btn_tutorial.setStyleSheet("background-color: #7f8c8d;")
        # In a real app, this would open a URL
        self.btn_tutorial.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_tutorial)

        layout.addLayout(btn_layout)
