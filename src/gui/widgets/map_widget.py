"""Map Widget Module.

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
import uuid
from typing import Iterator, List, Optional, Tuple

from PySide6.QtCore import QSettings, QSize, Qt, Signal, Slot
from PySide6.QtGui import QKeyEvent, QPaintEvent, QResizeEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.app.constants import (
    IMAGE_FILE_FILTER,
    MAP_LAYER_DEFAULT_GROUP_NAME,
    MAP_LAYER_TYPE_GROUP,
    MAP_LAYER_TYPE_MARKER,
    MAP_LAYER_TYPE_PATH,
    MAP_LAYER_TYPE_REGION,
)
from src.core.map import MapLayerNode
from src.core.paths import get_resource_path
from src.core.theme_manager import ThemeManager
from src.core.trajectory import KEYFRAME_TIME_EPSILON, interpolate_position
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.map.calibration_distance_dialog import CalibrationDistanceDialog
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.map.map_layer_model import MapLayerModel
from src.gui.widgets.map.map_layer_panel import MapLayerPanel
from src.gui.widgets.map.map_scale_dialog import MapScaleDialog
from src.gui.widgets.map.marker_item import MarkerItem

logger = logging.getLogger(__name__)

# Path to marker icons
MARKER_ICONS_PATH = get_resource_path(
    os.path.join("default_assets", "icons", "markers")
)


def get_available_icons() -> List[str]:
    """Returns a list of available marker icon filenames.

    Returns:
        List[str]: List of .svg filenames in the markers folder.

    """
    if not os.path.exists(MARKER_ICONS_PATH):
        return []
    return [f for f in os.listdir(MARKER_ICONS_PATH) if f.endswith(".svg")]


class NoLayoutLabel(QWidget):
    """A minimal label that draws text without participating in layout.

    This solves the infinite resize loop where updating text triggers layout
    recalculation, which resizes docks, which triggers more updates.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        """Initialize the scale indicator label.

        Args:
            text: Initial text to display.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._text = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def setText(self, text: str) -> None:
        """Set the label text without triggering layout recalculation.

        Args:
            text: New text to display.
        """
        if self._text != text:
            self._text = text
            # Trigger paint directly - DO NOT call updateGeometry
            self.update()

    def text(self) -> str:
        """Get the current label text.

        Returns:
            The current text string.
        """
        return self._text

    def sizeHint(self) -> QSize:
        """Get the preferred size hint.

        Returns:
            Fixed size of 50x20 pixels.
        """
        # minimal fixed size
        return QSize(50, 20)

    def minimumSizeHint(self) -> QSize:
        """Get the minimum size hint.

        Returns:
            Minimum size of 50x20 pixels.
        """
        return QSize(50, 20)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the scale indicator text.

        Args:
            event: The paint event.
        """
        from PySide6.QtGui import QColor, QPainter

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw text aligned right
        painter.setPen(QColor("#888888"))

        # Basic font setup - can be enhanced if needed
        # We assume styling is minimal
        # Since we bypass stylesheet drawing, we must draw manually

        rect = self.rect().adjusted(0, 0, -5, 0)  # Padding right
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            self._text,
        )


