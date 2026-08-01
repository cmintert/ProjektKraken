"""Map Widget Module.

Main entry point for map visualization. Provides MapWidget wrapper
that combines MapGraphicsView with map management controls.

The map components have been refactored into separate modules for better
maintainability:
- map/marker_item.py - MarkerItem rendering
- map/map_graphics_view.py - Main view with zoom/pan and interaction
- map/icon_picker_dialog.py - Icon selection dialog

Behaviour is composed from focused mixins:
- MapLayerMixin       – Layer tree CRUD & selection sync
- MapTrajectoryMixin  – Trajectory interpolation & clock-mode editing
- MapDrawingMixin     – Path/region drawing toggle & completion
- MapCalibrationMixin – Map-scale configuration & calibration
- MapDialogMixin      – User-facing dialogs (object picker, CRUD confirms)
"""

import logging
import os
from typing import List, Optional

from PySide6.QtCore import QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QKeyEvent, QPaintEvent, QResizeEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.core.calendar import CalendarConverter
from src.core.map import Map
from src.core.paths import get_resource_path
from src.core.theme_manager import ThemeManager
from src.gui.mixins.map_calibration_mixin import MapCalibrationMixin
from src.gui.mixins.map_dialog_mixin import MapDialogMixin
from src.gui.mixins.map_drawing_mixin import MapDrawingMixin
from src.gui.mixins.map_layer_mixin import MapLayerMixin
from src.gui.mixins.map_nesting_mixin import MapNestingMixin
from src.gui.mixins.map_trajectory_mixin import MapTrajectoryMixin
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.empty_state_widget import EmptyStateWidget
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.map.map_layer_model import MapLayerModel
from src.gui.widgets.map.map_layer_panel import MapLayerPanel
from src.gui.widgets.map.marker_item import MarkerItem
from src.gui.widgets.map.raster_legend_widget import RasterLegendWidget

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

        # Use theme-aware dim text colour
        dim_color = StyleHelper.get_dim_text_color()
        painter.setPen(QColor(dim_color))

        rect = self.rect().adjusted(0, 0, -5, 0)  # Padding right
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            self._text,
        )


