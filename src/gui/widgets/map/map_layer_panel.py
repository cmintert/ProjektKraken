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
    QFrame,
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

from src.app.ui_constants import Spacing
from src.core.map import MapLayerNode
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.map.raster_layer_item import BLEND_MODE_NAMES

if TYPE_CHECKING:
    from src.gui.widgets.map.map_layer_model import MapLayerModel

logger = logging.getLogger(__name__)

# Label width used for consistent alignment across raster tool rows.
_LABEL_WIDTH = 92


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
    raster_snapshot_selected = Signal(
        str, float
    )  # node_id, lore_date — jump playhead
    raster_snapshot_delete_requested = Signal(
        str, float
    )  # node_id, lore_date — delete snapshot
    raster_gradient_sub_mode_changed = Signal(str)  # gradient sub-mode name
    raster_notes_requested = Signal(str)  # node_id — open notes dialog
    raster_preset_loaded = Signal(
        str, int, float, int
    )  # (tool_mode, size, falloff, value)
    raster_query_requested = Signal()  # open cross-layer query dialog
    raster_query_cleared = Signal()  # clear query overlay
    # Carries (node_id, layer_meta_or_None) when a raster layer is selected;
    # also emitted with (None, None) when a non-raster layer is selected.
    raster_layer_selected = Signal(object, object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialise the panel.

        Args:
            parent: Parent widget.

        """
        super().__init__(parent)

        # ── Internal State ────────────────────────────────────────────
        self._model: Optional["MapLayerModel"] = None
        self._selected_node_id: Optional[str] = None
        self._current_node_id: str = ""
        self._slider_updating = False  # guard against feedback loops
        self._start_opacity: Optional[float] = None  # Opacity at drag start
        self._slider_dragging = False  # True while mouse is on the slider handle
        # Last committed opacity for the selected node — used as the
        # "old" value when a discrete change (keyboard) is committed.
        self._committed_opacity: Optional[float] = None
        # Full raster layer metadata keyed by node_id (set by MapHandler)
        self._raster_meta_by_id: Dict[str, Dict[str, Any]] = {}
        self._calendar_converter: Optional[Any] = None
        # Internal lookup: node_id → mode string (populated by MapHandler)
        self._raster_mode_by_id: dict[str, str] = {}

        # ── Build UI ─────────────────────────────────────────────────
        main_layout = QVBoxLayout(self)
        StyleHelper.apply_compact_spacing(main_layout)
        main_layout.setContentsMargins(
            Spacing.COMPACT, Spacing.COMPACT, Spacing.COMPACT, Spacing.COMPACT
        )

        self._build_header(main_layout)
        self._build_tree_view(main_layout)
        self._build_opacity_bar(main_layout)
        self._build_raster_toolbar(main_layout)

        # Apply all theme-aware styles
        self.refresh_styles()

        # Populate preset combo from saved presets
        self._refresh_preset_combo()

    # ------------------------------------------------------------------
    # Private — UI construction helpers
    # ------------------------------------------------------------------

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        """Build the header row with title and action buttons.

        Args:
            parent_layout: Layout to append the header into.
        """
        header_layout = QHBoxLayout()
        header_layout.setSpacing(Spacing.COMPACT)

        self._title_label = QLabel("Map Hierarchy")
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()

        self.btn_new_group = self._make_button(
            "+ Group", "Create a new layer (container)", self._on_new_group
        )
        header_layout.addWidget(self.btn_new_group)

        self.btn_new_raster = self._make_button(
            "+ Raster", "Create a new raster / heatmap layer", self._on_new_raster
        )
        header_layout.addWidget(self.btn_new_raster)

        header_layout.addSpacing(8)

        self.btn_delete = self._make_button(
            "Delete",
            "Delete the selected layer or feature",
            self._on_delete,
            enabled=False,
        )
        self.btn_delete.setStyleSheet(StyleHelper.get_ghost_destructive_button_style())
        header_layout.addWidget(self.btn_delete)

        parent_layout.addLayout(header_layout)

    def _build_tree_view(self, parent_layout: QVBoxLayout) -> None:
        """Build the layer tree view with drag-and-drop.

        Args:
            parent_layout: Layout to append the tree into.
        """
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

        parent_layout.addWidget(self._tree, 1)

    def _build_opacity_bar(self, parent_layout: QVBoxLayout) -> None:
        """Build the opacity slider row.

        Args:
            parent_layout: Layout to append the opacity controls into.
        """
        self._opacity_label = QLabel("Opacity:")
        self._opacity_value_label = QLabel("100 %")
        self._opacity_value_label.setMinimumWidth(40)
        self._opacity_value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(0, 100)
        self._opacity_slider.setValue(100)
        self._opacity_slider.setToolTip("Layer opacity (0–100 %)")
        self._opacity_slider.sliderPressed.connect(self._on_slider_pressed)
        self._opacity_slider.valueChanged.connect(self._on_opacity_preview)
        self._opacity_slider.sliderReleased.connect(self._on_opacity_committed)

        opacity_layout = QHBoxLayout()
        opacity_layout.setSpacing(Spacing.COMPACT)
        opacity_layout.addWidget(self._opacity_label)
        opacity_layout.addWidget(self._opacity_slider, 1)
        opacity_layout.addWidget(self._opacity_value_label)
        parent_layout.addLayout(opacity_layout)

    def _build_raster_toolbar(self, parent_layout: QVBoxLayout) -> None:
        """Build the raster editing toolbar (hidden by default).

        Args:
            parent_layout: Layout to append the toolbar into.
        """
        self._raster_toolbar = QWidget(self)
        self._raster_toolbar.setVisible(False)
        rt = QVBoxLayout(self._raster_toolbar)
        rt.setContentsMargins(
            Spacing.COMPACT, Spacing.COMPACT, Spacing.COMPACT, Spacing.COMPACT
        )
        rt.setSpacing(Spacing.COMPACT)

        rt.addWidget(QLabel("Raster Tools"))

        # Mode badge — shows "Discrete" or "Continuous"
        self._raster_mode_label = QLabel()
        self._raster_mode_label.setObjectName("RasterModeBadge")
        self._raster_mode_label.setVisible(False)
        rt.addWidget(self._raster_mode_label)

        self._build_tool_mode_buttons(rt)

        rt.addWidget(self._make_section_separator("PAINT"))
        self._build_paint_settings(rt)

        rt.addWidget(self._make_section_separator("SNAPSHOTS"))
        self._build_action_rows(rt)

        rt.addWidget(self._make_section_separator("DISPLAY"))
        self._build_layer_settings(rt)

        parent_layout.addWidget(self._raster_toolbar)

    def _build_tool_mode_buttons(self, rt: QVBoxLayout) -> None:
        """Build the mutually exclusive raster tool mode buttons.

        Args:
            rt: Raster toolbar layout to append into.
        """
        tool_row = QHBoxLayout()
        tool_row.setSpacing(2)

        tool_defs: list[tuple[str, str, bool, str]] = [
            ("_btn_brush", "Brush", True, "Paint individual pixels with the selected value"),
            ("_btn_fill", "Fill", False, "Flood-fill a contiguous region with the selected value"),
            ("_btn_gradient", "Gradient", False, "Paint a smooth gradient from center to edge of brush"),
            ("_btn_sample", "Sample", False, "Sample the value under the cursor (eye-dropper)"),
        ]
        for attr, label, checked, tooltip in tool_defs:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(checked)
            btn.setAutoExclusive(True)
            btn.setToolTip(tooltip)
            btn.toggled.connect(self._on_tool_mode_changed)
            setattr(self, attr, btn)
            tool_row.addWidget(btn)

        self._sample_tool_enabled_tooltip = self._btn_sample.toolTip()
        self._sample_tool_disabled_tooltip = (
            "Sample is unavailable for color rasters because they preserve RGBA pixels, "
            "not paintable scalar values"
        )

        rt.addLayout(tool_row)

    def _build_paint_settings(self, rt: QVBoxLayout) -> None:
        """Build paint parameter controls (size, value, entity picker, falloff, gradient).

        Args:
            rt: Raster toolbar layout to append into.
        """
        self._brush_size_spin = self._make_labeled_spinbox(
            rt, "Size:", 1, 128, 8, self._on_raster_setting_changed
        )
        self._brush_size_spin.setToolTip("Brush radius in pixels (1–128)")
        self._paint_value_spin = self._make_labeled_spinbox(
            rt, "Value:", 0, 65535, 1, self._on_paint_value_spin_changed
        )
        self._paint_value_spin.setToolTip("Raw raster value to paint (0–65535)")
        self._build_entity_picker(rt)

        self._falloff_slider, self._falloff_label = self._make_labeled_slider(
            rt,
            "Falloff:",
            0,
            100,
            0,
            "Brush falloff (0=hard, 100=soft)",
            self._on_falloff_changed,
        )

        self._build_gradient_sub_combo(rt)

    def _build_entity_picker(self, rt: QVBoxLayout) -> None:
        """Build the entity/class picker combo row (discrete rasters only).

        Args:
            rt: Raster toolbar layout to append into.
        """
        self._entity_picker_row = QWidget()
        ep_layout = QHBoxLayout(self._entity_picker_row)
        ep_layout.setContentsMargins(0, 0, 0, 0)
        ep_layout.setSpacing(Spacing.COMPACT)
        ep_layout.addWidget(QLabel("Paint as:"))
        self._entity_picker_combo = QComboBox()
        self._entity_picker_combo.setToolTip(
            "Shows the mapped class for the current paint value.  "
            "Select a class here to jump to its value, or type a value above to "
            "auto-highlight the matching class."
        )
        self._entity_picker_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self._entity_picker_combo.currentIndexChanged.connect(self._on_entity_picked)
        ep_layout.addWidget(self._entity_picker_combo, 1)
        ep_layout.addStretch()
        rt.addWidget(self._entity_picker_row)

    def _build_gradient_sub_combo(self, rt: QVBoxLayout) -> None:
        """Build the gradient sub-mode combo row.

        Args:
            rt: Raster toolbar layout to append into.
        """
        gradient_row = QHBoxLayout()
        gradient_row.setSpacing(Spacing.COMPACT)
        grad_lbl = QLabel("Gradient Style:")
        grad_lbl.setFixedWidth(_LABEL_WIDTH)
        gradient_row.addWidget(grad_lbl)
        self._gradient_sub_combo = QComboBox()
        self._gradient_sub_combo.addItems(["Linear", "Radial", "Reflected"])
        self._gradient_sub_combo.setToolTip(
            "Select gradient style (only applies when Gradient tool is active)"
        )
        self._gradient_sub_combo.currentTextChanged.connect(
            lambda t: self.raster_gradient_sub_mode_changed.emit(t.lower())
        )
        gradient_row.addWidget(self._gradient_sub_combo, 1)
        rt.addLayout(gradient_row)

    def _build_action_rows(self, rt: QVBoxLayout) -> None:
        """Build the action button rows (edit, palette, stats, snapshot).

        Args:
            rt: Raster toolbar layout to append into.
        """
        action_row = QHBoxLayout()
        action_row.setSpacing(Spacing.COMPACT)
        self._btn_edit_toggle = QPushButton("✎ Edit")
        self._btn_edit_toggle.setCheckable(True)
        self._btn_edit_toggle.setToolTip("Enter/exit raster edit mode — changes are applied to the active layer")
        self._btn_edit_toggle.toggled.connect(self._on_edit_toggled)
        action_row.addWidget(self._btn_edit_toggle)
        self._btn_palette = self._make_button(
            "Edit Palette…",
            "Open the colour map / class palette editor",
            self._on_palette_clicked,
        )
        action_row.addWidget(self._btn_palette)
        self._btn_stats = self._make_button(
            "Stats…",
            "Show coverage statistics for this raster layer",
            self._on_stats_clicked,
        )
        action_row.addWidget(self._btn_stats)
        action_row.addStretch()
        rt.addLayout(action_row)

        snapshot_row = QHBoxLayout()
        snapshot_row.setSpacing(Spacing.COMPACT)
        self._btn_snapshot = self._make_button(
            "📸 Snapshot",
            "Save snapshot of this raster layer at the current timeline date",
            self._on_snapshot_clicked,
        )
        snapshot_row.addWidget(self._btn_snapshot)
        self._snapshot_count_label = QLabel("")
        self._snapshot_count_label.setToolTip(
            "Number of saved temporal snapshots for this layer"
        )
        snapshot_row.addWidget(self._snapshot_count_label)
        snapshot_row.addStretch()
        rt.addLayout(snapshot_row)

    def _build_layer_settings(self, rt: QVBoxLayout) -> None:
        """Build layer-level controls (blend, notes, presets, query).

        Args:
            rt: Raster toolbar layout to append into.
        """
        # Blend mode
        blend_row = QHBoxLayout()
        blend_row.setSpacing(Spacing.COMPACT)
        blend_row.addWidget(QLabel("Blend:"))
        self._blend_combo = QComboBox()
        self._blend_combo.addItems(BLEND_MODE_NAMES)
        self._blend_combo.setToolTip("How this layer blends with layers below it")
        self._blend_combo.currentTextChanged.connect(self._on_blend_mode_changed)
        blend_row.addWidget(self._blend_combo)
        blend_row.addStretch()
        rt.addLayout(blend_row)

        # Notes
        notes_row = QHBoxLayout()
        notes_row.setSpacing(Spacing.COMPACT)
        self._btn_notes = self._make_button(
            "📝 Notes",
            "Add or edit text notes for this raster layer",
            self._on_notes_clicked,
        )
        notes_row.addWidget(self._btn_notes)
        self._notes_indicator_label = QLabel("")
        self._notes_indicator_label.setToolTip("This layer has saved notes")
        notes_row.addWidget(self._notes_indicator_label)
        notes_row.addStretch()
        rt.addLayout(notes_row)

        # Preset toolbar row (hidden until raster layer selected)
        self._preset_toolbar_row = QWidget()
        preset_layout = QHBoxLayout(self._preset_toolbar_row)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.setSpacing(Spacing.COMPACT)
        preset_layout.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        self._preset_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self._preset_combo.setToolTip("Apply a saved brush preset to the current layer")
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        preset_layout.addWidget(self._preset_combo, 1)
        preset_layout.addStretch()
        self._preset_toolbar_row.setVisible(False)
        rt.addWidget(self._preset_toolbar_row)

        # Query row (hidden until raster layer selected)
        self._query_row = QWidget()
        query_layout = QHBoxLayout(self._query_row)
        query_layout.setContentsMargins(0, 0, 0, 0)
        query_layout.setSpacing(Spacing.COMPACT)
        self._btn_query = self._make_button(
            "🔍 Query",
            "Build a cross-layer spatial query",
            lambda: self.raster_query_requested.emit(),
        )
        query_layout.addWidget(self._btn_query)
        self._btn_clear_query = self._make_button(
            "✕ Clear Query",
            "Remove the spatial query overlay",
            lambda: self.raster_query_cleared.emit(),
            visible=False,
        )
        query_layout.addWidget(self._btn_clear_query)
        query_layout.addStretch()
        self._query_row.setVisible(False)
        rt.addWidget(self._query_row)

    # ------------------------------------------------------------------
    # Private — widget factory helpers (DRY)
    # ------------------------------------------------------------------

    @staticmethod
    def _make_button(
        text: str,
        tooltip: str,
        on_click: Any,
        *,
        enabled: bool = True,
        visible: bool = True,
    ) -> QPushButton:
        """Create a push button with consistent setup.

        Args:
            text: Button label.
            tooltip: Tooltip text (empty string to skip).
            on_click: Slot to connect to ``clicked``.
            enabled: Initial enabled state.
            visible: Initial visibility.

        Returns:
            The configured ``QPushButton``.
        """
        btn = QPushButton(text)
        if tooltip:
            btn.setToolTip(tooltip)
        btn.clicked.connect(on_click)
        if not enabled:
            btn.setEnabled(False)
        if not visible:
            btn.setVisible(False)
        return btn

    @staticmethod
    def _make_labeled_spinbox(
        parent_layout: QVBoxLayout,
        label: str,
        min_val: int,
        max_val: int,
        default: int,
        on_changed: Any,
    ) -> QSpinBox:
        """Create a labeled spin box row and append it to *parent_layout*.

        Args:
            parent_layout: Layout to add the row into.
            label: Row label text.
            min_val: Minimum spin box value.
            max_val: Maximum spin box value.
            default: Initial spin box value.
            on_changed: Slot connected to ``valueChanged``.

        Returns:
            The configured ``QSpinBox``.
        """
        row = QHBoxLayout()
        row.setSpacing(Spacing.COMPACT)
        lbl = QLabel(label)
        lbl.setFixedWidth(_LABEL_WIDTH)
        row.addWidget(lbl)
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        spin.valueChanged.connect(on_changed)
        row.addWidget(spin, 1)
        parent_layout.addLayout(row)
        return spin

    @staticmethod
    def _make_labeled_slider(
        parent_layout: QVBoxLayout,
        label: str,
        min_val: int,
        max_val: int,
        default: int,
        tooltip: str,
        on_changed: Any,
    ) -> Tuple[QSlider, QLabel]:
        """Create a labeled slider row with a value readout label.

        Args:
            parent_layout: Layout to add the row into.
            label: Row label text.
            min_val: Minimum slider value.
            max_val: Maximum slider value.
            default: Initial slider value.
            tooltip: Slider tooltip text.
            on_changed: Slot connected to ``valueChanged``.

        Returns:
            A ``(slider, value_label)`` tuple.
        """
        row = QHBoxLayout()
        row.setSpacing(Spacing.COMPACT)
        lbl = QLabel(label)
        lbl.setFixedWidth(_LABEL_WIDTH)
        row.addWidget(lbl)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        slider.setToolTip(tooltip)
        slider.valueChanged.connect(on_changed)
        row.addWidget(slider, 1)

        value_label = QLabel(f"{default}%")
        value_label.setMinimumWidth(32)
        value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        row.addWidget(value_label)
        parent_layout.addLayout(row)
        return slider, value_label

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

    def set_calendar_converter(self, converter: object) -> None:
        """Set the calendar converter used for snapshot date labels.

        Args:
            converter: Object exposing ``format_date(float) -> str``.
        """
        self._calendar_converter = converter
        if self._selected_node_id and self._model is not None:
            node = self._model.find_node_by_id(self._selected_node_id)
            if node is not None:
                from src.app.constants import MAP_LAYER_TYPE_RASTER

                if node.layer_type == MAP_LAYER_TYPE_RASTER:
                    layer_meta = self._raster_meta_by_id.get(self._selected_node_id)
                    self._refresh_snapshot_list(self._selected_node_id, layer_meta)

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

        self.btn_delete.setStyleSheet(StyleHelper.get_ghost_destructive_button_style())
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

    @staticmethod
    def _make_section_separator(label: str = "") -> QWidget:
        """Create a thin horizontal separator with an optional dim section label.

        Args:
            label: Optional short section name shown to the left of the line.

        Returns:
            A widget containing the label and separator line.
        """
        label_style, line_style = StyleHelper.get_section_separator_style()

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, Spacing.COMPACT, 0, 2)
        layout.setSpacing(Spacing.COMPACT)

        if label:
            lbl = QLabel(label)
            lbl.setStyleSheet(label_style)
            layout.addWidget(lbl)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setStyleSheet(line_style)
        layout.addWidget(line, 1)
        return widget

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

        from src.app.constants import MAP_LAYER_TYPE_SNAPSHOT

        if node.layer_type == MAP_LAYER_TYPE_SNAPSHOT:
            # Jump playhead but keep parent raster toolbar active.
            lore_date = float(node.attributes.get("lore_date", 0.0))
            parent_id = str(node.attributes.get("parent_node_id", ""))
            self.raster_snapshot_selected.emit(parent_id, lore_date)
            # Restore tree selection to the parent raster.
            if self._selected_node_id:
                parent_node = self._model.find_node_by_id(self._selected_node_id)
                if parent_node is not None:
                    parent_idx = self._model.index_from_node(parent_node)
                    if parent_idx.isValid():
                        self._tree.setCurrentIndex(parent_idx)
            return

        # Before switching selection, flush any pending drag commit so
        # the outgoing node's opacity change is persisted.
        self._flush_pending_opacity_commit()
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

            from src.app.constants import MAP_LAYER_TYPE_SNAPSHOT

            if node.layer_type == MAP_LAYER_TYPE_SNAPSHOT:
                lore_date = float(node.attributes.get("lore_date", 0.0))
                parent_id = str(node.attributes.get("parent_node_id", ""))
                action_jump = menu.addAction("↰ Jump Playhead Here")
                action_jump.triggered.connect(
                    lambda _=False, pid=parent_id, ld=lore_date: self.raster_snapshot_selected.emit(pid, ld)
                )
                menu.addSeparator()
                action_del = menu.addAction("🗑 Delete Snapshot")
                action_del.triggered.connect(
                    lambda _=False, pid=parent_id, ld=lore_date: self.raster_snapshot_delete_requested.emit(pid, ld)
                )
                menu.exec(self._tree.viewport().mapToGlobal(pos))
                return

            self._selected_node_id = node.id
            self._sync_opacity_slider(node)
            self._update_button_state()

            from src.app.constants import MAP_LAYER_BASEMAP_NODE_ID

            is_basemap = node.id == MAP_LAYER_BASEMAP_NODE_ID

            # Toggle visibility
            vis_text = "Hide" if node.visible else "Show"
            action_toggle = menu.addAction(f"{vis_text} Layer")
            action_toggle.triggered.connect(lambda: self._toggle_visibility(node))

            # Rename (not allowed for the pinned basemap node)
            if not is_basemap:
                action_rename = menu.addAction("Rename…")
                action_rename.triggered.connect(
                    lambda: self._on_item_double_clicked(index)
                )

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
        """Handle slider value change (live preview).

        Updates the model visuals on every tick.  When the change did NOT
        originate from a mouse drag (``_slider_dragging`` is False) — e.g.
        arrow keys, Page Up/Down or a click at a new position — it also
        commits so the change reaches the undo stack and database.

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
                # Discrete changes (keyboard, click-at-position) are not
                # bracketed by sliderPressed/Released, so commit now.
                if not self._slider_dragging:
                    self._commit_opacity(node)

    @Slot()
    def _on_slider_pressed(self) -> None:
        """Handle slider press to capture initial opacity."""
        self._slider_dragging = True
        if self._model is None or not self._selected_node_id:
            return
        if node := self._model.find_node_by_id(self._selected_node_id):
            self._start_opacity = node.opacity

    @Slot()
    def _on_opacity_committed(self) -> None:
        """Handle slider release (commit).

        Emits the change signal to create a single undoable command.
        """
        self._slider_dragging = False
        if self._slider_updating or self._model is None or not self._selected_node_id:
            return

        if node := self._model.find_node_by_id(self._selected_node_id):
            self._commit_opacity(node)

    def _flush_pending_opacity_commit(self) -> None:
        """Commit an in-flight drag if the slider state suggests one.

        Called on selection change or when the panel is about to lose
        focus, so an abandoned drag still produces an undo entry and a
        database write.
        """
        if self._model is None or not self._selected_node_id:
            return
        if self._start_opacity is None:
            return
        node = self._model.find_node_by_id(self._selected_node_id)
        if node is None:
            return
        self._slider_dragging = False
        self._commit_opacity(node)

    def _commit_opacity(self, node: "MapLayerNode") -> None:
        """Emit the opacity-changed signal once per discrete edit.

        Uses ``_start_opacity`` when available (mouse drag).  For a
        discrete change (keyboard) the value has already been applied to
        the node by the time this runs, so the last committed opacity is
        used as the "old" value to keep undo correct.

        Args:
            node: The layer node whose opacity was committed.
        """
        if self._start_opacity is not None:
            old_opacity = self._start_opacity
        elif self._committed_opacity is not None:
            old_opacity = self._committed_opacity
        else:
            old_opacity = node.opacity

        if old_opacity == node.opacity:
            # Nothing actually changed (e.g. slider snapped back) — no
            # need to create a no-op undo entry.
            self._start_opacity = None
            return

        self.layer_opacity_changed.emit(
            self._selected_node_id, node.opacity, old_opacity
        )
        self._start_opacity = None
        self._committed_opacity = node.opacity

    def _sync_opacity_slider(self, node: "MapLayerNode") -> None:
        """Update the slider to reflect the selected node's opacity.

        Args:
            node: The selected layer node.

        """
        self._slider_updating = True
        value = int(node.opacity * 100)
        self._opacity_slider.setValue(value)
        self._opacity_value_label.setText(f"{value} %")
        self._committed_opacity = node.opacity
        self._slider_updating = False

    # ------------------------------------------------------------------
    # Private — UI state
    # ------------------------------------------------------------------

    def _update_button_state(self) -> None:
        """Enable/disable the Delete button based on selection.

        The pinned basemap node is never deletable, so the button stays
        disabled while it is selected.
        """
        from src.app.constants import MAP_LAYER_BASEMAP_NODE_ID

        has_selection = self._selected_node_id is not None
        is_basemap = self._selected_node_id == MAP_LAYER_BASEMAP_NODE_ID
        self.btn_delete.setEnabled(has_selection and not is_basemap)

    # ------------------------------------------------------------------
    # Private — raster editing toolbar
    # ------------------------------------------------------------------

    def _update_raster_toolbar(self, node: "MapLayerNode") -> None:
        """Show or hide the raster editing toolbar.

        Also refreshes the legend and class picker when a raster is selected.

        Args:
            node: The newly selected layer node.
        """
        from src.app.constants import MAP_LAYER_TYPE_RASTER, MAP_LAYER_TYPE_SNAPSHOT

        # Snapshot virtual rows: toolbar is already shown for the raster parent.
        if node.layer_type == MAP_LAYER_TYPE_SNAPSHOT:
            return

        is_raster = node.layer_type == MAP_LAYER_TYPE_RASTER
        self._raster_toolbar.setVisible(is_raster)

        if is_raster:
            self._current_node_id = node.id
            mode = self._raster_mode_by_id.get(node.id, "discrete")
            self._update_sample_tool_availability(mode)
            self._show_mode_badge(mode)
            # Refresh legend and entity picker from stored metadata
            layer_meta = self._raster_meta_by_id.get(node.id)
            name_map = getattr(self, "_raster_name_map_by_id", {}).get(node.id)
            self._refresh_entity_picker(layer_meta, mode, name_map)
            # Notify consumers (e.g. MapWidget) to update the floating legend
            self.raster_layer_selected.emit(node.id, layer_meta)
            # Refresh blend mode combo without triggering signals
            blend_mode = (layer_meta or {}).get("blend_mode", "Normal")
            self._blend_combo.blockSignals(True)
            idx = self._blend_combo.findText(blend_mode)
            if idx >= 0:
                self._blend_combo.setCurrentIndex(idx)
            self._blend_combo.blockSignals(False)
            self._update_snapshot_count_label(layer_meta)
            self._refresh_snapshot_list(node.id, layer_meta)
            # Show preset and query rows
            self._preset_toolbar_row.setVisible(True)
            self._query_row.setVisible(True)
        else:
            old_node_id = self._current_node_id
            self._current_node_id = ""
            self._update_sample_tool_availability("discrete")
            self._raster_mode_label.setVisible(False)
            self._snapshot_count_label.setText("")
            self._clear_snapshot_list(old_node_id)
            self._preset_toolbar_row.setVisible(False)
            self._query_row.setVisible(False)
            # Notify consumers that no raster is selected
            self.raster_layer_selected.emit(None, None)

        # Reset edit toggle when switching layers
        if not is_raster and self._btn_edit_toggle.isChecked():
            self._btn_edit_toggle.setChecked(False)

    def _on_edit_toggled(self, checked: bool) -> None:
        """Handle the Edit / Done toggle button."""
        if checked:
            self._btn_edit_toggle.setText("✎ Editing…")
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
        name_map: Optional[Dict[str, str]] = None,
    ) -> None:
        """Repopulate the *Paint as:* class picker from *layer_meta*.

        The picker is only visible for discrete layers with at least one
        defined class. For continuous and color layers it is hidden.

        Args:
            layer_meta: Raster layer metadata dict, or ``None``.
            mode: ``"discrete"``, ``"continuous"``, or ``"color"``.
            name_map: Optional dict mapping entity/event UUIDs to names.

        """
        from src.gui.widgets.map.raster_mapping import get_discrete_class_choices

        is_discrete = mode == "discrete"
        choices: List[Tuple[str, int]] = []

        if is_discrete and layer_meta:
            choices = get_discrete_class_choices(layer_meta, name_map)

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

    @Slot(int)
    def _on_paint_value_spin_changed(self, value: int) -> None:
        """Sync the class picker combo to reflect the typed paint value.

        When the user manually enters a value that matches a mapped class the
        combo automatically selects that class, giving instant feedback via
        "Paint as: <ClassName>".  When there is no match the combo falls back
        to "— manual —" (index 0) so it never shows a stale class name.

        Args:
            value: New paint value from the spin box.
        """
        self._on_raster_setting_changed()

        if not self._entity_picker_row.isVisible():
            return

        self._entity_picker_combo.blockSignals(True)
        try:
            for i in range(self._entity_picker_combo.count()):
                if self._entity_picker_combo.itemData(i) == value:
                    self._entity_picker_combo.setCurrentIndex(i)
                    return
            # No exact match — reset to the "— manual —" placeholder
            if self._entity_picker_combo.count() > 0:
                self._entity_picker_combo.setCurrentIndex(0)
        finally:
            self._entity_picker_combo.blockSignals(False)

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
                    self._update_sample_tool_availability(mode)
                    self._show_mode_badge(mode)

    def set_raster_layer_metadata(
        self,
        meta_by_id: "Dict[str, Dict[str, Any]]",
        name_map_by_id: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> None:
        """Store full raster layer metadata for legend and class picker.

        Should be called by :class:`MapHandler` after loading raster layers,
        immediately after :meth:`set_raster_mode_metadata`.

        Args:
            meta_by_id: Mapping of ``node_id`` → full raster layer metadata
                dict (the same dicts stored in
                ``maps.attributes["raster_layers"]``).
            name_map_by_id: Optional mapping of ``node_id`` → ``name_map`` dict
                for resolving entity/event names in the class picker.
        """
        self._raster_meta_by_id = meta_by_id
        self._raster_name_map_by_id = name_map_by_id or {}
        # Refresh legend and picker if a raster is already selected
        if self._selected_node_id and self._model is not None:
            node = self._model.find_node_by_id(self._selected_node_id)
            if node is not None:
                from src.app.constants import MAP_LAYER_TYPE_RASTER

                if node.layer_type == MAP_LAYER_TYPE_RASTER:
                    mode = self._raster_mode_by_id.get(
                        self._selected_node_id, "discrete"
                    )
                    self._update_sample_tool_availability(mode)
                    layer_meta = self._raster_meta_by_id.get(self._selected_node_id)
                    name_map = self._raster_name_map_by_id.get(self._selected_node_id)
                    self._refresh_entity_picker(layer_meta, mode, name_map)
                    self._update_snapshot_count_label(layer_meta)
                    self._refresh_snapshot_list(self._selected_node_id, layer_meta)
                    # Notify consumers to refresh the floating legend
                    self.raster_layer_selected.emit(self._selected_node_id, layer_meta)

    def _update_snapshot_count_label(self, layer_meta: Optional[Dict[str, Any]]) -> None:
        """Refresh the snapshot count label for the selected raster layer."""
        snap_count = len((layer_meta or {}).get("snapshots", {}))
        if snap_count:
            self._snapshot_count_label.setText(
                f"{snap_count} snapshot{'s' if snap_count != 1 else ''}"
            )
        else:
            self._snapshot_count_label.setText("")

    def _show_mode_badge(self, mode: str) -> None:
        """Render the mode badge label with the correct text and style.

        Args:
            mode: ``"discrete"``, ``"continuous"``, or ``"color"``.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()

        if mode == "discrete":
            icon = "📊"
            text = "Discrete — categories / classes"
            bg = theme.get("accent_secondary", "#4A90D9")
        elif mode == "color":
            icon = "🖼"
            text = "Color — original RGBA image"
            bg = theme.get("accent_primary", theme.get("primary", "#5C82FF"))
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
            StyleHelper.get_raster_mode_badge_style(bg)
        )
        self._raster_mode_label.setVisible(True)

    def _update_sample_tool_availability(self, mode: str) -> None:
        """Enable or disable the Sample tool for the active raster mode.

        Args:
            mode: Active raster mode string.
        """
        sample_enabled = mode != "color"
        self._btn_sample.setEnabled(sample_enabled)
        self._btn_sample.setToolTip(
            self._sample_tool_enabled_tooltip
            if sample_enabled
            else self._sample_tool_disabled_tooltip
        )
        if not sample_enabled and self._btn_sample.isChecked():
            self._btn_brush.setChecked(True)

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
    def _on_tool_mode_changed(self, checked: bool) -> None:
        """Emit settings changed only when a tool button becomes active."""
        if not checked:
            return
        self.raster_settings_changed.emit()

    @property
    def raster_tool_mode(self) -> str:
        """Currently selected raster tool mode name."""
        if self._btn_fill.isChecked():
            return "fill"
        return (
            "gradient"
            if self._btn_gradient.isChecked()
            else "sample" if self._btn_sample.isChecked() else "brush"
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

    @property
    def raster_gradient_sub_mode(self) -> str:
        """Current gradient sub-mode (lowercase) from the combo box."""
        return self._gradient_sub_combo.currentText().lower()

    def set_raster_layer_notes(self, node_id: str, has_notes: bool) -> None:
        """Update the notes indicator for a raster layer.

        Shows a visual indicator when the layer has non-empty notes.

        Args:
            node_id: Raster layer node ID.
            has_notes: ``True`` if the layer has non-empty notes.
        """
        if node_id == self._current_node_id:
            self._notes_indicator_label.setText("📝" if has_notes else "")

    @Slot()
    def _on_notes_clicked(self) -> None:
        """Emit raster_notes_requested for the currently selected raster layer."""
        if self._current_node_id:
            self.raster_notes_requested.emit(self._current_node_id)

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

    def _clear_snapshot_list(self, node_id: str = "") -> None:
        """Remove virtual snapshot children for the given raster node from the model."""
        target = node_id or self._current_node_id
        if self._model is not None and target:
            self._model.set_virtual_snapshot_children(target, [])

    @staticmethod
    def _format_snapshot_label_with_converter(
        converter: Optional[Any], lore_date: float
    ) -> str:
        """Format a snapshot lore date for display using calendar text when possible."""
        if converter is not None and hasattr(converter, "format_date"):
            try:
                text = converter.format_date(lore_date)
                if isinstance(text, str) and text.strip():
                    return text
            except Exception:
                pass
        return f"Lore day {lore_date:.2f}"

    def _refresh_snapshot_list(
        self, node_id: str, layer_meta: Optional[Dict[str, Any]]
    ) -> None:
        """Inject virtual snapshot nodes as direct children of the raster node."""
        if self._model is None:
            return

        from src.app.constants import MAP_LAYER_TYPE_SNAPSHOT

        snapshots = (layer_meta or {}).get("snapshots", {})
        if not snapshots:
            self._model.set_virtual_snapshot_children(node_id, [])
            return

        parsed: List[Tuple[str, float]] = []
        for key in snapshots:
            try:
                parsed.append((str(key), float(key)))
            except (TypeError, ValueError):
                continue

        parsed.sort(key=lambda s: s[1], reverse=True)

        virtual_nodes: List[MapLayerNode] = []
        for _key, lore_date in parsed:
            label = self._format_snapshot_label_with_converter(
                self._calendar_converter, lore_date
            )
            vnode = MapLayerNode(
                name=label,
                layer_type=MAP_LAYER_TYPE_SNAPSHOT,
                id=f"snap_{node_id}_{_key}",
            )
            vnode.virtual = True
            vnode.attributes = {"lore_date": lore_date, "parent_node_id": node_id}
            virtual_nodes.append(vnode)

        self._model.set_virtual_snapshot_children(node_id, virtual_nodes)

        raster_node = self._model.find_node_by_id(node_id)
        if raster_node is not None:
            raster_index = self._model.index_from_node(raster_node)
            if raster_index.isValid():
                self._tree.setExpanded(raster_index, True)

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