class MapWidget(QWidget):
    """Container widget for the map view.

    Provides a clean interface to the map system with signal routing.

    Signals:
        marker_position_changed: Emitted when a marker is moved by the user.
                                Args: (marker_id: str, x: float, y: float)
                                Coordinates are normalized [0.0, 1.0].
    """

    marker_position_changed = Signal(str, float, float)
    marker_clicked = Signal(str, str)
    # map_created carries (file_path, name) after user completes dialogs
    map_created = Signal(str, str)
    # map_deleted carries map_id after user confirms
    map_deleted = Signal(str)
    map_selected = Signal(str)  # map_id
    # marker_created carries (map_id, obj_id, obj_type, name, x, y)
    marker_created = Signal(str, str, str, str, float, float)
    # marker_delete_confirmed carries marker_id after user confirms
    marker_delete_confirmed = Signal(str)
    change_marker_icon_requested = Signal(str, str)  # marker_id, new_icon
    change_marker_color_requested = Signal(str, str)  # marker_id, new_color_hex
    marker_drop_requested = Signal(str, str, str, float, float)  # id, type, name, x, y
    # feature_created carries (map_id, obj_id, obj_type, name, feature_type, geometry)
    feature_created = Signal(str, str, str, str, str, list)
    feature_style_changed = Signal(str, dict)  # marker_id, new style
    feature_geometry_changed = Signal(str, list)  # marker_id, new geometry
    add_keyframe_requested = Signal(
        str, str, float, float, float
    )  # map_id, marker_id, t, x, y
    update_keyframe_time_requested = Signal(
        str, str, float, float
    )  # map_id, marker_id, old_t, new_t
    delete_keyframe_requested = Signal(str, str, float)  # map_id, marker_id, t
    jump_to_time_requested = Signal(float)  # target_time
    map_scale_changed = Signal(float)  # For persisting map scale
    show_onboarding_requested = Signal()  # To trigger animation or hints
    # Layer operations (routed through the command stack)
    layer_tree_changed = Signal()  # auto-persist hook
    layer_opacity_change_requested = Signal(
        str, float, float
    )  # node_id, opacity, old_opacity
    layer_rename_requested = Signal(str, str)  # node_id, new_name
    layer_delete_feature_requested = Signal(str)  # object_id of deleted leaf

    # Emitted when inline entity/event creation is requested from the map.
    create_entity_requested = Signal(str, str)  # new_id, name
    create_event_requested = Signal(str, str)  # new_id, name

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initializes the MapWidget.

        Args:
            parent: Parent widget.

        """
        super().__init__(parent)

        # Create view
        self.view = MapGraphicsView(self)

        self._pinned_marker_id: Optional[str] = None
        self._pinned_original_t: Optional[float] = None

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Toolbar
        self.toolbar = QToolBar(self)
        self.toolbar.setStyleSheet("QToolBar { spacing: 4px; padding: 4px; }")
        layout.addWidget(self.toolbar)

        # Map Selector
        self.map_selector = QComboBox()
        self.map_selector.setMinimumWidth(200)
        self.map_selector.currentIndexChanged.connect(self._on_map_selected)
        self.toolbar.addWidget(self.map_selector)

        # Buttons (themed via StyleHelper)
        tool_style = StyleHelper.get_tool_button_style()

        self.btn_new_map = QPushButton("New Map")
        self.btn_new_map.setStyleSheet(tool_style)
        self.btn_new_map.clicked.connect(self._on_create_map_clicked)
        self.toolbar.addWidget(self.btn_new_map)

        self.btn_delete_map = QPushButton("Delete Map")
        self.btn_delete_map.setStyleSheet(StyleHelper.get_destructive_button_style())
        self.btn_delete_map.clicked.connect(self._on_delete_map_clicked)
        self.toolbar.addWidget(self.btn_delete_map)

        self.btn_fit_view = QPushButton("Fit to View")
        self.btn_fit_view.setStyleSheet(tool_style)
        self.btn_fit_view.clicked.connect(self.view.fit_to_view)
        self.toolbar.addWidget(self.btn_fit_view)

        self.btn_settings = QPushButton("Settings")
        self.btn_settings.setToolTip("Configure Map Properties (Scale)")
        self.btn_settings.setStyleSheet(tool_style)
        self.btn_settings.clicked.connect(self._configure_map_width)
        self.toolbar.addWidget(self.btn_settings)

        self.btn_add_keyframe = QPushButton("Add Keyframe")
        self.btn_add_keyframe.setToolTip("Save current marker position at current time")
        self.btn_add_keyframe.setStyleSheet(tool_style)
        self.btn_add_keyframe.clicked.connect(self._on_add_keyframe)
        self.toolbar.addWidget(self.btn_add_keyframe)

        # Drawing tool buttons
        self.btn_draw_path = QPushButton("Draw Path")
        self.btn_draw_path.setToolTip(
            "Draw a polyline path on the map (click vertices, double-click to finish)"
        )
        self.btn_draw_path.setCheckable(True)
        self.btn_draw_path.setStyleSheet(tool_style)
        self.btn_draw_path.clicked.connect(self._on_draw_path_clicked)
        self.toolbar.addWidget(self.btn_draw_path)

        self.btn_draw_region = QPushButton("Draw Region")
        self.btn_draw_region.setToolTip(
            "Draw a polygon region on the map (click vertices, double-click to finish)"
        )
        self.btn_draw_region.setCheckable(True)
        self.btn_draw_region.setStyleSheet(tool_style)
        self.btn_draw_region.clicked.connect(self._on_draw_region_clicked)
        self.toolbar.addWidget(self.btn_draw_region)

        # Snap toggle
        self.btn_snap = QPushButton("Snap")
        self.btn_snap.setToolTip("Toggle snapping to nearby feature vertices and edges")
        self.btn_snap.setCheckable(True)
        self.btn_snap.setChecked(True)  # enabled by default
        self.btn_snap.setStyleSheet(tool_style)
        self.btn_snap.clicked.connect(self._on_snap_toggled)
        self.toolbar.addWidget(self.btn_snap)

        # Mode Indicator (right side)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)

        self.mode_indicator = QLabel("Normal Mode")
        self._apply_mode_indicator_style("normal")
        self.toolbar.addWidget(self.mode_indicator)

        # Add View (after toolbar) — wrapped in a splitter with the layer panel
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)

        self._splitter.addWidget(self.view)

        # Layer Panel (right side)
        self.layer_panel = MapLayerPanel(self)
        self._splitter.addWidget(self.layer_panel)

        # Default proportions: 80% map, 20% layer panel
        self._splitter.setStretchFactor(0, 4)
        self._splitter.setStretchFactor(1, 1)

        layout.addWidget(self._splitter)

        # Layer model (created per-map; None until markers load)
        self._layer_model: Optional[MapLayerModel] = None

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

        # Finish Sketch button (shown during drawing/vertex editing)
        self.btn_finish_sketch = QPushButton("✔ Finish Sketch", self.view)
        self.btn_finish_sketch.setStyleSheet(StyleHelper.get_primary_button_style())
        self.btn_finish_sketch.clicked.connect(self._on_finish_sketch)
        self.btn_finish_sketch.hide()

        # Coordinate Label
        self.coord_label = NoLayoutLabel("Ready")

        # Prevent label from pushing layout width when text changes
        self.coord_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
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
        self.view.add_marker_requested.connect(self._on_create_marker_requested)
        self.view.delete_marker_requested.connect(self._on_delete_marker_requested)
        self.view.change_marker_icon_requested.connect(
            self.change_marker_icon_requested.emit
        )
        self.view.change_marker_color_requested.connect(
            self.change_marker_color_requested.emit
        )
        self.view.marker_drop_requested.connect(self.marker_drop_requested.emit)
        self.view.mouse_coordinates_changed.connect(self._on_mouse_coordinates_changed)
        self.view.drawing_finished.connect(self._on_drawing_finished)
        self.view.drawing_cancelled.connect(self._on_drawing_cancelled)
        self.view.feature_style_changed.connect(self.feature_style_changed.emit)
        self.view.feature_geometry_changed.connect(self.feature_geometry_changed.emit)
        self.view.feature_geometry_changed.connect(self._on_geometry_changed)
        self.view.scene.selectionChanged.connect(self._on_selection_changed)
        # Bi-directional selection: marker click → highlight in layer panel
        self.view.marker_clicked.connect(self._on_marker_clicked_select_layer)
        self.layer_panel.layer_selected.connect(self._on_layer_panel_selected)
        # Layer panel actions
        self.layer_panel.create_group_requested.connect(self._on_create_group)
        self.layer_panel.create_layer_requested.connect(self._on_create_layer)
        self.layer_panel.delete_layer_requested.connect(self._on_delete_layer)
        self.layer_panel.layer_renamed.connect(self._on_layer_renamed)
        self.layer_panel.layer_opacity_changed.connect(self._on_layer_opacity_changed)

        self._maps_data = []  # List of maps for selector
        self._playhead_time: float = 0.0  # Current playhead time from Timeline
        self._current_time: float = 0.0  # Story's "Now" time from Timeline

        self._active_trajectories: dict[str, list] = {}  # marker_id -> list[Keyframe]
        self._selected_marker_id: Optional[str] = None
        self._transient_marker_ids: set[str] = set()  # Markers currently being dragged

        # Entity/event caches for the object-selection dialog
        self._cached_entities: list = []
        self._cached_events: list = []

        # Update all markers with active trajectories
        self._update_trajectory_positions()

    def _on_selection_changed(self) -> None:
        """Updates UI state based on selection."""
        # Clear transient states on selection change to ensure markers snap back
        if self._transient_marker_ids:
            logger.debug("Selection changed: clearing transient marker states")
            self._transient_marker_ids.clear()
            self._update_trajectory_positions(force_all=True)
            self._update_mode_indicator()

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
        """Sets the active trajectories for the current map.

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
        self._transient_marker_ids.clear()
        self._update_trajectory_positions()
        self._update_mode_indicator()

        # Update visualization if selection exists
        if self._selected_marker_id:
            self._update_trajectory_visualization(self._selected_marker_id)

    # Note: Skipping unrelated methods to reach _on_add_keyframe

    @Slot()
    def _on_add_keyframe(self) -> None:
        """Captures the current position of the selected marker and saves it as a
        keyframe.
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

    # ------------------------------------------------------------------
    # Drawing Mode
    # ------------------------------------------------------------------

    @Slot()
    def _on_draw_path_clicked(self) -> None:
        """Toggles path drawing mode."""
        if self.view.is_drawing:
            self.view.cancel_drawing()
            return
        self.btn_draw_region.setChecked(False)
        self.view.start_drawing("path")
        self._update_mode_indicator()

    @Slot()
    def _on_draw_region_clicked(self) -> None:
        """Toggles region drawing mode."""
        if self.view.is_drawing:
            self.view.cancel_drawing()
            return
        self.btn_draw_path.setChecked(False)
        self.view.start_drawing("region")
        self._update_mode_indicator()

    @Slot(str, list)
    def _on_drawing_finished(self, feature_type: str, geometry: list) -> None:
        """Handles drawing completion — shows object picker then emits feature_created.

        Args:
            feature_type: 'path' or 'region'.
            geometry: List of normalized coordinate dicts.

        """
        self.btn_draw_path.setChecked(False)
        self.btn_draw_region.setChecked(False)
        self._update_mode_indicator()

        map_id = self.get_selected_map_id()
        if not map_id:
            QMessageBox.warning(
                self, "No Map", "Please create or select a map first."
            )
            return

        result = self._select_or_create_object(
            f"Link {feature_type.title()}",
            f"Select object for this {feature_type}:",
        )
        if not result:
            return

        obj_id, obj_type, name = result
        self.feature_created.emit(map_id, obj_id, obj_type, name, feature_type, geometry)
        logger.info(
            f"Feature drawing complete: {feature_type}, {len(geometry)} vertices"
        )

    @Slot()
    def _on_drawing_cancelled(self) -> None:
        """Handles drawing cancellation — resets UI state."""
        self.btn_draw_path.setChecked(False)
        self.btn_draw_region.setChecked(False)
        self._update_mode_indicator()

    # ------------------------------------------------------------------
    # Dialog methods (UI layer owns all user-facing dialogs)
    # ------------------------------------------------------------------

    # Sentinel values for the object-selection dialog
    _NEW_ENTITY_SENTINEL = "<New Entity...>"
    _NEW_EVENT_SENTINEL = "<New Event...>"

    def set_cached_items(
        self, entities: list, events: list
    ) -> None:
        """Stores the entity/event caches for the object-selection dialog.

        Called by MainWindow when data is refreshed so the map's
        object-picker dialog can offer existing entities and events.

        Args:
            entities: List of entity objects.  Each must have ``.id``
                (``str``) and ``.name`` (``str``) attributes.
            events: List of event objects.  Each must have ``.id``
                (``str``) and ``.name`` (``str``) attributes.

        """
        self._cached_entities = entities
        self._cached_events = events

    def _select_or_create_object(
        self, dialog_title: str, dialog_label: str
    ) -> tuple[str, str, str] | None:
        """Shows a selection dialog with existing items + new-item options.

        Returns:
            Tuple of (object_id, object_type, name) on success, or None
            if the user cancels.

        """
        entities = getattr(self, "_cached_entities", [])
        events = getattr(self, "_cached_events", [])

        items: list[str] = [
            self._NEW_ENTITY_SENTINEL,
            self._NEW_EVENT_SENTINEL,
        ]
        for e in entities:
            items.append(f"{e.name} (Entity)")
        for e in events:
            items.append(f"{e.name} (Event)")

        # Sort existing items, keep sentinels at top
        sentinels = items[:2]
        existing = sorted(items[2:])
        items = sentinels + existing

        item_text, ok = QInputDialog.getItem(
            self, dialog_title, dialog_label, items, 0, False
        )
        if not ok or not item_text:
            return None

        if item_text == self._NEW_ENTITY_SENTINEL:
            return self._create_new_entity_inline()
        if item_text == self._NEW_EVENT_SENTINEL:
            return self._create_new_event_inline()

        if item_text.endswith(" (Entity)"):
            name = item_text[:-9]
            obj = next((e for e in entities if e.name == name), None)
            if obj:
                return obj.id, "entity", obj.name
        elif item_text.endswith(" (Event)"):
            name = item_text[:-8]
            obj = next((e for e in events if e.name == name), None)
            if obj:
                return obj.id, "event", obj.name

        return None

    def _create_new_entity_inline(self) -> tuple[str, str, str] | None:
        """Prompts for a name and emits ``create_entity_requested``.

        Returns:
            Tuple of (new_id, 'entity', name) or None if cancelled.

        """
        name, ok = QInputDialog.getText(self, "New Entity", "Entity Name:")
        if not ok or not name.strip():
            return None
        name = name.strip()
        new_id = str(uuid.uuid4())
        self.create_entity_requested.emit(new_id, name)
        logger.info(f"Created new entity '{name}' ({new_id}) from map")
        return new_id, "entity", name

    def _create_new_event_inline(self) -> tuple[str, str, str] | None:
        """Prompts for a name and emits ``create_event_requested``.

        Returns:
            Tuple of (new_id, 'event', name) or None if cancelled.

        """
        name, ok = QInputDialog.getText(self, "New Event", "Event Name:")
        if not ok or not name.strip():
            return None
        name = name.strip()
        new_id = str(uuid.uuid4())
        self.create_event_requested.emit(new_id, name)
        logger.info(f"Created new event '{name}' ({new_id}) from map")
        return new_id, "event", name

    @Slot()
    def _on_create_map_clicked(self) -> None:
        """Shows file/name dialogs and emits ``map_created``."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Map Image", "", IMAGE_FILE_FILTER
        )
        if not file_path:
            return
        name, ok = QInputDialog.getText(self, "New Map", "Map Name:")
        if not ok or not name.strip():
            return
        self.map_created.emit(file_path, name.strip())

    @Slot()
    def _on_delete_map_clicked(self) -> None:
        """Shows confirmation dialog and emits ``map_deleted``."""
        map_id = self.map_selector.currentData()
        if not map_id:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Map",
            "Are you sure you want to delete this map and all its markers?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.map_deleted.emit(map_id)

    @Slot(float, float)
    def _on_create_marker_requested(self, x: float, y: float) -> None:
        """Shows object-selection dialog and emits ``marker_created``."""
        map_id = self.get_selected_map_id()
        if not map_id:
            QMessageBox.warning(
                self, "No Map", "Please create or select a map first."
            )
            return
        result = self._select_or_create_object("Add Marker", "Select Object:")
        if not result:
            return
        obj_id, obj_type, name = result
        self.marker_created.emit(map_id, obj_id, obj_type, name, x, y)

    @Slot(str)
    def _on_delete_marker_requested(self, marker_id: str) -> None:
        """Shows confirmation dialog and emits ``marker_delete_confirmed``."""
        confirm = QMessageBox.question(
            self,
            "Delete Marker",
            "Remove this marker?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.marker_delete_confirmed.emit(marker_id)

    @Slot()
    def _on_snap_toggled(self) -> None:
        """Toggles snapping on the map view."""
        self.view.snapping_enabled = self.btn_snap.isChecked()

    @Slot()
    def _on_finish_sketch(self) -> None:
        """Handles the Finish Sketch button click.

        Completes the current drawing or vertex editing session.
        """
        if self.view.is_drawing:
            self.view.finish_drawing()
        elif self.view.is_editing_vertices:
            self.view.finish_editing()
        self._update_mode_indicator()

    @Slot(str, list)
    def _on_geometry_changed(self, marker_id: str, geometry: list) -> None:
        """Refreshes mode indicator when vertex editing completes.

        Args:
            marker_id: The feature whose geometry changed.
            geometry: The updated geometry list.

        """
        self._update_mode_indicator()

    def _iter_trajectory_positions(self) -> Iterator[Tuple[str, float, float]]:
        """Yield (marker_id, x, y) for markers with trajectories at current time."""
        for marker_id, keyframes in self._active_trajectories.items():
            position = interpolate_position(keyframes, self._playhead_time)
            if position:
                x, y = position
                yield marker_id, x, y

    def _update_trajectory_positions(self, force_all: bool = False) -> None:
        """Updates all trajectory-based markers for the current playhead time.

        Args:
            force_all: If True, even markers in transient state are snapped back.

        """
        for marker_id, x, y in self._iter_trajectory_positions():
            if not force_all and marker_id in self._transient_marker_ids:
                logger.debug(f"Skipping update for transient marker {marker_id}")
                continue
            self.view.update_marker_position(marker_id, x, y)

    @Slot(float)
    def on_time_changed(self, time: float) -> None:
        """Receives playhead time updates from the Timeline.

        Updates the internal time state, refreshes the status display,
        and updates any trajectory-based markers.

        Args:
            time: Current playhead time in lore_date units.

        """
        # Round to 4 decimal places to prevent float precision drift
        # during rapid playhead scrubbing
        time = round(time, 4)

        self._playhead_time = time
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
            # When playhead moves, we force a snap-back to the authoritative path
            self._transient_marker_ids.clear()
            self._update_trajectory_positions(force_all=True)

        # Update marker visuals (dull/vivid) based on new time
        self.view.update_markers_temporal_state(self._playhead_time, self._current_time)

    @Slot(float)
    def on_current_time_changed(self, time: float) -> None:
        """Receives current time ("Now") updates from the Timeline.

        This represents the story's current moment, distinct from the playhead.

        Args:
            time: Current time in lore_date units.

        """
        self._current_time = time
        self._update_time_display()

        # Update marker visuals (dull/vivid) based on new 'Now'
        self.view.update_markers_temporal_state(self._playhead_time, self._current_time)

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
        """Populates the map selector with available maps.

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
        """Handle map selection change.

        Automatically exits any active drawing or vertex editing mode
        when the user switches to a different map layer.
        """
        # Exit active editing modes before switching maps
        if self.view.is_drawing:
            self.view.cancel_drawing()
        if self.view.is_editing_vertices:
            self.view.finish_editing()
        self._update_mode_indicator()

        if index >= 0:
            map_id = self.map_selector.itemData(index)
            self.map_selected.emit(map_id)

    def get_selected_map_id(self) -> Optional[str]:
        """Returns the currently selected map ID.

        Returns:
            Optional[str]: The map ID, or None if no map is selected.

        """
        index = self.map_selector.currentIndex()
        return self.map_selector.itemData(index) if index >= 0 else None

    @property
    def maps_data(self) -> list:
        """The currently loaded list of :class:`Map` objects."""
        return self._maps_data

    @Slot(str, float, float)
    def _on_marker_moved(self, marker_id: str, x: float, y: float) -> None:
        """Handles marker movement from the view.

        Updates the widget's marker position and emits signal for persistence.

        Args:
            marker_id: ID of the moved marker.
            x: New normalized X coordinate.
            y: New normalized Y coordinate.

        """
        # If marker has a trajectory, we enter "Transient State" instead of persisting
        if marker_id in self._active_trajectories:
            self._transient_marker_ids.add(marker_id)
            self.update_marker_position(marker_id, x, y)
            self._update_mode_indicator()
            logger.info(
                f"Marker {marker_id} in Transient State (Draft Mode). "
                "Click 'Add Keyframe' to save."
            )
            return

        # No trajectory: update marker position in widget and persist
        self.update_marker_position(marker_id, x, y)

        # Emit signal so app layer can persist the change
        self.marker_position_changed.emit(marker_id, x, y)

        logger.debug(f"MapWidget: marker {marker_id} moved to ({x:.3f}, {y:.3f})")

    @Slot(float, float, bool)
    def _on_mouse_coordinates_changed(
        self, x: float, y: float, in_bounds: bool
    ) -> None:
        """Updates the coordinate label.

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

        new_text = f"{norm_str} | {km_str} | {time_str}"

        # Only update if text changed
        if self.coord_label.text() != new_text:
            self.coord_label.setText(new_text)
            # logger.debug(f"Coords updated: {new_text} | Label Width Hint: {self.coord_label.sizeHint().width()}")

    def load_map(self, image_path: str) -> bool:
        """Loads a map image.

        Args:
            image_path: Path to the image file.

        Returns:
            bool: True if successful, False otherwise.

        """
        return self.view.load_map(image_path)

    # ------------------------------------------------------------------
    # Layer management
    # ------------------------------------------------------------------

    def _build_layer_model(self, root: Optional[MapLayerNode] = None) -> MapLayerModel:
        """Create (or replace) the layer model and wire it to the view.

        Args:
            root: An existing layer tree root.  If ``None`` a default
                root with a "Default" group is created.

        Returns:
            MapLayerModel: The newly created model.

        """
        if root is None:
            root = MapLayerNode(
                name="Root",
                layer_type=MAP_LAYER_TYPE_GROUP,
                children=[
                    MapLayerNode(
                        name=MAP_LAYER_DEFAULT_GROUP_NAME,
                        layer_type=MAP_LAYER_TYPE_GROUP,
                    ),
                ],
            )
        model = MapLayerModel(root=root)
        self._layer_model = model
        self.view.set_layer_model(model)
        self.layer_panel.set_model(model)
        # Forward model mutations → widget signal for command-stack persistence
        model.layer_tree_changed.connect(self.layer_tree_changed.emit)
        return model

    def _ensure_layer_model(self) -> MapLayerModel:
        """Return the current layer model, creating one if needed.

        Returns:
            MapLayerModel: The active layer model.

        """
        if self._layer_model is None:
            return self._build_layer_model()
        return self._layer_model

    def _default_group(self) -> MapLayerNode:
        """Return the "Default" group in the layer tree, creating it if needed.

        Returns:
            MapLayerNode: The default group node.

        """
        model = self._ensure_layer_model()
        # Try to find an existing "Default" group
        for child in model.root.children:
            if (
                child.layer_type == MAP_LAYER_TYPE_GROUP
                and child.name == MAP_LAYER_DEFAULT_GROUP_NAME
            ):
                return child
        # Create one
        node = MapLayerNode(
            name=MAP_LAYER_DEFAULT_GROUP_NAME,
            layer_type=MAP_LAYER_TYPE_GROUP,
        )
        root_idx = model.index_from_node(model.root)
        model.add_layer(root_idx, node)
        return node

    def _feature_type_to_layer_type(self, feature_type: str) -> str:
        """Map a feature_type string to a layer_type constant.

        Args:
            feature_type: 'point', 'path', or 'region'.

        Returns:
            str: The corresponding MAP_LAYER_TYPE_* constant.

        """
        if feature_type == "path":
            return MAP_LAYER_TYPE_PATH
        if feature_type == "region":
            return MAP_LAYER_TYPE_REGION
        return MAP_LAYER_TYPE_MARKER

    def _register_layer_node(
        self,
        marker_id: str,
        label: str,
        feature_type: str = "point",
    ) -> None:
        """Register a new feature as a layer node under the Default group.

        If a node with this ID already exists in the tree, it is skipped.

        Args:
            marker_id: Unique identifier (same as graphics item key).
            label: Display name for the layer.
            feature_type: 'point', 'path', or 'region'.

        """
        model = self._ensure_layer_model()
        if model.find_node_by_id(marker_id) is not None:
            return  # Already tracked

        layer_type = self._feature_type_to_layer_type(feature_type)
        node = MapLayerNode(name=label, layer_type=layer_type, id=marker_id)
        default_group = self._default_group()
        parent_idx = model.index_from_node(default_group)
        model.add_layer(parent_idx, node)

    def _unregister_layer_node(self, marker_id: str) -> None:
        """Remove a layer node when the corresponding feature is deleted.

        Prevents "zombie nodes" (MEDIUM-7).

        Args:
            marker_id: ID of the node to remove.

        """
        if self._layer_model is None:
            return
        node = self._layer_model.find_node_by_id(marker_id)
        if node is None:
            return
        idx = self._layer_model.index_from_node(node)
        self._layer_model.remove_layer(idx)

    @Slot(str, str)
    def _on_marker_clicked_select_layer(self, marker_id: str, object_type: str) -> None:
        """Bi-directional selection: marker click → highlight in layer panel.

        Args:
            marker_id: The clicked marker's ID.
            object_type: 'entity' or 'event' (unused here).

        """
        self.layer_panel.select_node(marker_id)

    @Slot(str)
    def _on_layer_panel_selected(self, node_id: str) -> None:
        """Bi-directional selection: layer panel click → select on map.

        Args:
            node_id: The clicked layer node's ID.

        """
        # Select the graphics item on the map
        item = self.view.find_item_by_id(node_id)
        if item is not None:
            self.view.scene.clearSelection()
            item.setSelected(True)

    @Slot(str)
    def _on_create_group(self, name: str) -> None:
        """Handle request to create a new layer group.

        The group is added under the root of the layer tree.

        Args:
            name: Display name for the new group.

        """
        model = self._ensure_layer_model()
        node = MapLayerNode(name=name, layer_type=MAP_LAYER_TYPE_GROUP)
        root_idx = model.index_from_node(model.root)
        model.add_layer(root_idx, node)
        logger.info(f"Created layer group: {name}")

    @Slot(str)
    def _on_create_layer(self, name: str) -> None:
        """Handle request to create a new leaf layer.

        The layer is added under the selected group, or the Default group
        if no group is selected.

        Args:
            name: Display name for the new layer.

        """
        model = self._ensure_layer_model()
        node = MapLayerNode(name=name, layer_type=MAP_LAYER_TYPE_MARKER)

        # Find a suitable parent — the selected node if it's a group,
        # else the Default group
        parent_node = None
        selected_id = self.layer_panel.selected_node_id
        if selected_id:
            selected_node = model.find_node_by_id(selected_id)
            if selected_node and selected_node.layer_type == MAP_LAYER_TYPE_GROUP:
                parent_node = selected_node

        if parent_node is None:
            parent_node = self._default_group()

        parent_idx = model.index_from_node(parent_node)
        model.add_layer(parent_idx, node)
        logger.info(f"Created layer: {name}")

    @Slot(str)
    def _on_delete_layer(self, node_id: str) -> None:
        """Handle request to delete a layer.

        Removes graphics items, the layer node from the tree, and emits
        ``layer_delete_feature_requested`` for each leaf feature so
        the database marker is also deleted.

        Args:
            node_id: ID of the layer node to delete.

        """
        if self._layer_model is None:
            return
        node = self._layer_model.find_node_by_id(node_id)
        if node is None:
            return

        # Don't delete the root
        if node is self._layer_model.root:
            logger.warning("Cannot delete the root node")
            return

        # Collect all leaf feature IDs before mutating the tree
        leaf_ids = self._collect_leaf_ids(node)

        # Remove the graphics item if it's a leaf feature
        if node.layer_type != MAP_LAYER_TYPE_GROUP:
            self.view.remove_marker(node_id)

        # Also remove children's graphics items for groups
        if node.layer_type == MAP_LAYER_TYPE_GROUP:
            self._remove_children_graphics(node)

        idx = self._layer_model.index_from_node(node)
        self._layer_model.remove_layer(idx)
        logger.info(f"Deleted layer: {node.name} ({node_id})")

        # Request DB deletion for every leaf feature
        for leaf_id in leaf_ids:
            self.layer_delete_feature_requested.emit(leaf_id)

    def _collect_leaf_ids(self, node: MapLayerNode) -> List[str]:
        """Recursively collect IDs of all leaf (non-group) nodes.

        Args:
            node: The root node to search.

        Returns:
            List of leaf node IDs.

        """
        ids: List[str] = []
        if node.layer_type != MAP_LAYER_TYPE_GROUP:
            ids.append(node.id)
        for child in node.children:
            ids.extend(self._collect_leaf_ids(child))
        return ids

    def _remove_children_graphics(self, group_node: MapLayerNode) -> None:
        """Recursively remove graphics items for all children of a group.

        Args:
            group_node: The parent group node.

        """
        for child in group_node.children:
            if child.layer_type == MAP_LAYER_TYPE_GROUP:
                self._remove_children_graphics(child)
            else:
                self.view.remove_marker(child.id)

    @Slot(str, str)
    def _on_layer_renamed(self, node_id: str, new_name: str) -> None:
        """Handle a layer rename from the panel.

        Updates the node name in the model, refreshes the view, and emits
        a signal so the command stack can persist the change.

        Args:
            node_id: ID of the renamed node.
            new_name: The new display name.

        """
        if self._layer_model is None:
            return
        node = self._layer_model.find_node_by_id(node_id)
        if node is None:
            return

        node.name = new_name
        idx = self._layer_model.index_from_node(node)
        self._layer_model.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])
        self.layer_rename_requested.emit(node_id, new_name)

    @Slot(str, float, float)
    def _on_layer_opacity_changed(
        self, node_id: str, opacity: float, old_opacity: float
    ) -> None:
        """Handle opacity change from the panel's slider.

        The model is already updated by the panel; this emits a signal
        so the command stack can persist the change.

        Args:
            node_id: ID of the node whose opacity changed.
            opacity: New opacity (0.0–1.0).
            old_opacity: Previous opacity (for undo).

        """
        self.layer_opacity_change_requested.emit(node_id, opacity, old_opacity)

    def get_layer_model(self) -> Optional[MapLayerModel]:
        """Return the current layer model (if any).

        Returns:
            Optional[MapLayerModel]: The active layer model.

        """
        return self._layer_model

    # ------------------------------------------------------------------
    # Marker CRUD (with layer integration)
    # ------------------------------------------------------------------

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
        lore_date: Optional[float] = None,
        feature_type: str = "point",
        geometry: Optional[list] = None,
        style: Optional[dict] = None,
    ) -> None:
        """Adds a marker or feature to the map.

        Also auto-registers a corresponding layer node (HIGH-6).

        Args:
            marker_id: Unique identifier for the marker.
            object_type: Type of object ('entity' or 'event').
            label: Marker label text.
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].
            icon: Optional icon filename.
            color: Optional color hex string.
            description: Optional description for tooltip.
            lore_date: Optional lore timestamp for temporal filtering.
            feature_type: 'point', 'path', or 'region'.
            geometry: Optional list of coordinate dicts for paths/regions.
            style: Optional visual override dict.

        """
        self.view.add_marker(
            marker_id,
            object_type,
            label,
            x,
            y,
            icon,
            color,
            description,
            lore_date,
            feature_type,
            geometry,
            style,
        )
        # Auto-register in layer hierarchy
        self._register_layer_node(marker_id, label, feature_type)

    def update_marker_position(self, marker_id: str, x: float, y: float) -> None:
        """Updates a marker's position.

        Args:
            marker_id: Unique identifier for the marker.
            x: Normalized X coordinate.
            y: Normalized Y coordinate.

        """
        self.view.update_marker_position(marker_id, x, y)

    def remove_marker(self, marker_id: str) -> None:
        """Removes a marker from the map and its layer node (MEDIUM-7).

        Args:
            marker_id: ID of the marker to remove.

        """
        self._unregister_layer_node(marker_id)
        self.view.remove_marker(marker_id)

    def clear_markers(self) -> None:
        """Removes all markers from the map and resets the layer model."""
        self.view.clear_markers()
        # Reset layer model — will be recreated when new markers load
        self._layer_model = None

    @Slot()
    def _configure_map_width(self) -> None:
        """Opens dialog to configure the map's total real-world width."""
        current_map_id = self.get_selected_map_id()
        if not current_map_id:
            logger.warning("No map selected, cannot configure scale")
            return

        map_name = self.map_selector.currentText()
        current_width = self.view.map_width_meters

        dialog = MapScaleDialog(current_width, self, map_name)

        # Determine behavior on result
        dialog.calibrate_requested.connect(self._handle_calibration_request)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_width = dialog.get_width()
            if new_width != current_width:
                self.view.set_map_width_meters(new_width)
                self.map_scale_changed.emit(new_width)
                logger.info(f"Updated map width to {new_width:.2f} m")

    @Slot()
    def _handle_calibration_request(self) -> None:
        """Starts the map calibration workflow from the dialog."""
        logger.info("Starting map calibration via measurement")

        # Disconnect any old connections to avoid duplicates
        try:
            self.view.calibration_completed.disconnect()
        except Exception:
            pass  # No slots connected

        self.view.calibration_completed.connect(
            self._on_calibration_measurement_finished
        )

        self.view.start_calibration()

        # Show hint
        self.overlay_banner.setText(
            "Click two points on the map to measure a known distance."
        )
        self.overlay_banner.show()

    @Slot(float)
    def _on_calibration_measurement_finished(self, px_distance: float) -> None:
        """Handle completion of the calibration measurement step."""
        # 1. Hide overlay
        self.overlay_banner.hide()

        # 2. Ask for real world distance
        if px_distance < 1.0:
            logger.warning("Measured distance too small, ignoring.")
            return

        dialog = CalibrationDistanceDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            segment_meters = dialog.get_distance_meters()

            if segment_meters <= 0:
                return

            # Calculate new total width
            # Total Width / Image Width = Segment Real / Segment px
            # Total Width = (Image Width * Segment Real) / Segment px

            pixmap_item = getattr(self.view, "pixmap_item", None)
            if not pixmap_item:
                return

            image_width_px = pixmap_item.boundingRect().width()

            new_total_width = (image_width_px * segment_meters) / px_distance

            self.view.set_map_width_meters(new_total_width)
            self.map_scale_changed.emit(new_total_width)

            # Show confirmation details
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                "Calibration Complete",
                f"Map scale updated.\n\n"
                f"Segment: {segment_meters:.1f} m ({px_distance:.1f} px)\n"
                f"New Total Width: {new_total_width:.2f} m",
            )

        # Cleanup
        try:
            self.view.calibration_completed.disconnect(
                self._on_calibration_measurement_finished
            )
        except Exception:
            pass

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
        self._update_mode_indicator()

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

    def _apply_mode_indicator_style(self, mode: str) -> None:
        """Applies themed style to the mode indicator label.

        Args:
            mode: One of 'normal', 'clock', 'draft', 'drawing', 'vertex'.

        """
        theme = ThemeManager().get_theme()
        color_map = {
            "clock": theme.get("error", "#e74c3c"),
            "draft": theme.get("primary", "#f39c12"),
            "drawing": theme.get("accent_secondary", "#3498db"),
            "vertex": theme.get("primary", "#e67e22"),
            "normal": "#2ecc71",
        }
        bg = color_map.get(mode, "#2ecc71")
        self.mode_indicator.setStyleSheet(
            f"""
            QLabel {{
                background: {bg};
                color: white;
                padding: 5px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }}
            """
        )

    def _update_mode_indicator(self) -> None:
        """Updates the toolbar status, map overlay, and Finish Sketch button."""
        if self._pinned_marker_id:
            # Clock Mode (Priority)
            marker_id = self._pinned_marker_id
            self.mode_indicator.setText(f'🔴 CLOCK MODE: Editing "{marker_id}"')
            self._apply_mode_indicator_style("clock")

            # Overlay Banner
            banner_text = (
                "⏱ <b>CLOCK MODE ACTIVE</b><br/>"
                "Scrub timeline to adjust keyframe timestamp<br/>"
                "<small>[Esc to Cancel] [Enter to Commit]</small>"
            )
            self.overlay_banner.setText(banner_text)
            self.overlay_banner.show()
            self._update_overlay_position()
            self.btn_finish_sketch.hide()

            # Cursor Change
            self.view.setCursor(Qt.CursorShape.WaitCursor)

        elif self._transient_marker_ids:
            # Draft Mode
            self.mode_indicator.setText("🟠 DRAFT MODE: Unsaved keys")
            self._apply_mode_indicator_style("draft")

            # Overlay Banner
            banner_text = (
                "✍️ <b>DRAFT MODE ACTIVE</b><br/>"
                "You have unsaved marker positions.<br/>"
                "<small>[Add Keyframe to Save] [Esc to Discard]</small>"
            )
            self.overlay_banner.setText(banner_text)
            self.overlay_banner.show()
            self._update_overlay_position()
            self.btn_finish_sketch.hide()

            # Normal cursor
            self.view.setCursor(Qt.CursorShape.ArrowCursor)

        elif self.view.is_drawing:
            # Drawing Mode
            mode_name = self.view.drawing_mode or "shape"
            self.mode_indicator.setText(f"🔵 DRAWING: {mode_name.title()}")
            self._apply_mode_indicator_style("drawing")

            # Overlay Banner
            banner_text = (
                f"✏️ <b>DRAWING {mode_name.upper()}</b><br/>"
                "Click to add vertices<br/>"
                "<small>[Double-click to Finish] [Esc to Cancel]</small>"
            )
            self.overlay_banner.setText(banner_text)
            self.overlay_banner.show()
            self._update_overlay_position()

            # Show Finish Sketch button
            self.btn_finish_sketch.show()
            self._update_finish_sketch_position()

        elif self.view.is_editing_vertices:
            # Vertex Editing Mode
            self.mode_indicator.setText("🟣 EDITING VERTICES")
            self._apply_mode_indicator_style("vertex")

            # Overlay Banner
            banner_text = (
                "🔧 <b>VERTEX EDITING</b><br/>"
                "Drag vertices to reshape · Drag midpoints to add<br/>"
                "<small>[Right-click vertex to Delete] [Esc to Finish]</small>"
            )
            self.overlay_banner.setText(banner_text)
            self.overlay_banner.show()
            self._update_overlay_position()

            # Show Finish Sketch button
            self.btn_finish_sketch.show()
            self._update_finish_sketch_position()

        else:
            # Normal Mode
            self.mode_indicator.setText("Normal Mode")
            self._apply_mode_indicator_style("normal")

            # Overlay Banner
            self.overlay_banner.hide()
            self.btn_finish_sketch.hide()

            # Normal cursor
            self.view.setCursor(Qt.CursorShape.ArrowCursor)

    def _clear_clock_mode_visuals(self) -> None:
        """Resets visual pinned state and internal tracking."""
        if self._pinned_marker_id and self._pinned_original_t is not None:
            self.view.set_keyframe_pinned(
                self._pinned_marker_id, self._pinned_original_t, False
            )
        self._pinned_marker_id = None
        self._pinned_original_t = None
        self._update_mode_indicator()

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
        """Handle keyframe delete request from gizmo.

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
        elif event.key() == Qt.Key_Escape:
            # Deselect all items in the scene
            if self.view.scene.selectedItems():
                logger.debug("Esc pressed: Clearing selection")
                self.view.scene.clearSelection()
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

    def _update_finish_sketch_position(self) -> None:
        """Positions the Finish Sketch button at the bottom-center of the view."""
        if hasattr(self, "btn_finish_sketch") and self.btn_finish_sketch.isVisible():
            view_width = self.view.width()
            view_height = self.view.height()
            btn_width = self.btn_finish_sketch.sizeHint().width()
            btn_height = self.btn_finish_sketch.sizeHint().height()
            x = (view_width - btn_width) // 2
            y = view_height - btn_height - 20
            self.btn_finish_sketch.move(x, y)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Handle resize to keep overlay and Finish Sketch button centered."""
        super().resizeEvent(event)
        self._update_overlay_position()
        self._update_finish_sketch_position()
        logger.debug(
            f"MapWidget Resized: {event.size().width()}x{event.size().height()} (Old: {event.oldSize().width()}x{event.oldSize().height()})"
        )


