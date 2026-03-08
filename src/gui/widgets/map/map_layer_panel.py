"""Map Layer Panel Widget.

A themed panel that visualises the hierarchical layer tree and provides
controls for creating/deleting layers, adjusting opacity, renaming,
and reordering via drag-and-drop.  Integrates with the application's
:class:`StyleHelper` / :class:`ThemeManager` for consistent look and feel.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QModelIndex, QPoint, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QSpinBox,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from src.core.map import MapLayerNode
from src.gui.utils.style_helper import StyleHelper

if TYPE_CHECKING:
    from src.gui.widgets.map.map_layer_model import MapLayerModel

logger = logging.getLogger(__name__)


class MapLayerPanel(QWidget):
    """Panel containing a QTreeView for the hierarchical layer system.

    Provides themed controls for:
    - Creating / deleting layer groups and leaf layers
    - Opacity adjustment via an inline slider
    - Renaming layers (double-click or context menu)
    - Drag-and-drop reordering
    - Bi-directional selection with the map view

    Signals:
        layer_selected: Emitted when a layer node is clicked.
            Payload is ``(node_id: str)``.
        create_group_requested: Emitted when the user wants a new group.
            Payload is ``(group_name: str)``.
        create_layer_requested: Emitted when the user wants a new leaf layer.
            Payload is ``(layer_name: str)``.
        delete_layer_requested: Emitted when the user wants to delete the
            currently selected layer.  Payload is ``(node_id: str)``.
        layer_opacity_changed: Emitted when opacity slider is moved.
            Payload is ``(node_id: str, opacity: float)``.
        layer_renamed: Emitted when a layer is renamed.
            Payload is ``(node_id: str, new_name: str)``.

    """

    layer_selected = Signal(str)
    create_group_requested = Signal(str)
    create_layer_requested = Signal(str)
    create_raster_layer_requested = Signal()
    delete_layer_requested = Signal(str)
    layer_opacity_changed = Signal(str, float, float)  # id, new, old
    layer_renamed = Signal(str, str)

    # Raster editing signals
    raster_edit_requested = Signal(str)  # node_id — start editing
    raster_edit_stopped = Signal()  # stop editing
    raster_palette_edit_requested = Signal(str)  # node_id
    raster_settings_changed = Signal()  # tool settings changed during editing
    raster_stats_requested = Signal(str)  # node_id — open stats dialog
    raster_blend_mode_changed = Signal(str, str, str)  # (node_id, new_mode, old_mode)
    raster_snapshot_requested = Signal(str)  # node_id — save snapshot at current date
    raster_preset_loaded = Signal(
        str, int, float, int
    )  # (tool_mode, size, falloff, value)
    raster_query_requested = Signal()  # open cross-layer query dialog
    raster_query_cleared = Signal()  # clear query overlay

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialise the panel.

        Args:
            parent: Parent widget.

        """
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        StyleHelper.apply_compact_spacing(main_layout)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # ── Header ────────────────────────────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)

        self._title_label = QLabel("Map Hierarchy")
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()

        self.btn_new_group = QPushButton("+ Group")
        self.btn_new_group.setToolTip("Create a new layer (container)")
        self.btn_new_group.clicked.connect(self._on_new_group)
        header_layout.addWidget(self.btn_new_group)

        self.btn_new_raster = QPushButton("+ Raster")
        self.btn_new_raster.setToolTip("Create a new raster / heatmap layer")
        self.btn_new_raster.clicked.connect(self._on_new_raster)
        header_layout.addWidget(self.btn_new_raster)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setToolTip("Delete the selected layer or feature")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._on_delete)
        header_layout.addWidget(self.btn_delete)

        main_layout.addLayout(header_layout)

        # ── Tree View ─────────────────────────────────────────────────
        self._tree = QTreeView(self)
        self._tree.setHeaderHidden(True)
        self._tree.setDragEnabled(True)
        self._tree.setAcceptDrops(True)
        self._tree.setDropIndicatorShown(True)
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setAnimated(True)
        self._tree.setExpandsOnDoubleClick(False)  # double-click = rename
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.clicked.connect(self._on_item_clicked)
        self._tree.doubleClicked.connect(self._on_item_double_clicked)

        main_layout.addWidget(self._tree, 1)  # stretch=1 to fill space

        # ── Opacity Bar ───────────────────────────────────────────────
        opacity_layout = QHBoxLayout()
        opacity_layout.setSpacing(4)

        self._opacity_label = QLabel("Opacity:")
        opacity_layout.addWidget(self._opacity_label)

        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(0, 100)
        self._opacity_slider.setValue(100)
        self._opacity_slider.setToolTip("Layer opacity (0–100 %)")
        self._opacity_slider.sliderPressed.connect(self._on_slider_pressed)
        self._opacity_slider.valueChanged.connect(self._on_opacity_preview)
        self._opacity_slider.sliderReleased.connect(self._on_opacity_committed)
        opacity_layout.addWidget(self._opacity_slider, 1)

        self._opacity_value_label = QLabel("100 %")
        self._opacity_value_label.setMinimumWidth(40)
        self._opacity_value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        opacity_layout.addWidget(self._opacity_value_label)

        main_layout.addLayout(opacity_layout)

        # ── Raster Edit Toolbar ──────────────────────────────────────
        self._raster_toolbar = QWidget(self)
        self._raster_toolbar.setVisible(False)
        rt_layout = QVBoxLayout(self._raster_toolbar)
        rt_layout.setContentsMargins(4, 4, 4, 4)
        rt_layout.setSpacing(4)

        rt_label = QLabel("Raster Tools")
        rt_layout.addWidget(rt_label)

        # Mode badge — shows "Discrete" or "Continuous" for the active raster layer
        self._raster_mode_label = QLabel()
        self._raster_mode_label.setObjectName("RasterModeBadge")
        self._raster_mode_label.setVisible(False)
        rt_layout.addWidget(self._raster_mode_label)

        # Internal lookup: node_id → mode string (populated by MapHandler)
        self._raster_mode_by_id: dict[str, str] = {}

        # Tool buttons row
        tool_row = QHBoxLayout()
        tool_row.setSpacing(2)
        self._btn_brush = QPushButton("Brush")
        self._btn_brush.setCheckable(True)
        self._btn_brush.setChecked(True)
        self._btn_fill = QPushButton("Fill")
        self._btn_fill.setCheckable(True)
        self._btn_gradient = QPushButton("Gradient")
        self._btn_gradient.setCheckable(True)
        self._btn_sample = QPushButton("Sample")
        self._btn_sample.setCheckable(True)
        for b in (
            self._btn_brush,
            self._btn_fill,
            self._btn_gradient,
            self._btn_sample,
        ):
            b.setAutoExclusive(True)
            b.toggled.connect(self._on_tool_mode_changed)
            tool_row.addWidget(b)
        rt_layout.addLayout(tool_row)

        # Brush settings row 1: Size and Value
        settings_row_1 = QHBoxLayout()
        settings_row_1.setSpacing(4)
        settings_row_1.addWidget(QLabel("Size:"))
        self._brush_size_spin = QSpinBox()
        self._brush_size_spin.setRange(1, 128)
        self._brush_size_spin.setValue(8)
        self._brush_size_spin.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        self._brush_size_spin.valueChanged.connect(self._on_raster_setting_changed)
        settings_row_1.addWidget(self._brush_size_spin)

        settings_row_1.addWidget(QLabel("Value:"))
        self._paint_value_spin = QSpinBox()
        self._paint_value_spin.setRange(0, 65535)
        self._paint_value_spin.setValue(1)
        self._paint_value_spin.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        self._paint_value_spin.valueChanged.connect(self._on_raster_setting_changed)
        settings_row_1.addWidget(self._paint_value_spin)
        settings_row_1.addStretch()
        rt_layout.addLayout(settings_row_1)

        # Entity / class picker — "Paint as: [Class Name ▾]" (discrete only)
        self._entity_picker_row = QWidget()
        ep_layout = QHBoxLayout(self._entity_picker_row)
        ep_layout.setContentsMargins(0, 0, 0, 0)
        ep_layout.setSpacing(4)
        ep_layout.addWidget(QLabel("Paint as:"))
        self._entity_picker_combo = QComboBox()
        self._entity_picker_combo.setToolTip(
            "Select a mapped class to automatically set the paint value"
        )
        self._entity_picker_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self._entity_picker_combo.currentIndexChanged.connect(self._on_entity_picked)
        ep_layout.addWidget(self._entity_picker_combo, 1)
        ep_layout.addStretch()
        rt_layout.addWidget(self._entity_picker_row)

        # Brush settings row 2: Falloff
        settings_row_2 = QHBoxLayout()
        settings_row_2.setSpacing(4)
        settings_row_2.addWidget(QLabel("Falloff:"))
        self._falloff_slider = QSlider(Qt.Orientation.Horizontal)
        self._falloff_slider.setRange(0, 100)
        self._falloff_slider.setValue(0)
        self._falloff_slider.setToolTip("Brush falloff (0=hard, 100=soft)")
        self._falloff_slider.valueChanged.connect(self._on_falloff_changed)
        settings_row_2.addWidget(self._falloff_slider, 1)  # Give slider stretch

        self._falloff_label = QLabel("0%")
        self._falloff_label.setMinimumWidth(32)
        self._falloff_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        settings_row_2.addWidget(self._falloff_label)
        rt_layout.addLayout(settings_row_2)

        # Edit / Done toggle + Palette button + Stats button
        action_row = QHBoxLayout()
        action_row.setSpacing(4)
        self._btn_edit_toggle = QPushButton("✎ Edit")
        self._btn_edit_toggle.setCheckable(True)
        self._btn_edit_toggle.toggled.connect(self._on_edit_toggled)
        action_row.addWidget(self._btn_edit_toggle)
        self._btn_palette = QPushButton("Palette…")
        self._btn_palette.clicked.connect(self._on_palette_clicked)
        action_row.addWidget(self._btn_palette)
        self._btn_stats = QPushButton("Stats…")
        self._btn_stats.setToolTip("Show coverage statistics for this raster layer")
        self._btn_stats.clicked.connect(self._on_stats_clicked)
        action_row.addWidget(self._btn_stats)
        self._btn_snapshot = QPushButton("📸 Snapshot")
        self._btn_snapshot.setToolTip(
            "Save snapshot of this raster layer at the current timeline date"
        )
        self._btn_snapshot.clicked.connect(self._on_snapshot_clicked)
        action_row.addWidget(self._btn_snapshot)
        self._snapshot_count_label = QLabel("")
        self._snapshot_count_label.setToolTip(
            "Number of saved temporal snapshots for this layer"
        )
        action_row.addWidget(self._snapshot_count_label)
        action_row.addStretch()
        rt_layout.addLayout(action_row)

        # Blend mode row
        blend_row = QHBoxLayout()
        blend_row.setSpacing(4)
        blend_row.addWidget(QLabel("Blend:"))
        self._blend_combo = QComboBox()
        from src.gui.widgets.map.raster_layer_item import BLEND_MODE_NAMES

        self._blend_combo.addItems(BLEND_MODE_NAMES)
        self._blend_combo.currentTextChanged.connect(self._on_blend_mode_changed)
        blend_row.addWidget(self._blend_combo)
        blend_row.addStretch()
        rt_layout.addLayout(blend_row)

        # Preset toolbar row (hidden until raster layer selected)
        self._preset_toolbar_row = QWidget()
        preset_layout = QHBoxLayout(self._preset_toolbar_row)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.setSpacing(4)
        preset_layout.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        self._preset_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        preset_layout.addWidget(self._preset_combo, 1)
        preset_layout.addStretch()
        self._preset_toolbar_row.setVisible(False)
        rt_layout.addWidget(self._preset_toolbar_row)

        # Query row (hidden until raster layer selected)
        self._query_row = QWidget()
        query_layout = QHBoxLayout(self._query_row)
        query_layout.setContentsMargins(0, 0, 0, 0)
        query_layout.setSpacing(4)
        self._btn_query = QPushButton("🔍 Query")
        self._btn_query.setToolTip("Build a cross-layer spatial query")
        self._btn_query.clicked.connect(lambda: self.raster_query_requested.emit())
        query_layout.addWidget(self._btn_query)
        self._btn_clear_query = QPushButton("✕ Clear Query")
        self._btn_clear_query.setToolTip("Remove the spatial query overlay")
        self._btn_clear_query.setVisible(False)
        self._btn_clear_query.clicked.connect(lambda: self.raster_query_cleared.emit())
        query_layout.addWidget(self._btn_clear_query)
        query_layout.addStretch()
        self._query_row.setVisible(False)
        rt_layout.addWidget(self._query_row)

        main_layout.addWidget(self._raster_toolbar)

        # ── Raster Legend ─────────────────────────────────────────────
        from src.gui.widgets.map.raster_legend_widget import RasterLegendWidget

        self._legend = RasterLegendWidget(self)
        self._legend.setVisible(False)
        main_layout.addWidget(self._legend)

        # ── Internal State ────────────────────────────────────────────
        self._model: Optional["MapLayerModel"] = None
        self._selected_node_id: Optional[str] = None
        self._current_node_id: str = ""
        self._slider_updating = False  # guard against feedback loops
        self._start_opacity: Optional[float] = None  # Opacity at drag start
        # Full raster layer metadata keyed by node_id (set by MapHandler)
        self._raster_meta_by_id: Dict[str, Dict[str, Any]] = {}

        # Apply all theme-aware styles
        self.refresh_styles()

        # Populate preset combo from saved presets
        self._refresh_preset_combo()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def selected_node_id(self) -> Optional[str]:
        """The ID of the currently selected layer node, or ``None``."""
        return self._selected_node_id

    @property
    def tree_view(self) -> QTreeView:
        """Access the underlying QTreeView."""
        return self._tree

    def set_model(self, model: "MapLayerModel") -> None:
        """Attach a :class:`MapLayerModel` to the tree view.

        Args:
            model: The layer model to display.

        """
        self._model = model
        self._tree.setModel(model)
        self._tree.expandAll()
        self._update_button_state()

    def select_node(self, node_id: str) -> None:
        """Highlight and scroll to the node with the given ID.

        Args:
            node_id: The layer node ID to select.

        """
        if self._model is None:
            return
        node = self._model.find_node_by_id(node_id)
        if node is None:
            return
        index = self._model.index_from_node(node)
        if index.isValid():
            self._tree.setCurrentIndex(index)
            self._tree.scrollTo(index)
            self._selected_node_id = node_id
            self._sync_opacity_slider(node)
            self._update_button_state()

    def refresh_styles(self) -> None:
        """Re-apply all theme-aware styles (call on theme change)."""
        import contextlib

        with contextlib.suppress(ImportError):
            import shiboken6

            if not shiboken6.isValid(self):
                return

        tool_style = StyleHelper.get_tool_button_style()
        self.btn_new_group.setStyleSheet(tool_style)

        self.btn_delete.setStyleSheet(StyleHelper.get_destructive_button_style())
        self._title_label.setStyleSheet(StyleHelper.get_panel_header_style())
        self._opacity_slider.setStyleSheet(StyleHelper.get_slider_style())
        self._falloff_slider.setStyleSheet(StyleHelper.get_slider_style())
        dim_style = f"color: {self._theme_token('text_dim')}; font-size: 9pt;"
        self._opacity_label.setStyleSheet(dim_style)
        self._opacity_value_label.setStyleSheet(
            f"color: {self._theme_token('text_main')}; font-size: 9pt;"
        )
        self._apply_tree_style()

        # Raster tool buttons — prominent checked state
        raster_style = StyleHelper.get_raster_tool_button_style()
        for btn in (
            self._btn_brush,
            self._btn_fill,
            self._btn_gradient,
            self._btn_sample,
            self._btn_edit_toggle,
        ):
            btn.setStyleSheet(raster_style)

    # ------------------------------------------------------------------
    # Private — style helpers
    # ------------------------------------------------------------------

    def _apply_tree_style(self) -> None:
        """Apply the theme-aware stylesheet to the tree view."""
        self._tree.setStyleSheet(StyleHelper.get_tree_view_style())

    @staticmethod
    def _theme_token(key: str) -> str:
        """Fetch a single token from the current theme.

        Args:
            key: Theme token name (e.g. ``'text_dim'``).

        Returns:
            str: The hex colour for that token.

        """
        from src.core.theme_manager import ThemeManager

        return ThemeManager().get_theme().get(key, "#888888")

    # ------------------------------------------------------------------
    # Private — button actions
    # ------------------------------------------------------------------

    @Slot()
    def _on_new_group(self) -> None:
        """Prompt the user for a name and emit create_group_requested."""
        name, ok = QInputDialog.getText(
            self, "New Group", "Group name:", text="New Group"
        )
        if ok and name.strip():
            self.create_group_requested.emit(name.strip())

    @Slot()
    def _on_new_raster(self) -> None:
        """Emit create_raster_layer_requested to open the raster dialog."""
        self.create_raster_layer_requested.emit()

    @Slot()
    def _on_delete(self) -> None:
        """Emit delete_layer_requested for the current selection."""
        if self._selected_node_id:
            self.delete_layer_requested.emit(self._selected_node_id)
            self._selected_node_id = None
            self._update_button_state()

    # ------------------------------------------------------------------
    # Private — tree interactions
    # ------------------------------------------------------------------

    @Slot(QModelIndex)
    def _on_item_clicked(self, index: QModelIndex) -> None:
        """Handle a click on a tree item.

        Args:
            index: The clicked model index.

        """
        if self._model is None or not index.isValid():
            return
        node = self._model.node_from_index(index)
        self._selected_node_id = node.id
        self._sync_opacity_slider(node)
        self._update_button_state()
        self._update_raster_toolbar(node)
        self.layer_selected.emit(node.id)

    @Slot(QModelIndex)
    def _on_item_double_clicked(self, index: QModelIndex) -> None:
        """Handle double-click → rename.

        Args:
            index: The double-clicked model index.

        """
        if self._model is None or not index.isValid():
            return
        node = self._model.node_from_index(index)
        name, ok = QInputDialog.getText(
            self, "Rename Layer", "New name:", text=node.name
        )
        if ok and name.strip():
            self.layer_renamed.emit(node.id, name.strip())

    # ------------------------------------------------------------------
    # Private — context menu
    # ------------------------------------------------------------------

    @Slot()
    def _show_context_menu(self, pos: QPoint) -> None:
        """Show a right-click context menu for the layer tree.

        Args:
            pos: Position of the click in widget coordinates.

        """
        index = self._tree.indexAt(pos)
        if self._model is None:
            return

        menu = QMenu(self)

        if index.isValid():
            node = self._model.node_from_index(index)
            self._selected_node_id = node.id
            self._sync_opacity_slider(node)
            self._update_button_state()

            # Toggle visibility
            vis_text = "Hide" if node.visible else "Show"
            action_toggle = menu.addAction(f"{vis_text} Layer")
            action_toggle.triggered.connect(lambda: self._toggle_visibility(node))

            # Rename
            action_rename = menu.addAction("Rename…")
            action_rename.triggered.connect(lambda: self._on_item_double_clicked(index))

            menu.addSeparator()

            # Delete
            action_delete = menu.addAction("Delete")
            action_delete.triggered.connect(self._on_delete)
        else:
            # Click on empty area — offer to create
            action_group = menu.addAction("New Group…")
            action_group.triggered.connect(self._on_new_group)
            action_raster = menu.addAction("New Raster Layer…")
            action_raster.triggered.connect(self._on_new_raster)

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _toggle_visibility(self, node: "MapLayerNode") -> None:
        """Toggle a node's visibility via the model.

        Args:
            node: The layer node to toggle.

        """
        if self._model is not None:
            self._model.set_node_visible(node, not node.visible)

    # ------------------------------------------------------------------
    # Private — opacity slider
    # ------------------------------------------------------------------

    @Slot(int)
    def _on_opacity_preview(self, value: int) -> None:
        """Handle slider drag (live preview).

        Updates the model (visuals) but does NOT emit the change signal,
        avoiding a flood of undo commands.

        Args:
            value: Slider value 0–100.

        """
        if self._slider_updating:
            return
        pct = value / 100.0
        self._opacity_value_label.setText(f"{value} %")
        if self._selected_node_id and self._model is not None:
            node = self._model.find_node_by_id(self._selected_node_id)
            if node is not None:
                # Update visual state only (no command, no auto-save)
                self._model.set_node_opacity(node, pct, preview=True)

    @Slot()
    def _on_slider_pressed(self) -> None:
        """Handle slider press to capture initial opacity."""
        if self._model is None or not self._selected_node_id:
            return
        if node := self._model.find_node_by_id(self._selected_node_id):
            self._start_opacity = node.opacity

    @Slot()
    def _on_opacity_committed(self) -> None:
        """Handle slider release (commit).

        Emits the change signal to create a single undoable command.
        """
        if self._slider_updating or self._model is None or not self._selected_node_id:
            return

        if node := self._model.find_node_by_id(self._selected_node_id):
            # Emit signal to create undo command, passing both new and old opacity
            # If _start_opacity is None (e.g. key press instead of drag),
            # try to use current (less ideal)
            old_opacity = (
                self._start_opacity if self._start_opacity is not None else node.opacity
            )
            self.layer_opacity_changed.emit(
                self._selected_node_id, node.opacity, old_opacity
            )
            self._start_opacity = None

    def _sync_opacity_slider(self, node: "MapLayerNode") -> None:
        """Update the slider to reflect the selected node's opacity.

        Args:
            node: The selected layer node.

        """
        self._slider_updating = True
        value = int(node.opacity * 100)
        self._opacity_slider.setValue(value)
        self._opacity_value_label.setText(f"{value} %")
        self._slider_updating = False

    # ------------------------------------------------------------------
    # Private — UI state
    # ------------------------------------------------------------------

    def _update_button_state(self) -> None:
        """Enable/disable the Delete button based on selection."""
        has_selection = self._selected_node_id is not None
        self.btn_delete.setEnabled(has_selection)

    # ------------------------------------------------------------------
    # Private — raster editing toolbar
    # ------------------------------------------------------------------

    def _update_raster_toolbar(self, node: "MapLayerNode") -> None:
        """Show or hide the raster editing toolbar.

        Also refreshes the legend and class picker when a raster is selected.

        Args:
            node: The newly selected layer node.
        """
        from src.app.constants import MAP_LAYER_TYPE_RASTER

        is_raster = node.layer_type == MAP_LAYER_TYPE_RASTER
        self._raster_toolbar.setVisible(is_raster)
        self._legend.setVisible(is_raster)

        if is_raster:
            self._current_node_id = node.id
            mode = self._raster_mode_by_id.get(node.id, "discrete")
            self._show_mode_badge(mode)
            # Refresh legend and entity picker from stored metadata
            layer_meta = self._raster_meta_by_id.get(node.id)
            self._legend.set_layer(layer_meta)
            self._refresh_entity_picker(layer_meta, mode)
            # Refresh blend mode combo without triggering signals
            blend_mode = (layer_meta or {}).get("blend_mode", "Normal")
            self._blend_combo.blockSignals(True)
            idx = self._blend_combo.findText(blend_mode)
            if idx >= 0:
                self._blend_combo.setCurrentIndex(idx)
            self._blend_combo.blockSignals(False)
            # Refresh snapshot count label
            snap_count = len((layer_meta or {}).get("snapshots", {}))
            if snap_count:
                self._snapshot_count_label.setText(
                    f"{snap_count} snapshot{'s' if snap_count != 1 else ''}"
                )
            else:
                self._snapshot_count_label.setText("")
            # Show preset and query rows
            self._preset_toolbar_row.setVisible(True)
            self._query_row.setVisible(True)
        else:
            self._current_node_id = ""
            self._raster_mode_label.setVisible(False)
            self._snapshot_count_label.setText("")
            self._preset_toolbar_row.setVisible(False)
            self._query_row.setVisible(False)

        # Reset edit toggle when switching layers
        if not is_raster and self._btn_edit_toggle.isChecked():
            self._btn_edit_toggle.setChecked(False)

    def _on_edit_toggled(self, checked: bool) -> None:
        """Handle the Edit / Done toggle button."""
        if checked:
            self._btn_edit_toggle.setText("✓ Done")
            if self._selected_node_id:
                self.raster_edit_requested.emit(self._selected_node_id)
        else:
            self._btn_edit_toggle.setText("✎ Edit")
            self.raster_edit_stopped.emit()

    def _on_palette_clicked(self) -> None:
        """Open the palette editor for the selected raster layer."""
        if self._selected_node_id:
            self.raster_palette_edit_requested.emit(self._selected_node_id)

    def _refresh_entity_picker(
        self,
        layer_meta: Optional[Dict[str, Any]],
        mode: str,
    ) -> None:
        """Repopulate the *Paint as:* class picker from *layer_meta*.

        The picker is only visible for discrete layers with at least one
        defined class.  For continuous layers it is always hidden.

        Args:
            layer_meta: Raster layer metadata dict, or ``None``.
            mode: ``"discrete"`` or ``"continuous"``.

        """
        from src.gui.widgets.map.raster_mapping import get_discrete_class_choices

        is_discrete = mode != "continuous"
        choices: List[Tuple[str, int]] = []

        if is_discrete and layer_meta:
            choices = get_discrete_class_choices(layer_meta)

        # Block signals while repopulating to avoid spurious value changes
        self._entity_picker_combo.blockSignals(True)
        self._entity_picker_combo.clear()
        if choices:
            self._entity_picker_combo.addItem("— manual —", -1)
            for label, value in choices:
                self._entity_picker_combo.addItem(f"{label}  ({value})", value)

        self._entity_picker_combo.blockSignals(False)
        self._entity_picker_row.setVisible(is_discrete and bool(choices))

    @Slot(int)
    def _on_entity_picked(self, index: int) -> None:
        """Set paint value to the value of the selected class.

        Args:
            index: Combo box index of the selected item.

        """
        value = self._entity_picker_combo.itemData(index)
        if value is not None and value >= 0:
            self._paint_value_spin.setValue(int(value))

    def set_raster_mode_metadata(self, mode_by_id: "dict[str, str]") -> None:
        """Update the cached raster mode lookup used by the mode badge.

        Should be called by :class:`MapHandler` after loading raster layers.

        Args:
            mode_by_id: Mapping of ``node_id`` → ``"discrete"`` or ``"continuous"``.
        """
        self._raster_mode_by_id = mode_by_id
        # Refresh badge if a raster layer is already selected
        if self._selected_node_id and self._model is not None:
            node = self._model.find_node_by_id(self._selected_node_id)
            if node is not None:
                from src.app.constants import MAP_LAYER_TYPE_RASTER

                if node.layer_type == MAP_LAYER_TYPE_RASTER:
                    mode = self._raster_mode_by_id.get(
                        self._selected_node_id, "discrete"
                    )
                    self._show_mode_badge(mode)

    def set_raster_layer_metadata(
        self, meta_by_id: "Dict[str, Dict[str, Any]]"
    ) -> None:
        """Store full raster layer metadata for legend and class picker.

        Should be called by :class:`MapHandler` after loading raster layers,
        immediately after :meth:`set_raster_mode_metadata`.

        Args:
            meta_by_id: Mapping of ``node_id`` → full raster layer metadata
                dict (the same dicts stored in
                ``maps.attributes["raster_layers"]``).

        """
        self._raster_meta_by_id = meta_by_id
        # Refresh legend and picker if a raster is already selected
        if self._selected_node_id and self._model is not None:
            node = self._model.find_node_by_id(self._selected_node_id)
            if node is not None:
                from src.app.constants import MAP_LAYER_TYPE_RASTER

                if node.layer_type == MAP_LAYER_TYPE_RASTER:
                    mode = self._raster_mode_by_id.get(
                        self._selected_node_id, "discrete"
                    )
                    layer_meta = self._raster_meta_by_id.get(self._selected_node_id)
                    self._legend.set_layer(layer_meta)
                    self._refresh_entity_picker(layer_meta, mode)

    def _show_mode_badge(self, mode: str) -> None:
        """Render the mode badge label with the correct text and style.

        Args:
            mode: ``"discrete"`` or ``"continuous"``.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()

        if mode == "discrete":
            icon = "📊"
            text = "Discrete — categories / classes"
            bg = theme.get("accent_secondary", "#4A90D9")
        else:
            icon = "📈"
            text = "Continuous — scalar gradient"
            bg = theme.get("primary", "#5C82FF")

        # If continuous mode, and the user still has the tiny default paint
        # value (1), bump it to a reasonable middle value so brush/gradient
        # painting is visible by default. This avoids the common confusion
        # where continuous ramps painted with value=1 are visually null.
        try:
            if mode == "continuous" and self._paint_value_spin.value() < 256:
                self._paint_value_spin.setValue(32768)
        except Exception:
            # In some test contexts _paint_value_spin may not yet exist; ignore
            pass

        self._raster_mode_label.setText(f"{icon}  {text}")
        self._raster_mode_label.setStyleSheet(
            f"QLabel#RasterModeBadge {{"
            f"  background-color: {bg};"
            f"  color: #FFFFFF;"
            f"  border-radius: 4px;"
            f"  padding: 2px 8px;"
            f"  font-size: 8pt;"
            f"  font-weight: bold;"
            f"}}"
        )
        self._raster_mode_label.setVisible(True)

    @Slot()
    def _on_falloff_changed(self) -> None:
        """Update falloff label and emit settings changed."""
        value = self._falloff_slider.value()
        self._falloff_label.setText(f"{value}%")
        self._on_raster_setting_changed()

    @Slot()
    def _on_raster_setting_changed(self) -> None:
        """Emit raster_settings_changed when any tool setting changes."""
        self.raster_settings_changed.emit()

    @Slot(bool)
    def _on_tool_mode_changed(self, _checked: bool) -> None:
        """Emit settings changed when tool mode button is toggled."""
        self.raster_settings_changed.emit()

    @property
    def raster_tool_mode(self) -> str:
        """Currently selected raster tool mode name."""
        if self._btn_fill.isChecked():
            return "fill"
        return (
            "gradient"
            if self._btn_gradient.isChecked()
            else "sample"
            if self._btn_sample.isChecked()
            else "brush"
        )

    @property
    def raster_brush_size(self) -> int:
        """Current brush size from the spin box."""
        return self._brush_size_spin.value()

    @property
    def raster_paint_value(self) -> int:
        """Current paint value from the spin box."""
        return self._paint_value_spin.value()

    @property
    def raster_falloff(self) -> float:
        """Current falloff (0.0–1.0) from the slider."""
        return self._falloff_slider.value() / 100.0

    @Slot()
    def _on_stats_clicked(self) -> None:
        """Emit raster_stats_requested for the currently selected raster layer."""
        if self._current_node_id:
            self.raster_stats_requested.emit(self._current_node_id)

    @Slot()
    def _on_snapshot_clicked(self) -> None:
        """Emit snapshot request for the currently selected raster layer."""
        if self._current_node_id:
            self.raster_snapshot_requested.emit(self._current_node_id)

    @Slot(str)
    def _on_blend_mode_changed(self, new_mode: str) -> None:
        """Emit raster_blend_mode_changed when the blend combo selection changes.

        Args:
            new_mode: The newly selected blend mode name.
        """
        node_id = self._current_node_id
        if not node_id:
            return
        meta = self._raster_meta_by_id.get(node_id, {})
        old_mode = meta.get("blend_mode", "Normal")
        if old_mode == new_mode:
            return
        self.raster_blend_mode_changed.emit(node_id, new_mode, old_mode)

    # ------------------------------------------------------------------
    # Brush preset helpers (Feature A)
    # ------------------------------------------------------------------

    def _refresh_preset_combo(self) -> None:
        """Reload presets from QSettings and repopulate the combo box."""
        from src.core.raster_presets import PresetStore

        self._preset_combo.blockSignals(True)
        self._preset_combo.clear()
        self._preset_combo.addItem("— select preset —", None)
        for preset in PresetStore.load():
            self._preset_combo.addItem(preset.name, preset)
        self._preset_combo.addItem("💾 Save current…", "save")
        self._preset_combo.setCurrentIndex(0)
        self._preset_combo.blockSignals(False)

    @Slot(int)
    def _on_preset_selected(self, index: int) -> None:
        """Handle preset combo selection.

        Args:
            index: Selected combo index.
        """
        from src.core.raster_presets import BrushPreset

        data = self._preset_combo.itemData(index)
        if data is None:
            return
        if data == "save":
            self._on_save_preset()
            # Reset back to placeholder
            self._preset_combo.blockSignals(True)
            self._preset_combo.setCurrentIndex(0)
            self._preset_combo.blockSignals(False)
            return

        if not isinstance(data, BrushPreset):
            return

        preset: BrushPreset = data
        # Apply preset values to controls
        self._brush_size_spin.setValue(preset.size)
        self._falloff_slider.setValue(int(preset.falloff * 100))
        self._paint_value_spin.setValue(preset.paint_value)

        # Select the matching tool mode button
        mode_map = {
            "brush": self._btn_brush,
            "fill": self._btn_fill,
            "gradient": self._btn_gradient,
            "sample": self._btn_sample,
        }
        btn = mode_map.get(preset.tool_mode, self._btn_brush)
        btn.setChecked(True)

        # Emit so MapHandler picks up the new settings
        self.raster_settings_changed.emit()
        self.raster_preset_loaded.emit(
            preset.tool_mode,
            preset.size,
            preset.falloff,
            preset.paint_value,
        )

        # Reset combo to placeholder
        self._preset_combo.blockSignals(True)
        self._preset_combo.setCurrentIndex(0)
        self._preset_combo.blockSignals(False)

    def _on_save_preset(self) -> None:
        """Prompt user for a name and save the current settings as a preset."""
        from src.core.raster_presets import BrushPreset, PresetStore

        name, ok = QInputDialog.getText(
            self, "Save Preset", "Preset name:", text="My Preset"
        )
        if not ok or not name.strip():
            return

        preset = BrushPreset(
            name=name.strip(),
            tool_mode=self.raster_tool_mode,
            size=self.raster_brush_size,
            falloff=self.raster_falloff,
            paint_value=self.raster_paint_value,
        )
        presets = PresetStore.load()
        presets.append(preset)
        PresetStore.save(presets)
        self._refresh_preset_combo()

    # ------------------------------------------------------------------
    # Query overlay helpers (Feature D)
    # ------------------------------------------------------------------

    def set_query_active(self, active: bool) -> None:
        """Show or hide the 'Clear Query' button depending on query state.

        Args:
            active: ``True`` when a query overlay is visible.
        """
        self._btn_clear_query.setVisible(active)