class MapWidget(
    MapLayerMixin,
    MapTrajectoryMixin,
    MapDrawingMixin,
    MapCalibrationMixin,
    MapNestingMixin,
    MapDialogMixin,
    QWidget,
):
    """Container widget for the map view.

    Behaviour is composed from focused mixins (see module docstring).
    This class owns the signals, the ``__init__`` setup, and the
    remaining thin orchestration methods that glue the mixins together.

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
    marker_visual_style_changed = Signal(str, dict)  # marker_id, style overrides
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
    # Map nesting (master / detail) signals
    set_master_map_requested = Signal(str)  # map_id
    register_detail_map_requested = Signal(
        str, str, dict
    )  # detail_id, parent_id, registration
    edit_footprint_requested = Signal(str)  # detail_map_id (Phase 3)
    # Layer operations (routed through the command stack)
    layer_tree_changed = Signal()  # auto-persist hook
    layer_opacity_change_requested = Signal(
        str, float, float
    )  # node_id, opacity, old_opacity
    layer_rename_requested = Signal(str, str)  # node_id, new_name
    layer_delete_feature_requested = Signal(
        str, str
    )  # object_id, layer_type of deleted leaf
    layer_properties_changed = Signal(str, dict)
    create_raster_layer_requested = Signal(
        str, int, int, str, int, str, object, object, str
    )  # name,w,h,mode,def,import_path,display_min,display_max,unit
    raster_edit_requested = Signal(str)  # node_id — start raster editing
    raster_edit_stopped = Signal()  # stop raster editing
    raster_stroke_completed = Signal(str, object)  # node_id, tile patches
    raster_value_probed = Signal(str, object, float, float)  # node_id, sample, x, y
    raster_palette_edit_requested = Signal(str)  # node_id

    # Emitted when inline entity/event creation is requested from the map.
    create_entity_requested = Signal(str, str)  # new_id, name
    create_event_requested = Signal(str, str)  # new_id, name

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initializes the MapWidget.

        Args:
            parent: Parent widget.

        """
        super().__init__(parent)

        # Expanding policy prevents dock collapse during resize.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Create view
        self.view = MapGraphicsView(self)

        self._pinned_marker_id: Optional[str] = None
        self._pinned_original_t: Optional[float] = None

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Toolbar
        self.toolbar = QToolBar(self)
        self.toolbar.setStyleSheet(StyleHelper.get_toolbar_spacing_style())
        layout.addWidget(self.toolbar)

        self._breadcrumb_parent_id: Optional[str] = None

        # Map Selector
        self.map_selector = QComboBox()
        self.map_selector.setMinimumWidth(200)
        self.map_selector.setToolTip("Switch between maps in this world")
        self.map_selector.currentIndexChanged.connect(self._on_map_selected)
        self.toolbar.addWidget(self.map_selector)

        # Buttons (themed via StyleHelper)
        tool_style = StyleHelper.get_tool_button_style()
        drawing_style = StyleHelper.get_raster_tool_button_style()
        toggle_style = StyleHelper.get_toggle_button_style()

        # Group 1: Map management
        self.btn_new_map = QPushButton("New Map")
        self.btn_new_map.setToolTip("Create a new map in this world")
        self.btn_new_map.setStyleSheet(tool_style)
        self.btn_new_map.clicked.connect(self._on_create_map_clicked)
        self.toolbar.addWidget(self.btn_new_map)

        self.btn_map_overflow = QPushButton("⋯")
        self.btn_map_overflow.setFixedWidth(28)
        self.btn_map_overflow.setToolTip("Map options (delete, etc.)")
        self.btn_map_overflow.setStyleSheet(tool_style)
        self.btn_map_overflow.clicked.connect(self._show_map_overflow_menu)
        self.toolbar.addWidget(self.btn_map_overflow)

        self.toolbar.addSeparator()

        # Group 2: Viewport
        self.btn_fit_view = QPushButton("Fit to View")
        self.btn_fit_view.setToolTip("Zoom and pan to fit all content in view")
        self.btn_fit_view.setStyleSheet(tool_style)
        self.btn_fit_view.clicked.connect(self.view.fit_to_view)
        self.toolbar.addWidget(self.btn_fit_view)

        self.btn_settings = QPushButton("Settings")
        self.btn_settings.setToolTip("Configure Map Properties (Scale)")
        self.btn_settings.setStyleSheet(tool_style)
        self.btn_settings.clicked.connect(self._configure_map_width)
        self.toolbar.addWidget(self.btn_settings)

        self.toolbar.addSeparator()

        # Group 3: Drawing tools (mutually exclusive, fill when active)
        self.btn_add_marker = QPushButton("Add Marker")
        self.btn_add_marker.setToolTip(
            "Add a marker to the map (click the map to choose its position)"
        )
        self.btn_add_marker.setCheckable(True)
        self.btn_add_marker.setStyleSheet(drawing_style)
        self.btn_add_marker.clicked.connect(self._on_add_marker_clicked)
        self.toolbar.addWidget(self.btn_add_marker)

        self.btn_draw_path = QPushButton("Draw Path")
        self.btn_draw_path.setToolTip(
            "Draw a polyline path on the map (click vertices, double-click to finish)"
        )
        self.btn_draw_path.setCheckable(True)
        self.btn_draw_path.setStyleSheet(drawing_style)
        self.btn_draw_path.clicked.connect(self._on_draw_path_clicked)
        self.toolbar.addWidget(self.btn_draw_path)

        self.btn_draw_region = QPushButton("Draw Region")
        self.btn_draw_region.setToolTip(
            "Draw a polygon region on the map (click vertices, double-click to finish)"
        )
        self.btn_draw_region.setCheckable(True)
        self.btn_draw_region.setStyleSheet(drawing_style)
        self.btn_draw_region.clicked.connect(self._on_draw_region_clicked)
        self.toolbar.addWidget(self.btn_draw_region)

        self.toolbar.addSeparator()

        # Group 4: Persistent view toggles (border highlight when on)
        self.btn_snap = QPushButton("Snap")
        self.btn_snap.setToolTip("Toggle snapping to nearby feature vertices and edges")
        self.btn_snap.setCheckable(True)
        self.btn_snap.setChecked(True)  # enabled by default
        self.btn_snap.setStyleSheet(toggle_style)
        self.btn_snap.clicked.connect(self._on_snap_toggled)
        self.toolbar.addWidget(self.btn_snap)

        self.btn_legend_toggle = QPushButton("Legend")
        self.btn_legend_toggle.setToolTip("Show / hide the raster layer legend overlay")
        self.btn_legend_toggle.setCheckable(True)
        self.btn_legend_toggle.setChecked(False)
        self.btn_legend_toggle.setStyleSheet(toggle_style)
        self.btn_legend_toggle.toggled.connect(self._on_legend_toggle)
        self.toolbar.addWidget(self.btn_legend_toggle)

        self.toolbar.addSeparator()

        # Add Keyframe — hidden by default; shown only in draft mode
        self.btn_add_keyframe = QPushButton("Add Keyframe")
        self.btn_add_keyframe.setToolTip("Save current marker position at current time")
        self.btn_add_keyframe.setStyleSheet(tool_style)
        self.btn_add_keyframe.setVisible(False)
        self.btn_add_keyframe.clicked.connect(self._on_add_keyframe)
        self.toolbar.addWidget(self.btn_add_keyframe)

        # Mode Pill (right side) — clickable to exit the current mode
        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.toolbar.addWidget(spacer)

        self.mode_indicator = QPushButton("● Normal")
        self.mode_indicator.setToolTip("Current editing mode — click to exit")
        self.mode_indicator.clicked.connect(self._on_mode_indicator_clicked)
        self._apply_mode_indicator_style("normal")
        self.toolbar.addWidget(self.mode_indicator)

        # Add View (after toolbar) — wrapped in a splitter with the layer panel
        # Breadcrumb row — shows the ancestor chain for master/detail maps.
        # Hidden for plain maps.  Lives on its own row to avoid being
        # clipped by the crowded toolbar above.
        breadcrumb_row = QWidget(self)
        breadcrumb_layout = QHBoxLayout(breadcrumb_row)
        breadcrumb_layout.setContentsMargins(8, 2, 8, 2)
        breadcrumb_layout.setSpacing(6)

        self.btn_parent = QPushButton("↑")
        self.btn_parent.setFixedWidth(24)
        self.btn_parent.setToolTip("Navigate to parent map")
        self.btn_parent.setStyleSheet(StyleHelper.get_tool_button_style())
        self.btn_parent.clicked.connect(self._on_navigate_to_parent)
        self.btn_parent.hide()
        breadcrumb_layout.addWidget(self.btn_parent)

        self.breadcrumb_label = QLabel()
        self.breadcrumb_label.setTextFormat(Qt.TextFormat.RichText)
        self.breadcrumb_label.setOpenExternalLinks(False)
        self.breadcrumb_label.linkActivated.connect(self.select_map)
        self.breadcrumb_label.setToolTip("Nesting path — click a segment to navigate")
        self.breadcrumb_label.hide()
        breadcrumb_layout.addWidget(self.breadcrumb_label)
        breadcrumb_layout.addStretch(1)

        breadcrumb_row.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self._breadcrumb_row = breadcrumb_row
        self._breadcrumb_row.hide()
        layout.addWidget(self._breadcrumb_row)

        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)

        self._splitter.addWidget(self.view)

        # Layer Panel (right side)
        self.layer_panel = MapLayerPanel(self)
        self._splitter.addWidget(self.layer_panel)

        # Default proportions: 80% map, 20% layer panel
        self._splitter.setStretchFactor(0, 4)
        self._splitter.setStretchFactor(1, 1)

        layout.addWidget(self._splitter)

        # Empty State
        self.empty_state = EmptyStateWidget(
            title="No Map Available",
            description="Create or select a map to start exploring.",
            parent=self,
        )
        self.empty_state.add_action(
            "Create Map", self._on_create_map_clicked, primary=True
        )
        layout.addWidget(self.empty_state)
        # Hidden by default

        # Layer model (created per-map; None until markers load)
        self._layer_model: Optional[MapLayerModel] = None

        # Overlay Banner (Child of view, positioned at top)
        self.overlay_banner = QLabel(self.view)
        self.overlay_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay_banner.setStyleSheet(StyleHelper.get_overlay_banner_style())
        self.overlay_banner.hide()

        # ── Raster Legend Overlay (bottom-left, floating over the map) ──
        # Parented to the view (not viewport) so it survives OpenGL viewport
        # recreation during map switches (`setViewport()`), but positioned
        # mathematically relative to the viewport's geometry to avoid scrollbars.
        self.legend_overlay = RasterLegendWidget(self.view)
        self.legend_overlay.setMaximumWidth(360)  # wide enough for class labels
        self.legend_overlay.setStyleSheet(StyleHelper.get_legend_overlay_style())
        self.legend_overlay.hide()

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
        self.view.marker_placement_ended.connect(self._on_marker_placement_ended)
        self.view.delete_marker_requested.connect(self._on_delete_marker_requested)
        self.view.change_marker_icon_requested.connect(
            self.change_marker_icon_requested.emit
        )
        self.view.change_marker_color_requested.connect(
            self.change_marker_color_requested.emit
        )
        self.view.marker_visual_style_changed.connect(
            self.marker_visual_style_changed.emit
        )
        self.view.marker_drop_requested.connect(self.marker_drop_requested.emit)
        self.view.mouse_coordinates_changed.connect(self._on_mouse_coordinates_changed)
        self.view.viewport_resized.connect(lambda _: self._position_legend_overlay())

        # Focus proxy to ensure view gets keyboard events when widget is clicked
        self.setFocusProxy(self.view)
        self.view.drawing_finished.connect(self._on_drawing_finished)
        self.view.drawing_cancelled.connect(self._on_drawing_cancelled)
        self.view.feature_style_changed.connect(self.feature_style_changed.emit)
        self.view.feature_geometry_changed.connect(self.feature_geometry_changed.emit)
        self.view.feature_geometry_changed.connect(self._on_geometry_changed)
        self.view.graphics_scene.selectionChanged.connect(self._on_selection_changed)
        # Bi-directional selection: marker click → highlight in layer panel
        self.view.marker_clicked.connect(self._on_marker_clicked_select_layer)
        self.layer_panel.layer_selected.connect(self._on_layer_panel_selected)
        # Layer panel actions
        self.layer_panel.create_group_requested.connect(self._on_create_group)
        self.layer_panel.create_layer_requested.connect(self._on_create_layer)
        self.layer_panel.delete_layer_requested.connect(self._on_delete_layer)
        self.layer_panel.layer_renamed.connect(self._on_layer_renamed)
        self.layer_panel.layer_opacity_changed.connect(self._on_layer_opacity_changed)
        self.layer_panel.layer_properties_changed.connect(
            self.layer_properties_changed.emit
        )
        self.layer_panel.create_raster_layer_requested.connect(
            self._on_create_raster_layer
        )
        self.layer_panel.raster_edit_requested.connect(self._on_raster_edit_requested)
        self.layer_panel.raster_edit_stopped.connect(self._on_raster_edit_stopped)
        self.layer_panel.raster_palette_edit_requested.connect(
            self.raster_palette_edit_requested.emit
        )
        self.layer_panel.raster_settings_changed.connect(
            self._on_raster_settings_changed
        )
        self.layer_panel.raster_layer_selected.connect(self._on_raster_layer_selected)
        self.layer_panel.raster_snapshot_selected.connect(
            self._on_raster_snapshot_selected
        )

        # Forward raster signals from the graphics view
        self.view.raster_stroke_completed.connect(self.raster_stroke_completed.emit)
        self.view.raster_value_probed.connect(self.raster_value_probed.emit)
        self.view.raster_edit_externally_stopped.connect(
            self.layer_panel.reset_edit_toggle
        )
        self.view.raster_edit_externally_stopped.connect(
            self._on_raster_edit_stopped
        )
        self.view.raster_brush_resize_requested.connect(
            self._on_raster_brush_resize_from_view
        )
        self.view.raster_tool_shortcut_requested.connect(
            self.layer_panel.set_raster_tool_mode
        )

        self._maps_data: list[Map] = []  # List of maps for selector
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

    def minimumSizeHint(self) -> QSize:
        """Allow the widget to shrink inside its dock.

        Returns:
            QSize: Minimum usable size for the map widget.
        """
        return QSize(200, 150)

    def sizeHint(self) -> QSize:
        """Preferred size for the map widget.

        Returns:
            QSize: Comfortable working size for map interaction.
        """
        return QSize(600, 400)

    def _position_legend_overlay(self) -> None:
        """Position the legend overlay fully within the map view viewport.

        Always anchors to the top-left corner so long class lists expand
        downward and are never clipped.  Width is capped at 360 px and height
        is capped to the available viewport height so the overlay never
        extends outside the map area.
        """
        _MARGIN = 12
        legend = self.legend_overlay
        vp_rect = self.view.viewport().geometry()

        available_w = vp_rect.width() - 2 * _MARGIN
        available_h = vp_rect.height() - 2 * _MARGIN

        if available_w <= 0 or available_h <= 0:
            return

        # Force layout recalculation so sizeHint() reflects current content.
        # Without this, sizeHint() is stale on the first show after set_layer()
        # adds new widgets, causing the overlay to render too small until the
        # next event-loop pass.
        outer_layout = legend.layout()
        if outer_layout is not None:
            outer_layout.activate()
        content_layout = legend._content.layout()
        if content_layout is not None:
            content_layout.activate()

        max_w = min(360, available_w)
        legend.setMaximumWidth(max_w)
        legend.setMaximumHeight(available_h)

        header_h = legend._header_label.sizeHint().height() + 10
        title_h = (
            legend._title_label.sizeHint().height()
            if legend._title_label.isVisible()
            else 0
        )
        w = max_w

        # Compute ideal height from content widget so every row is shown.
        # Include the title label (in outer layout, not inside _content).
        content_h = legend._content.sizeHint().height()
        ideal_h = content_h + header_h + title_h + 16  # padding
        h = min(ideal_h, available_h)

        # Anchor to top-left of the viewport.
        x = vp_rect.x() + _MARGIN
        y = vp_rect.y() + _MARGIN
        legend.move(x, y)
        legend.raise_()  # Ensure it floats above the QGraphicsView viewport
        legend.resize(w, h)

    @Slot(object, object)
    def _on_raster_layer_selected(self, node_id: object, layer_meta: object) -> None:
        """Show/hide and populate the floating legend overlay.

        Connected to :attr:`MapLayerPanel.raster_layer_selected`.  When
        *node_id* is ``None`` the overlay is hidden; otherwise it is updated
        with *layer_meta* and shown.

        Args:
            node_id: The selected raster layer's ID, or ``None``.
            layer_meta: The raster layer metadata dict, or ``None``.
        """
        overlay = self.legend_overlay
        # Notify the edit tool so SAMPLE can probe without requiring edit mode.
        if hasattr(self.view, "_raster_edit_tool"):
            self.view._raster_edit_tool.set_preview_node_id(
                str(node_id) if node_id else None
            )
        if not node_id or not isinstance(layer_meta, dict) or not layer_meta:
            overlay.hide()
            self.btn_legend_toggle.blockSignals(True)
            self.btn_legend_toggle.setChecked(False)
            self.btn_legend_toggle.blockSignals(False)
        else:
            name_map = {}
            for e in self._cached_entities:
                if getattr(e, "id", None) and getattr(e, "name", None):
                    name_map[e.id] = e.name
            for ev in self._cached_events:
                if getattr(ev, "id", None) and getattr(ev, "name", None):
                    name_map[ev.id] = ev.name

            overlay.set_layer(layer_meta, name_map=name_map)
            # Do NOT auto-show or force the toggle — the user controls
            # legend visibility via btn_legend_toggle.  Just reposition if
            # the overlay is already visible so new content fits correctly.
            if overlay.isVisible():
                self._position_legend_overlay()
                QTimer.singleShot(0, self._position_legend_overlay)

    @Slot(int)
    def _on_raster_brush_resize_from_view(self, new_size: int) -> None:
        """Sync panel brush-size spinbox when Ctrl+scroll resized the brush."""
        self.layer_panel.set_raster_brush_size(new_size)

    @Slot(bool)
    def _on_legend_toggle(self, checked: bool) -> None:
        """Show or hide the legend overlay from the toolbar button.

        Args:
            checked: ``True`` to show; ``False`` to hide.
        """
        if checked:
            # Position BEFORE show() so the first paint is at the correct
            # size.  _position_legend_overlay activates layouts and reads
            # sizeHints from the toggle-button checked state (not isVisible),
            # so it works correctly while the overlay is still hidden.
            self._position_legend_overlay()
            self.legend_overlay.show()
        else:
            self.legend_overlay.hide()

    @Slot(str, float)
    def _on_raster_snapshot_selected(self, _node_id: str, lore_date: float) -> None:
        """Forward snapshot selection to timeline playhead jump."""
        self.jump_to_time_requested.emit(lore_date)

    def _on_selection_changed(self) -> None:
        """Updates UI state based on selection."""
        # Clear transient states on selection change to ensure markers snap back
        if self._transient_marker_ids:
            logger.debug("Selection changed: clearing transient marker states")
            self._transient_marker_ids.clear()
            self._update_trajectory_positions(force_all=True)
            self._update_mode_indicator()

        selected_items = self.view.graphics_scene.selectedItems()
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
            elif not should_enable:
                self.btn_add_keyframe.setToolTip(
                    "Select a marker in the map to enable keyframe recording"
                )
            else:
                self.btn_add_keyframe.setToolTip(
                    "Save current marker position at current time"
                )

    # -- Trajectory / drawing / dialog methods provided by mixins ------

    @Slot()
    def _show_map_overflow_menu(self) -> None:
        """Shows the map overflow menu containing map-level actions.

        Includes nesting actions (Set as Master, Register as Detail,
        Edit Footprint) gated by the active map's role and the world's
        master state, plus the destructive Delete action.

        """
        menu = QMenu(self)
        active_role = self._active_map_role()
        has_master = self._world_has_master_map()

        master_action = menu.addAction("Set as Master Map")
        master_action.setCheckable(True)
        master_action.setChecked(active_role == "master")
        master_action.triggered.connect(self._on_set_master_map_clicked)

        register_action = menu.addAction("Register as Detail Map…")
        register_action.setEnabled(has_master and active_role != "master")
        if not has_master:
            register_action.setToolTip(
                "Designate a master map first before registering a detail map."
            )
        register_action.triggered.connect(
            self._on_register_detail_map_clicked
        )

        show_footprints_action = menu.addAction("Show Footprints")
        show_footprints_action.setCheckable(True)
        show_footprints_action.setChecked(self.view.footprints_visible)

        def _on_show_footprints_toggled(checked: bool) -> None:
            self.view.set_footprints_visible(checked)
            self._update_mode_indicator()

        show_footprints_action.toggled.connect(_on_show_footprints_toggled)

        edit_footprint_action = menu.addAction("Edit Footprint…")
        edit_footprint_action.setEnabled(
            self.view.footprints_visible
            and (bool(self.view._footprint_items) or active_role == "detail")
        )
        edit_footprint_action.triggered.connect(
            self._on_edit_footprint_clicked
        )

        menu.addSeparator()
        delete_action = menu.addAction("Delete Map...")
        delete_action.triggered.connect(self._on_delete_map_clicked)
        pos = self.btn_map_overflow.mapToGlobal(self.btn_map_overflow.rect().bottomLeft())
        menu.exec(pos)

    @Slot()
    def _on_mode_indicator_clicked(self) -> None:
        """Exits the current editing mode when the mode pill is clicked."""
        if self._pinned_marker_id:
            self._cancel_clock_mode()  # already calls _update_mode_indicator internally
            return
        elif self.view.is_editing_footprint:
            self.view.cancel_footprint_edit()
        elif self.view.is_drawing:
            self.view.cancel_drawing()
        elif self.view.is_placing_marker:
            self.view.cancel_marker_placement()
        elif self.view.is_editing_vertices:
            self.view.finish_editing()
        elif self._transient_marker_ids:
            self._transient_marker_ids.clear()
            self._update_trajectory_positions(force_all=True)
        self._update_mode_indicator()

    @Slot()
    def _on_add_marker_clicked(self) -> None:
        """Toggle one-shot marker placement mode."""
        if self.view.is_placing_marker:
            self.view.cancel_marker_placement()
            return
        if self.view.is_drawing:
            self.view.cancel_drawing()
        self.btn_draw_path.setChecked(False)
        self.btn_draw_region.setChecked(False)
        self.view.start_marker_placement()
        self._update_mode_indicator()

    @Slot()
    def _on_marker_placement_ended(self) -> None:
        """Reset toolbar state after marker placement or cancellation."""
        self.btn_add_marker.setChecked(False)
        self._update_mode_indicator()

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

    # -- Trajectory position / time methods provided by MapTrajectoryMixin --

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

        if not maps:
            self._splitter.hide()
            self.toolbar.hide()
            self.empty_state.show()
        else:
            self.empty_state.hide()
            self.toolbar.show()
            self._splitter.show()

    def select_map(self, map_id: str) -> None:
        """Selects the map with the given ID in the dropdown."""
        index = self.map_selector.findData(map_id)
        if index >= 0:
            logger.debug(f"Selecting map index {index} for id {map_id}")
            self.map_selector.setCurrentIndex(index)
        else:
            logger.warning(f"Map ID {map_id} not found in selector")

    def set_breadcrumb(self, chain: list) -> None:
        """Update the breadcrumb label from the nesting ancestor chain.

        Args:
            chain: Ordered list of ``(map_id, map_name)`` tuples from root
                to the current map.  An empty list hides the breadcrumb.

        """
        if len(chain) <= 1:
            self.breadcrumb_label.hide()
            self.btn_parent.hide()
            self._breadcrumb_row.hide()
            self._breadcrumb_parent_id = None
            return

        theme = ThemeManager().get_theme()
        link_color = theme.get("accent_secondary", "#4DA6FF")
        dim_color = theme.get("text_dim", "#9E9E9E")

        parts = []
        for i, (mid, mname) in enumerate(chain):
            is_last = i == len(chain) - 1
            if is_last:
                parts.append(
                    f'<span style="color:{dim_color};">{mname}</span>'
                )
            else:
                parts.append(
                    f'<a href="{mid}" style="color:{link_color};'
                    f' text-decoration:none;">{mname}</a>'
                )

        separator = f' <span style="color:{dim_color};">›</span> '
        self.breadcrumb_label.setText(separator.join(parts))
        self.breadcrumb_label.show()

        # Back-to-parent: parent is the second-to-last in the chain.
        parent_id = chain[-2][0] if len(chain) >= 2 else None
        self._breadcrumb_parent_id = parent_id
        self.btn_parent.setVisible(parent_id is not None)
        self._breadcrumb_row.show()

    @Slot()
    def _on_navigate_to_parent(self) -> None:
        """Navigate to the parent map when the back button is clicked."""
        if self._breadcrumb_parent_id:
            self.select_map(self._breadcrumb_parent_id)

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
        ok = self.view.load_map(image_path)
        if ok:
            # A fresh pixmap item was just created — re-apply the
            # basemap layer node's visibility/opacity to it.
            self._sync_basemap_to_view()
        return ok

    # -- Layer management provided by MapLayerMixin --------------------

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
        visual_attributes: Optional[dict] = None,
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
            visual_attributes: Optional dict with ``_v_*`` visual override keys.

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
            visual_attributes,
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

    def exit_editing_modes(self) -> None:
        """Exit active map and layer editing modes without committing edits."""
        self.view.exit_all_editing(commit_feature_edits=False)
        self._update_mode_indicator()

    def clear_markers(self) -> None:
        """Removes all markers from the map and resets the layer model."""
        self.view.clear_markers()
        # Reset layer model — will be recreated when new markers load
        self._layer_model = None

    # -- Calibration provided by MapCalibrationMixin -------------------

    # -- Keyframe / clock-mode methods provided by MapTrajectoryMixin --

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
            "normal": theme.get("success", "#2ecc71"),
        }
        bg = color_map.get(mode, theme.get("text_dim", "#aaaaaa"))
        active = mode != "normal"
        self.mode_indicator.setStyleSheet(StyleHelper.get_mode_pill_style(bg, active=active))

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
            # Draft Mode — Add Keyframe shown below via consolidated visibility call
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

        elif self.view.is_placing_marker:
            self.mode_indicator.setText("🔵 PLACING MARKER")
            self._apply_mode_indicator_style("drawing")

            self.overlay_banner.setText(
                "📍 <b>PLACE MARKER</b><br/>"
                "Click the map to choose its position<br/>"
                "<small>[Esc to Cancel]</small>"
            )
            self.overlay_banner.show()
            self._update_overlay_position()
            self.btn_finish_sketch.hide()
            self.view.setCursor(Qt.CursorShape.CrossCursor)

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

        elif self.view.is_editing_footprint:
            # Footprint Edit Mode
            self.mode_indicator.setText("🟤 EDITING FOOTPRINT")
            self._apply_mode_indicator_style("drawing")

            # Overlay Banner
            banner_text = (
                "📌 <b>FOOTPRINT EDIT</b><br/>"
                "Drag body to move · Drag corner to scale · "
                "Drag ○ to rotate<br/>"
                "<small>[←→↑↓ nudge] [[ ]] rotate] "
                "[Enter to Confirm] [Esc to Cancel]</small>"
            )
            self.overlay_banner.setText(banner_text)
            self.overlay_banner.show()
            self._update_overlay_position()
            self.btn_finish_sketch.hide()

            self.view.setCursor(Qt.CursorShape.SizeAllCursor)

        else:
            # Normal Mode
            self.mode_indicator.setText("● Normal")
            self._apply_mode_indicator_style("normal")

            # Overlay Banner
            self.overlay_banner.hide()
            self.btn_finish_sketch.hide()

            # Normal cursor
            self.view.setCursor(Qt.CursorShape.ArrowCursor)

        # Add Keyframe is only relevant in draft mode
        self.btn_add_keyframe.setVisible(
            bool(self._transient_marker_ids) and not self._pinned_marker_id
        )

    # -- Clock-mode visuals / keyframe delete provided by MapTrajectoryMixin --

    def set_calendar_converter(self, converter: CalendarConverter) -> None:
        """Sets the calendar converter for formatting keyframe date labels."""
        self.view.set_calendar_converter(converter)
        self.layer_panel.set_calendar_converter(converter)

    # -- Keyframe delete provided by MapTrajectoryMixin ----------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard shortcuts for MapWidget."""
        if self._pinned_marker_id:
            if event.key() == Qt.Key.Key_Escape:
                self._cancel_clock_mode()
                event.accept()
                return
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._commit_clock_mode()
                event.accept()
                return
        elif event.key() == Qt.Key.Key_Escape:
            # Draft Mode: discard unsaved marker positions
            if self._transient_marker_ids:
                logger.debug("Esc pressed: Discarding draft marker positions")
                self._transient_marker_ids.clear()
                self._update_trajectory_positions(force_all=True)
                self._update_mode_indicator()
                event.accept()
                return
            # Deselect all items in the scene
            if self.view.graphics_scene.selectedItems():
                logger.debug("Esc pressed: Clearing selection")
                self.view.graphics_scene.clearSelection()
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
        """Handle resize to keep overlays and Finish Sketch button positioned."""
        super().resizeEvent(event)
        self._update_overlay_position()
        self._update_finish_sketch_position()
        self._position_legend_overlay()
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
        title.setStyleSheet(
            f"font-size: 18px; {StyleHelper.get_section_header_style()}"
        )
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