class OnboardingDialog(QDialog):
    """Onboarding dialog shown when the first keyframe is created."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the onboarding dialog.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("✨ Keyframe Created!")
        self.setFixedWidth(400)
        
        # Apply theme-aware styling
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

        layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(layout)
        layout.setSpacing(15)

        title = QLabel("✨ Keyframe Created!")
        title.setStyleSheet(f"font-size: 18px; {StyleHelper.get_section_header_style()}")
        layout.addWidget(title)
        
        # Get theme for specific text colors not covered by base style
        from src.core.theme_manager import ThemeManager
        theme = ThemeManager().get_theme()

        body = QLabel(
            "Hover over yellow dots to reveal editing tools:<br/>"
            "• <b>Drag</b> to adjust position<br/>"
            "• Click 🕐 to adjust <b>timing</b> (Clock Mode)<br/>"
            "• Click ✕ to <b>delete</b>"
        )
        body.setWordWrap(True)
        # Ensure body text matches theme standard
        body.setStyleSheet(f"color: {theme['text_main']}; font-size: 13px;")
        layout.addWidget(body)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton

        self.btn_tutorial = StandardButton("Show Tutorial Video")
        # In a real app, this would open a URL
        self.btn_tutorial.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_tutorial)

        self.btn_got_it = PrimaryButton("Got it!")
        self.btn_got_it.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_got_it)

        layout.addLayout(btn_layout)
