"""Map Layer Panel Widget.

A themed panel that visualises the hierarchical layer tree and provides
controls for creating/deleting layers, adjusting opacity, renaming,
and reordering via drag-and-drop.  Integrates with the application's
:class:`StyleHelper` / :class:`ThemeManager` for consistent look and feel.
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, cast

from PySide6.QtCore import (
    QEvent,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    QRectF,
    QSize,
    QSortFilterProxyModel,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from src.core.calendar import CalendarConverter
from src.core.map import VECTOR_LAYER_TYPES, MapLayerNode
from src.core.theme_manager import ThemeManager
from src.gui.constants import (
    MAP_LAYER_BASEMAP_NODE_ID,
    MAP_LAYER_TYPE_RASTER,
    MAP_LAYER_TYPE_SNAPSHOT,
)
from src.gui.ui_constants import Spacing
from src.gui.utils.icon_loader import load_icon
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.color_pickers import (
    ColorHistoryService,
    GradientScrubberWidget,
    NumericScrubberSpinBox,
    RecentValuesStrip,
    Swatch,
    SwatchGridWidget,
)
from src.gui.widgets.map.map_data_buffer import (
    ColorMap,
    format_display_value,
)
from src.gui.widgets.map.raster_layer_item import BLEND_MODE_NAMES

if TYPE_CHECKING:
    from src.gui.dialogs.layer_properties_dialog import LayerPropertiesDialog
    from src.gui.dialogs.temporal_validity_dialog import TemporalValidityDialog
    from src.gui.widgets.map.map_layer_model import MapLayerModel

logger = logging.getLogger(__name__)

_MAXIMUM_SWATCH_HOTKEY_INDEX = 9
_CONTINUOUS_DEFAULT_VISIBILITY_THRESHOLD = 256

# Label width used for consistent alignment across raster tool rows.
_LABEL_WIDTH = 52
ModelIndex = QModelIndex | QPersistentModelIndex


class TemporalLayerFilterProxy(QSortFilterProxyModel):
    """Optionally retain only vector features outside the current date."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the optional temporal layer filter."""
        super().__init__(parent)
        self._outside_only = False
        self.setRecursiveFilteringEnabled(True)

    def set_outside_only(self, enabled: bool) -> None:
        """Toggle the temporal-authoring filter."""
        self._outside_only = bool(enabled)
        self.invalidate()

    def filterAcceptsRow(
        self, source_row: int, source_parent: ModelIndex
    ) -> bool:
        """Return whether a layer satisfies the optional temporal filter."""
        if not self._outside_only:
            return True
        source = self.sourceModel()
        if source is None:
            return False
        index = source.index(source_row, 0, source_parent)
        from src.gui.widgets.map.map_layer_model import MapLayerModel

        layer_type = index.data(MapLayerModel.LayerTypeRole)
        state = index.data(MapLayerModel.TemporalValidityRole)
        return bool(
            layer_type in VECTOR_LAYER_TYPES
            and state is not None
            and not state.valid
        )


class TemporalLayerDelegate(QStyledItemDelegate):
    """Paint temporal, visibility, and feature-lock controls in layer rows."""

    def __init__(
        self,
        on_lock_toggled: Callable[[ModelIndex], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialise the delegate with its layer-lock callback."""
        super().__init__(parent)
        self._on_lock_toggled = on_lock_toggled

    @staticmethod
    def _lock_rect(option: QStyleOptionViewItem, index: ModelIndex) -> QRectF:
        from src.gui.widgets.map.map_layer_model import MapLayerModel

        state = index.data(MapLayerModel.TemporalValidityRole)
        manual_hidden = bool(index.data(MapLayerModel.ManualHiddenRole))
        vector_feature = index.data(MapLayerModel.LayerTypeRole) in VECTOR_LAYER_TYPES
        badge_count = int(state is not None and state.applicable and not state.valid)
        badge_count += int(manual_hidden)
        if not vector_feature:
            return QRectF()
        option_view = cast(Any, option)
        return QRectF(
            option_view.rect.right() - (badge_count + 1) * 18,
            option_view.rect.center().y() - 9,
            18,
            18,
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: ModelIndex,
    ) -> None:
        """Paint the layer row with temporal and visibility badges."""
        from src.gui.widgets.map.map_layer_model import MapLayerModel

        state = index.data(MapLayerModel.TemporalValidityRole)
        manual_hidden = bool(index.data(MapLayerModel.ManualHiddenRole))
        outside = bool(state is not None and state.applicable and not state.valid)
        vector_feature = index.data(MapLayerModel.LayerTypeRole) in VECTOR_LAYER_TYPES
        badge_count = int(outside) + int(manual_hidden) + int(vector_feature)

        adjusted = QStyleOptionViewItem(option)
        adjusted_view = cast(Any, adjusted)
        option_view = cast(Any, option)
        if badge_count:
            adjusted_view.rect.adjust(0, 0, -(badge_count * 18 + 4), 0)
        if outside:
            adjusted_view.palette.setColor(
                adjusted_view.palette.ColorRole.Text,
                QColor(ThemeManager().get_theme().get("text_dim", "#888888")),
            )
        super().paint(painter, adjusted, index)

        x = option_view.rect.right() - badge_count * 18
        color = ThemeManager().get_theme().get("text_dim", "#888888")
        for icon_name, show in (
            ("clock.svg", outside),
            ("eye-slash.svg", manual_hidden),
            (
                "lock.svg"
                if bool(index.data(MapLayerModel.LockedRole))
                else "lock-open.svg",
                vector_feature,
            ),
        ):
            if not show:
                continue
            icon = load_icon(f"default_assets/icons/ui_icons/{icon_name}", color)
            icon.paint(painter, x, option_view.rect.center().y() - 7, 14, 14)
            x += 18

    def editorEvent(
        self,
        event: QEvent,
        _model: object,
        option: QStyleOptionViewItem,
        index: ModelIndex,
    ) -> bool:
        """Toggle a vector-feature lock when its inline icon is clicked."""
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False
        position = getattr(event, "pos", lambda: QPoint())()
        if self._lock_rect(option, index).contains(position):
            self._on_lock_toggled(index)
            return True
        return False


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
    layer_properties_changed = Signal(str, dict)
    temporal_jump_requested = Signal(float)
    temporal_filter_changed = Signal(bool)
    temporal_counts_changed = Signal(int, int)

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
    raster_snapshot_edit_requested = Signal(str, float)
    raster_base_edit_requested = Signal(str)
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
        self._proxy_model = TemporalLayerFilterProxy(self)
        self._playhead_time = 0.0
        self._selected_node_id: Optional[str] = None
        self._current_node_id: str = ""
        self._slider_updating = False  # guard against feedback loops
        self._start_opacity: Optional[float] = None  # Opacity at drag start
        self._slider_dragging = False  # True while mouse is on the slider handle
        # Created dynamically by _build_tool_mode_buttons via setattr.
        self._btn_brush: QPushButton
        self._btn_fill: QPushButton
        self._btn_gradient: QPushButton
        self._btn_sample: QPushButton
        # Last committed opacity for the selected node — used as the
        # "old" value when a discrete change (keyboard) is committed.
        self._committed_opacity: Optional[float] = None
        # Full raster layer metadata keyed by node_id (set by MapHandler)
        self._raster_meta_by_id: Dict[str, Dict[str, Any]] = {}
        self._calendar_converter: Optional[CalendarConverter] = None
        self._properties_dialog: Optional["LayerPropertiesDialog"] = None
        self._properties_node_id: Optional[str] = None
        self._temporal_dialog: Optional["TemporalValidityDialog"] = None
        self._temporal_node_id: Optional[str] = None
        # Internal lookup: node_id → mode string (populated by MapHandler)
        self._raster_mode_by_id: dict[str, str] = {}
        self._raster_edit_target_label_by_id: dict[str, str] = {}
        self._selected_snapshot_date_by_node: dict[str, float] = {}
        self._discrete_paint_values_by_id: dict[str, set[int]] = {}
        self._raster_save_failed_nodes: set[str] = set()
        self._active_color_map: Optional[ColorMap] = None
        self._display_value_updating = False

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

        self._title_label = QLabel("Layers")
        header_layout.addWidget(self._title_label)
        self._temporal_count_button = QPushButton("0 in date · 0 outside")
        self._temporal_count_button.setCheckable(True)
        self._temporal_count_button.setToolTip(
            "Show only vector features outside the current playhead date"
        )
        self._temporal_count_button.setEnabled(False)
        self._temporal_count_button.toggled.connect(
            self.set_temporal_filter_enabled
        )
        header_layout.addWidget(self._temporal_count_button)
        header_layout.addStretch()

        _dim = self._theme_token("text_dim")
        _err = self._theme_token("destructive")

        self.btn_new_group = QPushButton()
        self.btn_new_group.setIcon(
            load_icon("default_assets/icons/ui_icons/stack-simple.svg", _dim)
        )
        self.btn_new_group.setIconSize(QSize(16, 16))
        self.btn_new_group.setFixedSize(QSize(28, 28))
        self.btn_new_group.setToolTip("New Group — Create a new layer group")
        self.btn_new_group.setStyleSheet(StyleHelper.get_icon_button_style())
        self.btn_new_group.clicked.connect(self._on_new_group)
        header_layout.addWidget(self.btn_new_group)

        self.btn_new_raster = QPushButton()
        self.btn_new_raster.setIcon(
            load_icon("default_assets/icons/ui_icons/paint-brush-broad.svg", _dim)
        )
        self.btn_new_raster.setIconSize(QSize(16, 16))
        self.btn_new_raster.setFixedSize(QSize(28, 28))
        self.btn_new_raster.setToolTip("New Raster — Create a new raster / heatmap layer")
        self.btn_new_raster.setStyleSheet(StyleHelper.get_icon_button_style())
        self.btn_new_raster.clicked.connect(self._on_new_raster)
        header_layout.addWidget(self.btn_new_raster)

        header_layout.addSpacing(8)

        self.btn_delete = QPushButton()
        self.btn_delete.setIcon(
            load_icon("default_assets/icons/ui_icons/trash.svg", _err)
        )
        self.btn_delete.setIconSize(QSize(16, 16))
        self.btn_delete.setFixedSize(QSize(28, 28))
        self.btn_delete.setToolTip("Delete — Delete the selected layer or feature")
        self.btn_delete.setStyleSheet(StyleHelper.get_ghost_destructive_button_style())
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._on_delete)
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
        self._tree.setItemDelegate(TemporalLayerDelegate(self._toggle_lock_at_index, self._tree))
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

        self._raster_name_label = QLabel("Raster")
        self._raster_name_label.setObjectName("RasterEditName")
        rt.addWidget(self._raster_name_label)

        # Mode badge — shows "Discrete" or "Continuous"
        self._raster_mode_label = QLabel()
        self._raster_mode_label.setObjectName("RasterModeBadge")
        self._raster_mode_label.setVisible(False)
        rt.addWidget(self._raster_mode_label)

        self._edit_target_label = QLabel("Target: Base")
        self._edit_target_label.setObjectName("RasterEditTarget")
        self._edit_target_label.setVisible(False)
        rt.addWidget(self._edit_target_label)
        self._paint_guidance_label = QLabel("")
        self._paint_guidance_label.setObjectName("RasterPaintGuidance")
        self._paint_guidance_label.setWordWrap(True)
        self._paint_guidance_label.setVisible(False)
        rt.addWidget(self._paint_guidance_label)
        self._save_status_label = QLabel("Saved")
        self._save_status_label.setObjectName("RasterSaveStatus")
        self._save_status_label.setVisible(False)
        rt.addWidget(self._save_status_label)

        self._build_edit_action_row(rt)
        self._build_tool_mode_buttons(rt)

        rt.addWidget(self._make_section_separator("PAINT"))
        self._build_paint_settings(rt)

        rt.addWidget(self._make_section_separator("RASTER STATES"))
        self._build_snapshot_row(rt)

        rt.addWidget(self._make_section_separator("LAYER"))
        self._build_layer_settings(rt)

        parent_layout.addWidget(self._raster_toolbar)

    def _build_tool_mode_buttons(self, rt: QVBoxLayout) -> None:
        """Build the mutually exclusive raster tool mode buttons.

        Args:
            rt: Raster toolbar layout to append into.
        """
        tool_row = QHBoxLayout()
        tool_row.setSpacing(2)

        _dim = self._theme_token("text_dim")
        _icon_style = StyleHelper.get_icon_raster_tool_button_style()
        tool_defs: list[tuple[str, str, bool, str, str]] = [
            (
                "_btn_brush", "Brush", True,
                "Paint individual pixels with the selected value",
                "default_assets/icons/ui_icons/paint-brush.svg",
            ),
            (
                "_btn_fill", "Fill", False,
                "Flood-fill a contiguous region with the selected value",
                "default_assets/icons/ui_icons/paint-bucket.svg",
            ),
            (
                "_btn_gradient", "Gradient", False,
                "Paint a smooth gradient from center to edge of brush",
                "default_assets/icons/ui_icons/gradient.svg",
            ),
            (
                "_btn_sample", "Sample", False,
                "Sample the value under the cursor (eye-dropper)",
                "default_assets/icons/ui_icons/eyedropper.svg",
            ),
        ]
        for attr, label, checked, tooltip, icon_path in tool_defs:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(checked)
            btn.setAutoExclusive(True)
            btn.setToolTip(f"{label} — {tooltip}")
            btn.setIcon(load_icon(icon_path, _dim))
            btn.setIconSize(QSize(16, 16))
            btn.setAccessibleName(label)
            btn.setStyleSheet(_icon_style)
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
        """Build paint parameter controls (size, value, entity picker, hardness, gradient).

        Args:
            rt: Raster toolbar layout to append into.
        """
        self._brush_size_spin, self._brush_size_slider = (
            self._make_slider_scrubber_row(
                rt,
                "Size:",
                1,
                128,
                8,
                "Brush radius in pixels (1–128)",
                self._on_brush_size_slider_changed,
                self._on_brush_size_spin_changed,
            )
        )
        self._brush_size_row = cast(QWidget, self._brush_size_spin.parentWidget())

        self._build_paint_value_selector(rt)
        self._build_entity_picker(rt)
        self._build_recent_values_strip(rt)
        self._build_mode_specific_paint_controls(rt)

        self._falloff_slider, self._falloff_label = self._make_labeled_slider(
            rt,
            "Hardness:",
            0,
            100,
            100,
            "Brush hardness (0=soft edge, 100=hard edge)",
            self._on_falloff_changed,
            icon_path="default_assets/icons/ui_icons/drop.svg",
        )
        self._hardness_row = cast(QWidget, self._falloff_slider.parentWidget())

        self._brush_opacity_slider, self._brush_opacity_label = self._make_labeled_slider(
            rt,
            "Opacity:",
            0,
            100,
            100,
            "Brush opacity (100=full replacement, 0=no change)",
            self._on_brush_opacity_changed,
            icon_path="default_assets/icons/ui_icons/circle-half.svg",
        )
        self._brush_opacity_row = cast(
            QWidget, self._brush_opacity_slider.parentWidget()
        )

        self._build_falloff_curve_combo(rt)
        self._build_gradient_sub_combo(rt)

    def _build_mode_specific_paint_controls(self, rt: QVBoxLayout) -> None:
        """Build target, tolerance, colour, and explicit endpoint controls."""
        self._advanced_paint_toggle = QCheckBox("Advanced")
        self._advanced_paint_toggle.setToolTip(
            "Show raw raster values for specialist workflows"
        )
        self._advanced_paint_toggle.toggled.connect(
            self._on_advanced_paint_toggled
        )
        rt.addWidget(self._advanced_paint_toggle)

        self._display_value_row = QWidget()
        display_layout = QHBoxLayout(self._display_value_row)
        display_layout.setContentsMargins(0, 0, 0, 0)
        display_layout.addWidget(QLabel("Target:"))
        self._display_value_spin = QDoubleSpinBox()
        self._display_value_spin.setDecimals(3)
        self._display_value_spin.setRange(0.0, 65535.0)
        self._display_value_spin.valueChanged.connect(
            self._on_display_value_changed
        )
        display_layout.addWidget(self._display_value_spin, 1)
        self._display_unit_label = QLabel("raw")
        display_layout.addWidget(self._display_unit_label)
        rt.addWidget(self._display_value_row)

        self._fill_tolerance_row = QWidget()
        tolerance_layout = QHBoxLayout(self._fill_tolerance_row)
        tolerance_layout.setContentsMargins(0, 0, 0, 0)
        tolerance_layout.addWidget(QLabel("Tolerance:"))
        self._fill_tolerance_slider = QSlider(Qt.Orientation.Horizontal)
        self._fill_tolerance_slider.setRange(0, 100)
        self._fill_tolerance_slider.valueChanged.connect(
            lambda _: self._on_raster_setting_changed()
        )
        tolerance_layout.addWidget(self._fill_tolerance_slider, 1)
        self._fill_tolerance_label = QLabel("0%")
        self._fill_tolerance_slider.valueChanged.connect(
            lambda value: self._fill_tolerance_label.setText(f"{value}%")
        )
        tolerance_layout.addWidget(self._fill_tolerance_label)
        rt.addWidget(self._fill_tolerance_row)

        self._rgba_color_row = QWidget()
        color_layout = QHBoxLayout(self._rgba_color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(QLabel("Colour:"))
        self._rgba_color = QColor(255, 255, 255, 255)
        self._rgba_color_button = QPushButton("#FFFFFFFF")
        self._rgba_color_button.setAccessibleName("Paint colour")
        self._rgba_color_button.clicked.connect(self._choose_rgba_color)
        color_layout.addWidget(self._rgba_color_button, 1)
        color_layout.addWidget(QLabel("Alpha:"))
        self._rgba_alpha_spin = QSpinBox()
        self._rgba_alpha_spin.setRange(0, 255)
        self._rgba_alpha_spin.setValue(255)
        self._rgba_alpha_spin.valueChanged.connect(self._on_rgba_alpha_changed)
        color_layout.addWidget(self._rgba_alpha_spin)
        rt.addWidget(self._rgba_color_row)

        self._gradient_endpoints_row = QWidget()
        endpoint_layout = QHBoxLayout(self._gradient_endpoints_row)
        endpoint_layout.setContentsMargins(0, 0, 0, 0)
        endpoint_layout.addWidget(QLabel("From:"))
        self._gradient_from_spin = QSpinBox()
        self._gradient_from_spin.setRange(0, 65535)
        self._gradient_from_spin.valueChanged.connect(
            lambda _: self._on_raster_setting_changed()
        )
        endpoint_layout.addWidget(self._gradient_from_spin)
        endpoint_layout.addWidget(QLabel("To:"))
        self._gradient_to_spin = QSpinBox()
        self._gradient_to_spin.setRange(0, 65535)
        self._gradient_to_spin.setValue(1)
        self._gradient_to_spin.valueChanged.connect(
            lambda _: self._on_raster_setting_changed()
        )
        endpoint_layout.addWidget(self._gradient_to_spin)
        rt.addWidget(self._gradient_endpoints_row)

        self._rgba_gradient_row = QWidget()
        rgba_gradient_layout = QHBoxLayout(self._rgba_gradient_row)
        rgba_gradient_layout.setContentsMargins(0, 0, 0, 0)
        self._rgba_gradient_from = QColor(0, 0, 0, 0)
        self._rgba_gradient_to = QColor(255, 255, 255, 255)
        self._rgba_gradient_from_button = QPushButton("From #00000000")
        self._rgba_gradient_to_button = QPushButton("To #FFFFFFFF")
        self._rgba_gradient_from_button.clicked.connect(
            lambda: self._choose_gradient_color(True)
        )
        self._rgba_gradient_to_button.clicked.connect(
            lambda: self._choose_gradient_color(False)
        )
        rgba_gradient_layout.addWidget(self._rgba_gradient_from_button)
        rgba_gradient_layout.addWidget(self._rgba_gradient_to_button)
        rt.addWidget(self._rgba_gradient_row)

    def _build_paint_value_selector(self, rt: QVBoxLayout) -> None:
        """Build the mode-aware paint-value selector.

        Contents:
        - Stacked area that shows either a :class:`SwatchGridWidget`
          (discrete) or a :class:`GradientScrubberWidget` (continuous)
        - A numeric scrubber spin box for precise entry (always visible)
        - An implicit sync helper (:meth:`_set_paint_value`)

        Args:
            rt: Raster toolbar layout to append into.
        """
        # Value scrubber spin (always visible, compact — source of truth)
        self._raw_value_row = QWidget()
        scrub_row = QHBoxLayout(self._raw_value_row)
        scrub_row.setContentsMargins(0, 0, 0, 0)
        scrub_row.setSpacing(Spacing.COMPACT)
        lbl = QLabel("Value:")
        lbl.setFixedWidth(_LABEL_WIDTH)
        scrub_row.addWidget(lbl)

        self._paint_value_spin = NumericScrubberSpinBox()
        self._paint_value_spin.setRange(0, 65535)
        self._paint_value_spin.setValue(1)
        self._paint_value_spin.setFixedWidth(96)
        self._paint_value_spin.setToolTip(
            "Raw raster value to paint (0–65535) — drag to scrub, double-click to type"
        )
        self._paint_value_spin.valueChanged.connect(
            self._on_paint_value_spin_changed
        )
        scrub_row.addWidget(self._paint_value_spin)

        self._paint_value_display_label = QLabel("")
        dim_color = ThemeManager().get_theme().get("text_dim", "#888888")
        self._paint_value_display_label.setStyleSheet(
            f"color: {dim_color}; font-style: italic;"
        )
        scrub_row.addWidget(self._paint_value_display_label, 1)
        rt.addWidget(self._raw_value_row)

        # Mode-dependent picker: swatch grid (discrete) vs gradient scrubber (continuous)
        self._paint_value_stack = QStackedWidget()
        self._swatch_grid = SwatchGridWidget()
        self._swatch_grid.swatch_clicked.connect(self._on_swatch_clicked)
        self._paint_value_stack.addWidget(self._swatch_grid)

        self._gradient_scrubber = GradientScrubberWidget()
        self._gradient_scrubber.value_changed.connect(
            self._on_gradient_scrubber_changed
        )
        self._gradient_scrubber.value_committed.connect(
            self._on_gradient_scrubber_committed
        )
        self._paint_value_stack.addWidget(self._gradient_scrubber)

        # Empty page for color / no-raster modes
        empty = QWidget()
        self._paint_value_stack.addWidget(empty)

        rt.addWidget(self._paint_value_stack)

    def _build_recent_values_strip(self, rt: QVBoxLayout) -> None:
        """Build the recent-paint-values strip below the paint selector.

        Args:
            rt: Raster toolbar layout to append into.
        """
        self._recent_paint_values = RecentValuesStrip(
            "raster.paint_value", is_color=False
        )
        self._recent_paint_values.set_label_formatter(
            self._format_value_for_display
        )
        self._recent_paint_values.value_chosen.connect(self._on_recent_value_chosen)
        rt.addWidget(self._recent_paint_values)

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

    def _build_falloff_curve_combo(self, rt: QVBoxLayout) -> None:
        """Build the falloff curve combo row (Linear / Cosine / Gaussian).

        Args:
            rt: Raster toolbar layout to append into.
        """
        self._falloff_curve_row = QWidget()
        curve_row = QHBoxLayout(self._falloff_curve_row)
        curve_row.setContentsMargins(0, 0, 0, 0)
        curve_row.setSpacing(Spacing.COMPACT)
        curve_lbl = QLabel("Curve:")
        curve_lbl.setFixedWidth(_LABEL_WIDTH)
        curve_lbl.setToolTip("Shape of the brush feather ramp")
        curve_row.addWidget(curve_lbl)
        self._falloff_curve_combo = QComboBox()
        self._falloff_curve_combo.addItems(["Cosine", "Linear", "Gaussian"])
        self._falloff_curve_combo.setToolTip(
            "Cosine: smooth S-curve (default)  |  "
            "Linear: uniform ramp  |  "
            "Gaussian: tight centre, rapid falloff"
        )
        self._falloff_curve_combo.currentTextChanged.connect(
            lambda _: self._on_raster_setting_changed()
        )
        curve_row.addWidget(self._falloff_curve_combo, 1)
        rt.addWidget(self._falloff_curve_row)

    def _build_gradient_sub_combo(self, rt: QVBoxLayout) -> None:
        """Build the gradient sub-mode combo row.

        Args:
            rt: Raster toolbar layout to append into.
        """
        self._gradient_sub_row = QWidget()
        gradient_row = QHBoxLayout(self._gradient_sub_row)
        gradient_row.setContentsMargins(0, 0, 0, 0)
        gradient_row.setSpacing(Spacing.COMPACT)
        grad_lbl = QLabel()
        grad_lbl.setPixmap(
            load_icon(
                "default_assets/icons/ui_icons/gradient.svg",
                self._theme_token("text_dim"),
            ).pixmap(QSize(16, 16))
        )
        grad_lbl.setFixedWidth(22)
        grad_lbl.setToolTip("Gradient style")
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
        rt.addWidget(self._gradient_sub_row)

    def _build_edit_action_row(self, rt: QVBoxLayout) -> None:
        """Build the Edit / Palette / Stats action row (appended to the PAINT section).

        Args:
            rt: Raster toolbar layout to append into.
        """
        _dim = self._theme_token("text_dim")
        action_row = QHBoxLayout()
        action_row.setSpacing(Spacing.COMPACT)
        self._btn_edit_toggle = QPushButton("Paint")
        self._btn_edit_toggle.setCheckable(True)
        self._btn_edit_toggle.setEnabled(False)
        self._btn_edit_toggle.setToolTip("Enter/exit raster edit mode — changes are applied to the active layer")
        self._btn_edit_toggle.toggled.connect(self._on_edit_toggled)
        action_row.addWidget(self._btn_edit_toggle)

        self._btn_palette = QPushButton("Palette")
        self._btn_palette.setIcon(
            load_icon("default_assets/icons/ui_icons/palette.svg", _dim)
        )
        self._btn_palette.setIconSize(QSize(16, 16))
        self._btn_palette.setAccessibleName("Palette")
        self._btn_palette.setToolTip("Palette — Open the colour map / class palette editor")
        self._btn_palette.setStyleSheet(StyleHelper.get_icon_button_style())
        self._btn_palette.clicked.connect(self._on_palette_clicked)
        action_row.addWidget(self._btn_palette)

        self._btn_stats = QPushButton("Analyze")
        self._btn_stats.setIcon(
            load_icon("default_assets/icons/ui_icons/chart-bar.svg", _dim)
        )
        self._btn_stats.setIconSize(QSize(16, 16))
        self._btn_stats.setAccessibleName("Analyze")
        self._btn_stats.setToolTip("Stats — Show coverage statistics for this raster layer")
        self._btn_stats.setStyleSheet(StyleHelper.get_icon_button_style())
        self._btn_stats.clicked.connect(self._on_stats_clicked)
        action_row.addWidget(self._btn_stats)
        action_row.addStretch()
        rt.addLayout(action_row)

    def _build_snapshot_row(self, rt: QVBoxLayout) -> None:
        """Build the snapshot button and count label row.

        Args:
            rt: Raster toolbar layout to append into.
        """
        _dim = self._theme_token("text_dim")
        snapshot_row = QHBoxLayout()
        snapshot_row.setSpacing(Spacing.COMPACT)
        self._btn_snapshot = QPushButton("Create state")
        self._btn_snapshot.setIcon(
            load_icon("default_assets/icons/ui_icons/camera.svg", _dim)
        )
        self._btn_snapshot.setIconSize(QSize(16, 16))
        self._btn_snapshot.setAccessibleName("Create state")
        self._btn_snapshot.setToolTip(
            "Create Editable State — branch the displayed raster at the "
            "current timeline date"
        )
        self._btn_snapshot.setStyleSheet(StyleHelper.get_icon_button_style())
        self._btn_snapshot.clicked.connect(self._on_snapshot_clicked)
        snapshot_row.addWidget(self._btn_snapshot)
        self._btn_edit_base = QPushButton("Edit base")
        self._btn_edit_base.setToolTip(
            "Explicitly display and edit the undated base raster"
        )
        self._btn_edit_base.clicked.connect(self._on_edit_base_clicked)
        snapshot_row.addWidget(self._btn_edit_base)
        self._btn_edit_state = QPushButton("Edit this state")
        self._btn_edit_state.setAccessibleName("Edit this raster state")
        self._btn_edit_state.setToolTip(
            "Select the dated raster state shown in the layer tree as the edit target"
        )
        self._btn_edit_state.clicked.connect(self._on_edit_state_clicked)
        self._btn_edit_state.setVisible(False)
        snapshot_row.addWidget(self._btn_edit_state)
        self._snapshot_count_label = QLabel("")
        self._snapshot_count_label.setToolTip(
            "Number of dated raster states for this layer"
        )
        snapshot_row.addWidget(self._snapshot_count_label)
        snapshot_row.addStretch()
        rt.addLayout(snapshot_row)

    def _build_layer_settings(self, rt: QVBoxLayout) -> None:
        """Build layer-level controls (blend, notes, presets, query).

        Args:
            rt: Raster toolbar layout to append into.
        """
        _dim = self._theme_token("text_dim")
        # Blend mode
        blend_row = QHBoxLayout()
        blend_row.setSpacing(Spacing.COMPACT)
        _blend_lbl = QLabel()
        _blend_lbl.setPixmap(
            load_icon("default_assets/icons/ui_icons/sliders.svg", _dim).pixmap(
                QSize(16, 16)
            )
        )
        _blend_lbl.setFixedWidth(22)
        _blend_lbl.setToolTip("Blend mode")
        blend_row.addWidget(_blend_lbl)
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
        self._btn_notes = QPushButton()
        self._btn_notes.setIcon(
            load_icon("default_assets/icons/ui_icons/note-pencil.svg", _dim)
        )
        self._btn_notes.setIconSize(QSize(16, 16))
        self._btn_notes.setFixedSize(QSize(28, 28))
        self._btn_notes.setToolTip("Notes — Add or edit text notes for this raster layer")
        self._btn_notes.setStyleSheet(StyleHelper.get_icon_button_style())
        self._btn_notes.clicked.connect(self._on_notes_clicked)
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
        self._btn_query = QPushButton()
        self._btn_query.setIcon(
            load_icon("default_assets/icons/ui_icons/funnel.svg", _dim)
        )
        self._btn_query.setIconSize(QSize(16, 16))
        self._btn_query.setFixedSize(QSize(28, 28))
        self._btn_query.setToolTip("Query — Build a cross-layer spatial query")
        self._btn_query.setStyleSheet(StyleHelper.get_icon_button_style())
        self._btn_query.clicked.connect(lambda: self.raster_query_requested.emit())
        query_layout.addWidget(self._btn_query)

        self._btn_clear_query = QPushButton()
        self._btn_clear_query.setIcon(
            load_icon("default_assets/icons/ui_icons/funnel-x.svg", _dim)
        )
        self._btn_clear_query.setIconSize(QSize(16, 16))
        self._btn_clear_query.setFixedSize(QSize(28, 28))
        self._btn_clear_query.setToolTip("Clear Query — Remove the spatial query overlay")
        self._btn_clear_query.setStyleSheet(StyleHelper.get_icon_button_style())
        self._btn_clear_query.clicked.connect(lambda: self.raster_query_cleared.emit())
        self._btn_clear_query.setVisible(False)
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
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
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
        parent_layout.addWidget(row_widget)
        return spin

    @staticmethod
    def _make_slider_scrubber_row(
        parent_layout: QVBoxLayout,
        label: str,
        min_val: int,
        max_val: int,
        default: int,
        tooltip: str,
        on_slider_changed: Any,
        on_spin_changed: Any,
    ) -> Tuple[NumericScrubberSpinBox, QSlider]:
        """Create a slider + numeric scrubber spin box row.

        The slider gives a visual overview; the scrubber spin provides
        precision (press-drag or keyboard entry).

        Args:
            parent_layout: Layout to add the row into.
            label: Row label text.
            min_val: Minimum value.
            max_val: Maximum value.
            default: Initial value.
            tooltip: Shared tooltip text.
            on_slider_changed: Slot for slider ``valueChanged``.
            on_spin_changed: Slot for spin ``valueChanged``.

        Returns:
            Tuple of ``(spin, slider)``.
        """
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Spacing.COMPACT)
        lbl = QLabel(label)
        lbl.setFixedWidth(_LABEL_WIDTH)
        row.addWidget(lbl)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        slider.setToolTip(tooltip)
        slider.valueChanged.connect(on_slider_changed)
        row.addWidget(slider, 1)

        spin = NumericScrubberSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setFixedWidth(64)
        spin.setToolTip(tooltip + " — drag to scrub, double-click to type")
        spin.valueChanged.connect(on_spin_changed)
        row.addWidget(spin)

        parent_layout.addWidget(row_widget)
        return spin, slider

    @staticmethod
    def _make_labeled_slider(
        parent_layout: QVBoxLayout,
        label: str,
        min_val: int,
        max_val: int,
        default: int,
        tooltip: str,
        on_changed: Any,
        *,
        icon_path: str = "",
    ) -> Tuple[QSlider, QLabel]:
        """Create a labeled slider row with a value readout label.

        Args:
            parent_layout: Layout to add the row into.
            label: Row label text (shown as tooltip when *icon_path* is used).
            min_val: Minimum slider value.
            max_val: Maximum slider value.
            default: Initial slider value.
            tooltip: Slider tooltip text.
            on_changed: Slot connected to ``valueChanged``.
            icon_path: Optional path to a Phosphor SVG icon to show in place of
                the text label.  Relative to the project root, e.g.
                ``"default_assets/icons/ui_icons/drop.svg"``.

        Returns:
            A ``(slider, value_label)`` tuple.
        """
        from src.core.theme_manager import ThemeManager

        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Spacing.COMPACT)
        if icon_path:
            lbl = QLabel()
            lbl.setPixmap(
                load_icon(
                    icon_path,
                    ThemeManager().get_theme().get("text_dim", "#888888"),
                ).pixmap(QSize(16, 16))
            )
            lbl.setFixedWidth(22)
            lbl.setToolTip(label)
        else:
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
        parent_layout.addWidget(row_widget)
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

    def source_index(self, index: ModelIndex) -> QModelIndex:
        """Map a tree/proxy index to the canonical layer-model index."""
        if index.model() is self._model:
            return cast(QModelIndex, index)
        return self._proxy_model.mapToSource(index)

    def set_model(self, model: "MapLayerModel") -> None:
        """Attach a :class:`MapLayerModel` to the tree view.

        Args:
            model: The layer model to display.

        """
        had_model = self._model is not None
        expanded_node_ids = self._expanded_node_ids()
        if self._model is not None:
            try:
                self._model.layer_tree_changed.disconnect(
                    self._reconcile_selection_with_model
                )
                self._model.dataChanged.disconnect(self._on_model_data_changed)
                self._model.temporal_state_changed.disconnect(
                    self._on_temporal_state_changed
                )
            except (RuntimeError, TypeError):
                pass
        self._model = model
        self._proxy_model.setSourceModel(model)
        self._tree.setModel(self._proxy_model)
        model.layer_tree_changed.connect(self._reconcile_selection_with_model)
        model.dataChanged.connect(self._on_model_data_changed)
        model.temporal_state_changed.connect(self._on_temporal_state_changed)
        if self._calendar_converter is not None:
            model.set_date_formatter(self._calendar_converter.format_date)
        model.set_current_time(self._playhead_time)
        if had_model:
            self._restore_expanded_nodes(expanded_node_ids)
        else:
            self._tree.expandAll()
        self._reconcile_selection_with_model()
        self._update_temporal_count()

    def _expanded_node_ids(self) -> set[str]:
        """Return expanded group IDs before replacing the source model."""
        model = self._model
        if model is None:
            return set()
        expanded: set[str] = set()

        def visit(node: MapLayerNode) -> None:
            index = model.index_from_node(node)
            if index.isValid():
                proxy_index = self._proxy_model.mapFromSource(index)
                if proxy_index.isValid() and self._tree.isExpanded(proxy_index):
                    expanded.add(node.id)
            for child in node.children:
                visit(child)

        visit(model.root)
        return expanded

    def _restore_expanded_nodes(self, node_ids: set[str]) -> None:
        """Restore expansion state after installing a fresh layer model."""
        if self._model is None:
            return
        for node_id in node_ids:
            node = self._model.find_node_by_id(node_id)
            if node is None:
                continue
            index = self._proxy_model.mapFromSource(
                self._model.index_from_node(node)
            )
            if index.isValid():
                self._tree.setExpanded(index, True)

    def _reconcile_selection_with_model(self) -> None:
        """Clear controls that refer to a node removed from the layer model."""
        if self._model is None:
            return

        if (
            self._properties_node_id
            and self._model.find_node_by_id(self._properties_node_id) is None
        ):
            self._close_properties_dialog()
        if (
            self._temporal_node_id
            and self._model.find_node_by_id(self._temporal_node_id) is None
        ):
            self._close_temporal_dialog()

        selected = (
            self._model.find_node_by_id(self._selected_node_id)
            if self._selected_node_id
            else None
        )
        if selected is not None:
            index = self._model.index_from_node(selected)
            if index.isValid():
                self._tree.setCurrentIndex(self._proxy_model.mapFromSource(index))
            self._update_button_state()
            return

        self._selected_node_id = None
        self._tree.clearSelection()
        self._tree.setCurrentIndex(QModelIndex())
        self._update_button_state()

        if (
            self._current_node_id
            and self._model.find_node_by_id(self._current_node_id) is None
        ):
            self._update_raster_toolbar(self._model.root)

    def set_calendar_converter(self, converter: CalendarConverter) -> None:
        """Set the calendar converter used for snapshot date labels.

        Args:
            converter: Object exposing ``format_date(float) -> str``.
        """
        self._calendar_converter = converter
        if self._model is not None:
            self._model.set_date_formatter(converter.format_date)
        if self._selected_node_id and self._model is not None:
            node = self._model.find_node_by_id(self._selected_node_id)
            if node is not None:
                from src.gui.constants import MAP_LAYER_TYPE_RASTER

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
            proxy_index = self._proxy_model.mapFromSource(index)
            if not proxy_index.isValid() and self._temporal_count_button.isChecked():
                self.set_temporal_filter_enabled(False)
                proxy_index = self._proxy_model.mapFromSource(index)
            self._tree.setCurrentIndex(proxy_index)
            self._tree.scrollTo(proxy_index)
            self._selected_node_id = node_id
            self._sync_opacity_slider(node)
            self._update_button_state()

    def set_playhead_time(self, time: float) -> None:
        """Refresh temporal tree awareness for the active playhead."""
        self._playhead_time = float(time)
        if self._temporal_dialog is not None:
            self._temporal_dialog.set_playhead_time(self._playhead_time)
        if self._model is not None:
            self._model.set_current_time(self._playhead_time)
        self._proxy_model.invalidate()
        self._update_temporal_count()

    @Slot(bool)
    def set_temporal_filter_enabled(self, enabled: bool) -> None:
        """Show only vector features outside the current date when enabled."""
        enabled = bool(enabled)
        self._proxy_model.set_outside_only(enabled)
        self._temporal_count_button.blockSignals(True)
        self._temporal_count_button.setChecked(enabled)
        self._temporal_count_button.blockSignals(False)
        self._tree.expandAll()
        self.temporal_filter_changed.emit(enabled)

    @Slot()
    def _on_model_data_changed(self, *_args: object) -> None:
        self._proxy_model.invalidate()
        self._update_temporal_count()

    @Slot()
    def _on_temporal_state_changed(self) -> None:
        self._proxy_model.invalidate()
        self._tree.viewport().update()
        self._update_temporal_count()

    def _update_temporal_count(self) -> None:
        """Refresh the vector-feature date summary in the panel header."""
        if self._model is None:
            self._temporal_count_button.setText("0 in date · 0 outside")
            self.temporal_counts_changed.emit(0, 0)
            return
        valid, outside = self._model.vector_temporal_counts()
        self.temporal_counts_changed.emit(valid, outside)
        self._temporal_count_button.setText(
            f"{valid} in date · {outside} outside"
        )
        self._temporal_count_button.setEnabled(outside > 0)
        if outside == 0 and self._temporal_count_button.isChecked():
            self.set_temporal_filter_enabled(False)

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
        self._brush_opacity_slider.setStyleSheet(StyleHelper.get_slider_style())
        dim_style = f"color: {self._theme_token('text_dim')}; font-size: 9pt;"
        self._opacity_label.setStyleSheet(dim_style)
        self._opacity_value_label.setStyleSheet(
            f"color: {self._theme_token('text_main')}; font-size: 9pt;"
        )
        self._apply_tree_style()

        # Raster tool icon buttons — prominent checked state
        icon_tool_style = StyleHelper.get_icon_raster_tool_button_style()
        for btn in (
            self._btn_brush,
            self._btn_fill,
            self._btn_gradient,
            self._btn_sample,
        ):
            btn.setStyleSheet(icon_tool_style)
        # Edit toggle is a text button; keep the text-oriented style
        self._btn_edit_toggle.setStyleSheet(StyleHelper.get_raster_tool_button_style())

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
        """Request deletion while retaining selection until success is confirmed."""
        if self._selected_node_id:
            self.delete_layer_requested.emit(self._selected_node_id)

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
        source_index = self.source_index(index)
        node = self._model.node_from_index(source_index)

        if node.layer_type == MAP_LAYER_TYPE_SNAPSHOT:
            # Remember the dated state so its edit action remains visible after
            # the tree selection returns to the parent raster.
            lore_date = float(node.attributes.get("lore_date", 0.0))
            parent_id = str(node.attributes.get("parent_node_id", ""))
            self._selected_snapshot_date_by_node[parent_id] = lore_date
            self._refresh_edit_state_action(parent_id)
            self.raster_snapshot_selected.emit(parent_id, lore_date)
            # Restore tree selection to the parent raster.
            if self._selected_node_id:
                parent_node = self._model.find_node_by_id(self._selected_node_id)
                if parent_node is not None:
                    parent_idx = self._model.index_from_node(parent_node)
                    if parent_idx.isValid():
                        self._tree.setCurrentIndex(
                            self._proxy_model.mapFromSource(parent_idx)
                        )
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
        source_index = self.source_index(index)
        node = self._model.node_from_index(source_index)
        name, ok = QInputDialog.getText(
            self, "Rename Layer", "New name:", text=node.name
        )
        if ok and name.strip():
            self.layer_renamed.emit(node.id, name.strip())

    def _toggle_lock_at_index(self, index: ModelIndex) -> None:
        """Toggle a vector feature's persistent canvas-interaction lock."""
        if self._model is None or not index.isValid():
            return
        node = self._model.node_from_index(self.source_index(index))
        self._model.set_node_locked(node, not node.locked)

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
            source_index = self.source_index(index)
            node = self._model.node_from_index(source_index)

            from src.gui.constants import MAP_LAYER_TYPE_SNAPSHOT

            if node.layer_type == MAP_LAYER_TYPE_SNAPSHOT:
                lore_date = float(node.attributes.get("lore_date", 0.0))
                parent_id = str(node.attributes.get("parent_node_id", ""))
                action_jump = menu.addAction("↰ Jump Playhead Here")
                action_jump.triggered.connect(
                    lambda _=False, pid=parent_id, ld=lore_date: (
                        self.raster_snapshot_selected.emit(pid, ld)
                    )
                )
                action_edit = menu.addAction("Edit This State")
                action_edit.triggered.connect(
                    lambda _=False, pid=parent_id, ld=lore_date: (
                        self.raster_snapshot_edit_requested.emit(pid, ld)
                    )
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

            if node.layer_type in VECTOR_LAYER_TYPES and node.locked:
                action_unlock = menu.addAction("Unlock")
                action_unlock.triggered.connect(
                    lambda _=False, source=source_index: self._toggle_lock_at_index(
                        source
                    )
                )
                menu.exec(self._tree.viewport().mapToGlobal(pos))
                return

            from src.gui.constants import MAP_LAYER_BASEMAP_NODE_ID

            is_basemap = node.id == MAP_LAYER_BASEMAP_NODE_ID

            # Toggle visibility
            vis_text = "Hide" if node.visible else "Show"
            action_toggle = menu.addAction(f"{vis_text} Layer")
            action_toggle.triggered.connect(lambda: self._toggle_visibility(node))

            # Rename (not allowed for the pinned basemap node)
            if not is_basemap:
                if node.layer_type in VECTOR_LAYER_TYPES:
                    lock_text = "Unlock Feature" if node.locked else "Lock Feature"
                    action_lock = menu.addAction(lock_text)
                    action_lock.triggered.connect(
                        lambda _=False, source=source_index: self._toggle_lock_at_index(
                            source
                        )
                    )
                action_rename = menu.addAction("Rename…")
                action_rename.triggered.connect(
                    lambda: self._on_item_double_clicked(index)
                )
                action_properties = menu.addAction("Properties…")
                action_properties.triggered.connect(
                    lambda: self._edit_properties(node)
                )

                if node.layer_type in VECTOR_LAYER_TYPES or node.layer_type == "group":
                    temporal_action = menu.addAction("Temporal Validity…")
                    temporal_action.triggered.connect(
                        lambda: self._edit_temporal_validity(node)
                    )
                    state = self._model.temporal_validity(node)
                    if not state.valid and state.boundary is not None:
                        jump_text = (
                            "Jump to Start"
                            if state.status.value == "before_start"
                            else "Jump to Last Valid Day"
                        )
                        jump_action = menu.addAction(jump_text)
                        jump_action.triggered.connect(
                            lambda: self.jump_to_valid_time(node.id)
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

    def edit_properties(self, node_id: str) -> None:
        """Open properties for a node by id through the existing command path."""
        if self._model is None:
            return
        node = self._model.find_node_by_id(node_id)
        if node is not None:
            self._edit_properties(node)

    def edit_temporal_validity(self, node_id: str) -> None:
        """Open the focused temporal-validity editor for a node by id."""
        if self._model is None:
            return
        node = self._model.find_node_by_id(node_id)
        if node is not None:
            self._edit_temporal_validity(node)

    def _edit_properties(self, node: "MapLayerNode") -> None:
        """Open the contextual inspector and emit a property-edit intent."""
        from src.gui.dialogs.layer_properties_dialog import (
            LayerPropertiesDialog,
        )

        self._close_temporal_dialog()
        if self._properties_dialog is not None:
            if self._properties_node_id == node.id:
                self._properties_dialog.show()
                self._properties_dialog.raise_()
                self._properties_dialog.activateWindow()
                return
            self._close_properties_dialog()

        dialog = LayerPropertiesDialog(
            node,
            self,
        )
        self._properties_dialog = dialog
        self._properties_node_id = node.id
        dialog.accepted.connect(
            lambda: self.layer_properties_changed.emit(
                node.id, dialog.properties()
            )
        )
        dialog.destroyed.connect(self._on_properties_dialog_destroyed)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _edit_temporal_validity(self, node: "MapLayerNode") -> None:
        """Open the temporal editor and emit only validity properties."""
        from src.gui.dialogs.temporal_validity_dialog import (
            TemporalValidityDialog,
        )

        self._close_properties_dialog()
        if self._temporal_dialog is not None:
            if self._temporal_node_id == node.id:
                self._temporal_dialog.set_playhead_time(self._playhead_time)
                self._temporal_dialog.show()
                self._temporal_dialog.raise_()
                self._temporal_dialog.activateWindow()
                return
            self._close_temporal_dialog()

        dialog = TemporalValidityDialog(
            node,
            self,
            calendar_converter=self._calendar_converter,
            playhead_time=self._playhead_time,
        )
        self._temporal_dialog = dialog
        self._temporal_node_id = node.id
        dialog.accepted.connect(
            lambda: self.layer_properties_changed.emit(
                node.id, dialog.properties()
            )
        )
        dialog.destroyed.connect(self._on_temporal_dialog_destroyed)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    @Slot()
    def _on_properties_dialog_destroyed(self) -> None:
        """Forget the modeless editor after either OK or Cancel."""
        self._properties_dialog = None
        self._properties_node_id = None

    def _close_properties_dialog(self) -> None:
        """Close the current properties editor without applying changes."""
        dialog = self._properties_dialog
        self._properties_dialog = None
        self._properties_node_id = None
        if dialog is not None:
            dialog.reject()

    @Slot()
    def _on_temporal_dialog_destroyed(self) -> None:
        """Forget the temporal editor after either OK or Cancel."""
        self._temporal_dialog = None
        self._temporal_node_id = None

    def _close_temporal_dialog(self) -> None:
        """Close the temporal editor without applying changes."""
        dialog = self._temporal_dialog
        self._temporal_dialog = None
        self._temporal_node_id = None
        if dialog is not None:
            dialog.reject()

    def close_properties_editor(self) -> None:
        """Close modeless layer editors when map context changes."""
        self._close_properties_dialog()
        self._close_temporal_dialog()

    def jump_to_valid_time(self, node_id: str) -> None:
        """Jump to a deterministic date inside a feature's valid interval."""
        if self._model is None:
            return
        node = self._model.find_node_by_id(node_id)
        if node is None:
            return
        state = self._model.temporal_validity(node)
        if state.valid or state.boundary is None:
            return
        if state.status.value == "before_start":
            target = state.boundary
        else:
            target = state.boundary - 1.0
            source = (
                self._model.find_node_by_id(state.source_node_id)
                if state.source_node_id
                else node
            )
            if source is not None and source.start_date is not None:
                target = max(source.start_date, target)
        self.temporal_jump_requested.emit(float(target))

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
        # Snapshot virtual rows: toolbar is already shown for the raster parent.
        if node.layer_type == MAP_LAYER_TYPE_SNAPSHOT:
            return

        is_raster = node.layer_type == MAP_LAYER_TYPE_RASTER
        self._raster_toolbar.setVisible(is_raster)

        if is_raster:
            previous_node_id = self._current_node_id
            if (
                self._btn_edit_toggle.isChecked()
                and previous_node_id
                and previous_node_id != node.id
            ):
                self.raster_edit_stopped.emit()
                self.reset_edit_toggle()
            self._current_node_id = node.id
            mode = self._raster_mode_by_id.get(node.id, "discrete")
            if previous_node_id != node.id and mode == "discrete":
                self._advanced_paint_toggle.blockSignals(True)
                self._advanced_paint_toggle.setChecked(False)
                self._advanced_paint_toggle.blockSignals(False)
            self._update_sample_tool_availability(mode)
            self._show_mode_badge(mode)
            # Refresh legend and entity picker from stored metadata
            layer_meta = self._raster_meta_by_id.get(node.id)
            self._raster_name_label.setText(node.name)
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
            self._refresh_edit_target_state(node.id, layer_meta)
            # Show preset and query rows
            self._preset_toolbar_row.setVisible(True)
            self._query_row.setVisible(True)
            self._apply_mode_tool_visibility()
        else:
            self._current_node_id = ""
            self._update_sample_tool_availability("discrete")
            self._raster_mode_label.setVisible(False)
            self._edit_target_label.setVisible(False)
            self._paint_guidance_label.setVisible(False)
            self._snapshot_count_label.setText("")
            self._preset_toolbar_row.setVisible(False)
            self._query_row.setVisible(False)
            # Notify consumers that no raster is selected
            self.raster_layer_selected.emit(None, None)

        # Reset edit toggle when switching layers or switching between rasters
        if self._btn_edit_toggle.isChecked() and not is_raster:
            self.raster_edit_stopped.emit()
            self.reset_edit_toggle()

    def reset_edit_toggle(self) -> None:
        """Reset the edit toggle button without emitting signals.

        Use when edit mode was stopped externally (e.g. Escape key or
        raster-to-raster layer switch) so the panel stays in sync with
        the tool state.
        """
        self._btn_edit_toggle.blockSignals(True)
        self._btn_edit_toggle.setChecked(False)
        self._btn_edit_toggle.setText("Paint")
        self._save_status_label.setVisible(False)
        self._btn_edit_toggle.blockSignals(False)
        if self._current_node_id:
            self._refresh_edit_target_state(self._current_node_id)
        else:
            self._edit_target_label.setVisible(False)
            self._paint_guidance_label.setVisible(False)

    def _on_edit_toggled(self, checked: bool) -> None:
        """Handle the Edit / Done toggle button."""
        if checked:
            self._btn_edit_toggle.setText("Stop painting")
            self._edit_target_label.setVisible(True)
            self._save_status_label.setVisible(True)
            if self._selected_node_id:
                self.raster_edit_requested.emit(self._selected_node_id)
        else:
            self._btn_edit_toggle.setText("Paint")
            self._edit_target_label.setVisible(bool(self._current_node_id))
            self._save_status_label.setVisible(False)
            self.raster_edit_stopped.emit()

    def _refresh_edit_target_state(
        self,
        node_id: str,
        layer_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Resolve and render the safe Base/dated edit target for one raster."""
        if node_id != self._current_node_id:
            return

        metadata_known = node_id in self._raster_meta_by_id
        meta = (
            layer_meta
            if layer_meta is not None
            else self._raster_meta_by_id.get(node_id)
        )
        snapshots = dict((meta or {}).get("snapshots", {}))
        explicit_label = self._raster_edit_target_label_by_id.get(node_id)

        if explicit_label:
            target_label = explicit_label
            target_ready = True
        elif not metadata_known:
            target_label = "Loading…"
            target_ready = False
        elif snapshots:
            target_label = "Not selected"
            target_ready = False
        else:
            target_label = "Base"
            target_ready = True

        self._edit_target_label.setText(f"Target: {target_label}")
        self._edit_target_label.setVisible(True)
        self._btn_edit_base.setEnabled(metadata_known)
        self._refresh_edit_state_action(node_id)
        self._refresh_paint_action_state(target_ready=target_ready)

    def _refresh_edit_state_action(self, node_id: str) -> None:
        """Show the dated-state edit action for the last clicked state."""
        lore_date = self._selected_snapshot_date_by_node.get(node_id)
        snapshots = dict(
            (self._raster_meta_by_id.get(node_id) or {}).get("snapshots", {})
        )
        has_exact_state = False
        if lore_date is not None:
            for key in snapshots:
                try:
                    if float(key) == lore_date:
                        has_exact_state = True
                        break
                except (TypeError, ValueError):
                    continue
        if not has_exact_state:
            self._selected_snapshot_date_by_node.pop(node_id, None)

        is_current = node_id == self._current_node_id
        self._btn_edit_state.setVisible(is_current and has_exact_state)
        self._btn_edit_state.setEnabled(is_current and has_exact_state)
        if has_exact_state and lore_date is not None:
            label = self._format_snapshot_label_with_converter(
                self._calendar_converter, lore_date
            )
            self._btn_edit_state.setToolTip(f"Edit dated raster state: {label}")

    def _refresh_paint_action_state(
        self,
        *,
        target_ready: Optional[bool] = None,
    ) -> None:
        """Gate Paint on both a safe file target and a valid mode target."""
        node_id = self._current_node_id
        if not node_id:
            self._btn_edit_toggle.setEnabled(False)
            self._paint_guidance_label.setVisible(False)
            return

        if target_ready is None:
            meta = self._raster_meta_by_id.get(node_id)
            metadata_known = node_id in self._raster_meta_by_id
            target_ready = bool(
                self._raster_edit_target_label_by_id.get(node_id)
                or (metadata_known and not (meta or {}).get("snapshots"))
            )

        mode = self._raster_mode_by_id.get(node_id, "discrete")
        value_ready = True
        if (
            self._current_node_id
            and mode == "discrete"
            and not self._advanced_paint_toggle.isChecked()
        ):
            allowed = self._discrete_paint_values_by_id.get(node_id, set())
            value_ready = self._paint_value_spin.value() in allowed

        failed = node_id in self._raster_save_failed_nodes
        enabled = target_ready and value_ready and not failed
        self._btn_edit_toggle.setEnabled(enabled)

        guidance = ""
        if not target_ready:
            if node_id not in self._raster_meta_by_id:
                guidance = "Loading raster states…"
            else:
                guidance = (
                    "Choose Edit base, or select a dated state and choose "
                    "Edit this state."
                )
        elif not value_ready:
            guidance = (
                "Choose a class or palette swatch. Enable Manual value only "
                "when you need to paint an unmapped class ID."
            )
        elif failed:
            guidance = "Save failed — choose an edit target again to resume."

        self._paint_guidance_label.setText(guidance)
        self._paint_guidance_label.setVisible(bool(guidance))
        if not enabled and self._btn_edit_toggle.isChecked():
            self.raster_edit_stopped.emit()
            self.reset_edit_toggle()

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
        """Repopulate the *Paint as:* class picker and paint-value selector.

        Also drives the visual swatch grid / gradient scrubber switch: in
        discrete mode the stack shows the swatch grid; in continuous mode it
        shows the gradient scrubber; in color mode both are hidden.

        Args:
            layer_meta: Raster layer metadata dict, or ``None``.
            mode: ``"discrete"``, ``"continuous"``, or ``"color"``.
            name_map: Optional dict mapping entity/event UUIDs to names.
        """
        from src.gui.widgets.map.raster_mapping import get_discrete_class_choices

        is_discrete = mode == "discrete"
        is_continuous = mode == "continuous"
        choices: List[Tuple[str, int]] = []

        if is_discrete and layer_meta:
            choices = get_discrete_class_choices(layer_meta, name_map)

        # Repopulate class combo
        self._entity_picker_combo.blockSignals(True)
        self._entity_picker_combo.clear()
        for label, value in choices:
            self._entity_picker_combo.addItem(f"{label}  ({value})", value)
        self._entity_picker_combo.blockSignals(False)
        self._entity_picker_row.setVisible(is_discrete and bool(choices))

        # Populate visual selectors from the active ColorMap (if any).
        color_map: Optional[ColorMap] = None
        cm_dict = (layer_meta or {}).get("color_map")
        if cm_dict:
            try:
                color_map = ColorMap.from_dict(cm_dict)
            except Exception:
                color_map = None
        self._active_color_map = color_map
        self._configure_display_value_control(color_map)

        # Swatch grid (discrete).
        swatches: List[Swatch] = []
        allowed_values = {value for _label, value in choices}
        if is_discrete and color_map is not None:
            label_by_value: Dict[int, str] = {val: lbl for lbl, val in choices}
            for idx, entry in enumerate(color_map.entries):
                try:
                    val = int(entry.value) if entry.value is not None else None
                except (TypeError, ValueError):
                    val = None
                if val is None:
                    continue
                allowed_values.add(val)
                lbl = label_by_value.get(val, str(val))
                hotkey = idx + 1 if idx < _MAXIMUM_SWATCH_HOTKEY_INDEX else None
                swatches.append(Swatch(value=val, color=entry.color, label=lbl, hotkey=hotkey))
        if self._current_node_id:
            self._discrete_paint_values_by_id[self._current_node_id] = allowed_values
        if (
            is_discrete
            and allowed_values
            and not self._advanced_paint_toggle.isChecked()
            and self._paint_value_spin.value() not in allowed_values
        ):
            preferred_value = choices[0][1] if choices else swatches[0].value
            self._set_paint_value(int(cast(Any, preferred_value)))
        self._swatch_grid.set_swatches(swatches)
        self._swatch_grid.set_active_value(self._paint_value_spin.value())

        # Gradient scrubber (continuous).
        self._gradient_scrubber.set_color_map(color_map)
        if color_map is not None:
            lo = color_map.stretch_min if color_map.stretch_min is not None else 0
            hi = color_map.stretch_max if color_map.stretch_max is not None else 65535
            try:
                self._gradient_scrubber.set_range(int(lo), int(hi))
            except (TypeError, ValueError):
                pass
        self._gradient_scrubber.blockSignals(True)
        self._gradient_scrubber.set_value(self._paint_value_spin.value())
        self._gradient_scrubber.blockSignals(False)

        # Switch stacked page: 0=swatch, 1=gradient, 2=empty (color mode).
        if is_discrete and swatches:
            self._paint_value_stack.setCurrentIndex(0)
            self._paint_value_stack.setVisible(True)
        elif is_continuous:
            self._paint_value_stack.setCurrentIndex(1)
            self._paint_value_stack.setVisible(True)
        else:
            self._paint_value_stack.setCurrentIndex(2)
            self._paint_value_stack.setVisible(mode != "color")

        # Refresh the display-mapped label for the current value.
        self._paint_value_display_label.setText(
            self._format_value_for_display(self._paint_value_spin.value())
        )
        self._refresh_paint_action_state()

    @Slot(int)
    def _on_entity_picked(self, index: int) -> None:
        """Set paint value to the value of the selected class.

        Args:
            index: Combo box index of the selected item.

        """
        value = self._entity_picker_combo.itemData(index)
        if value is not None and value >= 0:
            self._set_paint_value(int(value))
            ColorHistoryService.instance().push("raster.paint_value", int(value))

    @Slot(int)
    def _on_paint_value_spin_changed(self, value: int) -> None:
        """Sync the class picker combo, swatch grid, scrubber and display label.

        When the user manually enters a value that matches a mapped class the
        combo automatically selects that class, giving instant feedback via
        "Paint as: <ClassName>".  When there is no match the combo falls back
        to "— manual —" (index 0) so it never shows a stale class name.

        Args:
            value: New paint value from the spin box.
        """
        self._sync_paint_value_peers(value)
        self._on_raster_setting_changed()

    def _sync_paint_value_peers(self, value: int) -> None:
        """Push *value* into swatch grid, scrubber, combo, and display label.

        Called from the spin-box slot and from :meth:`_set_paint_value`.
        Signals on peer widgets are blocked to avoid feedback loops.
        """
        self._swatch_grid.set_active_value(int(value))
        self._sync_display_value_from_raw(int(value))
        self._gradient_scrubber.blockSignals(True)
        self._gradient_scrubber.set_value(int(value))
        self._gradient_scrubber.blockSignals(False)
        self._paint_value_display_label.setText(
            self._format_value_for_display(int(value))
        )
        if self._entity_picker_row.isVisible():
            self._entity_picker_combo.blockSignals(True)
            try:
                matched = False
                for i in range(self._entity_picker_combo.count()):
                    if self._entity_picker_combo.itemData(i) == value:
                        self._entity_picker_combo.setCurrentIndex(i)
                        matched = True
                        break
                if not matched:
                    self._entity_picker_combo.setCurrentIndex(-1)
            finally:
                self._entity_picker_combo.blockSignals(False)

    def _set_paint_value(self, value: int) -> None:
        """Set the paint value from an external caller (syncs all peers).

        Use this instead of ``self._paint_value_spin.setValue(...)`` so the
        swatch grid, scrubber, and display label all stay aligned.

        Args:
            value: New paint value.
        """
        clamped = max(0, min(65535, int(value)))
        mode = self._raster_mode_by_id.get(self._current_node_id, "discrete")
        if (
            self._current_node_id
            and mode == "discrete"
            and not self._advanced_paint_toggle.isChecked()
        ):
            allowed = self._discrete_paint_values_by_id.get(
                self._current_node_id, set()
            )
            if clamped not in allowed:
                return
        if self._paint_value_spin.value() == clamped:
            # Still sync peers in case they drifted.
            self._sync_paint_value_peers(clamped)
            return
        self._paint_value_spin.setValue(clamped)

    @Slot(int)
    def _on_brush_size_slider_changed(self, value: int) -> None:
        """Mirror the brush-size slider into the scrubber spin box."""
        if self._brush_size_spin.value() == value:
            return
        self._brush_size_spin.blockSignals(True)
        self._brush_size_spin.setValue(int(value))
        self._brush_size_spin.blockSignals(False)
        self._on_raster_setting_changed()

    @Slot(int)
    def _on_brush_size_spin_changed(self, value: int) -> None:
        """Mirror the brush-size scrubber into the slider."""
        if self._brush_size_slider.value() == value:
            return
        self._brush_size_slider.blockSignals(True)
        self._brush_size_slider.setValue(int(value))
        self._brush_size_slider.blockSignals(False)
        self._on_raster_setting_changed()

    @Slot(object)
    def _on_swatch_clicked(self, value: object) -> None:
        """Set the paint value from a swatch tile click."""
        try:
            int_val = int(cast(Any, value))
        except (TypeError, ValueError):
            return
        self._set_paint_value(int_val)
        ColorHistoryService.instance().push("raster.paint_value", int_val)

    @Slot(int)
    def _on_gradient_scrubber_changed(self, value: int) -> None:
        """Live scrubber drag — update spin without pushing to history."""
        if self._paint_value_spin.value() == value:
            return
        self._paint_value_spin.setValue(int(value))

    @Slot(int)
    def _on_gradient_scrubber_committed(self, value: int) -> None:
        """Gradient scrubber release — commit value to history."""
        self._set_paint_value(int(value))
        ColorHistoryService.instance().push("raster.paint_value", int(value))

    @Slot(object)
    def _on_recent_value_chosen(self, value: object) -> None:
        """A recent-values tile was clicked — restore its value."""
        try:
            int_val = int(cast(Any, value))
        except (TypeError, ValueError):
            return
        mode = self._raster_mode_by_id.get(self._current_node_id, "discrete")
        if mode == "discrete" and not self._advanced_paint_toggle.isChecked():
            return
        self._set_paint_value(int_val)

    def _format_value_for_display(self, value: int) -> str:
        """Format *value* using the active colour map's display mapping.

        Returns the raw integer string when no display mapping is defined.

        Args:
            value: Raw raster value.

        Returns:
            Human-readable value (e.g. ``"23.5 °C"`` or ``"42"``).
        """
        layer_meta = self._raster_meta_by_id.get(self._current_node_id) if self._current_node_id else None
        cm_dict = (layer_meta or {}).get("color_map")
        if not cm_dict:
            return str(int(value))
        try:
            color_map = ColorMap.from_dict(cm_dict)
            if color_map.display_min is not None:
                return format_display_value(color_map, int(value))
        except Exception:
            pass
        return str(int(value))

    def _configure_display_value_control(
        self,
        color_map: Optional[ColorMap],
    ) -> None:
        """Configure the continuous target in calibrated display units."""
        self._display_value_updating = True
        try:
            if (
                color_map is not None
                and color_map.display_min is not None
                and color_map.display_max is not None
            ):
                lo = min(color_map.display_min, color_map.display_max)
                hi = max(color_map.display_min, color_map.display_max)
                self._display_value_spin.setRange(lo, hi)
                self._display_unit_label.setText(color_map.unit or "display")
            else:
                self._display_value_spin.setRange(0.0, 65535.0)
                self._display_unit_label.setText("raw")
            self._sync_display_value_from_raw(self._paint_value_spin.value())
        finally:
            self._display_value_updating = False

    def _sync_display_value_from_raw(self, raw_value: int) -> None:
        color_map = self._active_color_map
        display_value = float(raw_value)
        if (
            color_map is not None
            and color_map.display_min is not None
            and color_map.display_max is not None
        ):
            raw_min = float(color_map.stretch_min or 0)
            raw_max = float(
                color_map.stretch_max
                if color_map.stretch_max is not None
                else 65535
            )
            fraction = (float(raw_value) - raw_min) / max(raw_max - raw_min, 1.0)
            display_value = color_map.display_min + fraction * (
                color_map.display_max - color_map.display_min
            )
        self._display_value_spin.blockSignals(True)
        self._display_value_spin.setValue(display_value)
        self._display_value_spin.blockSignals(False)

    @Slot(float)
    def _on_display_value_changed(self, display_value: float) -> None:
        if self._display_value_updating:
            return
        color_map = self._active_color_map
        raw_value = display_value
        if (
            color_map is not None
            and color_map.display_min is not None
            and color_map.display_max is not None
        ):
            raw_min = float(color_map.stretch_min or 0)
            raw_max = float(
                color_map.stretch_max
                if color_map.stretch_max is not None
                else 65535
            )
            fraction = (display_value - color_map.display_min) / max(
                color_map.display_max - color_map.display_min,
                1e-12,
            )
            raw_value = raw_min + fraction * (raw_max - raw_min)
        self._set_paint_value(int(round(raw_value)))

    def _choose_rgba_color(self) -> None:
        color = QColorDialog.getColor(
            self._rgba_color,
            self,
            "Choose paint colour",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if not color.isValid():
            return
        self._rgba_color = color
        self._rgba_alpha_spin.setValue(color.alpha())
        self._refresh_rgba_button()
        self._on_raster_setting_changed()

    @Slot(int)
    def _on_rgba_alpha_changed(self, alpha: int) -> None:
        self._rgba_color.setAlpha(alpha)
        self._refresh_rgba_button()
        self._on_raster_setting_changed()

    def _refresh_rgba_button(self) -> None:
        self._rgba_color_button.setText(
            f"#{self._rgba_color.red():02X}{self._rgba_color.green():02X}"
            f"{self._rgba_color.blue():02X}{self._rgba_color.alpha():02X}"
        )

    def _choose_gradient_color(self, choose_from: bool) -> None:
        current = self._rgba_gradient_from if choose_from else self._rgba_gradient_to
        color = QColorDialog.getColor(
            current,
            self,
            "Choose gradient endpoint",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if not color.isValid():
            return
        if choose_from:
            self._rgba_gradient_from = color
            self._rgba_gradient_from_button.setText(
                f"From #{color.red():02X}{color.green():02X}"
                f"{color.blue():02X}{color.alpha():02X}"
            )
        else:
            self._rgba_gradient_to = color
            self._rgba_gradient_to_button.setText(
                f"To #{color.red():02X}{color.green():02X}"
                f"{color.blue():02X}{color.alpha():02X}"
            )
        self._on_raster_setting_changed()

    @Slot(str, str, str)
    def set_raster_save_state(
        self,
        node_id: str,
        state: str,
        message: str = "",
    ) -> None:
        """Display queued raster persistence state for the active layer."""
        if node_id != self._current_node_id:
            return
        labels = {
            "saving": "Saving…",
            "saved": "Saved",
            "failed": "Save failed — editing paused",
        }
        self._save_status_label.setText(message or labels.get(state, state))
        self._save_status_label.setVisible(self._btn_edit_toggle.isChecked())
        if state == "failed":
            self._raster_save_failed_nodes.add(node_id)
            self._refresh_paint_action_state()

    def set_raster_edit_target(self, node_id: str, label: str) -> None:
        """Expose the resolved Base/dated target before Paint can begin."""
        self._raster_edit_target_label_by_id[node_id] = label
        self._raster_save_failed_nodes.discard(node_id)
        if node_id != self._current_node_id:
            return
        self._save_status_label.setText("Saved")
        self._refresh_edit_target_state(node_id)

    def clear_raster_edit_targets(self, node_id: Optional[str] = None) -> None:
        """Clear panel target state when the coordinator invalidates file targets."""
        if node_id is None:
            self._raster_edit_target_label_by_id.clear()
        else:
            self._raster_edit_target_label_by_id.pop(node_id, None)
        if self._current_node_id and (
            node_id is None or node_id == self._current_node_id
        ):
            self._refresh_edit_target_state(self._current_node_id)

    def set_raster_paint_color(
        self,
        color: tuple[int, int, int, int],
    ) -> None:
        """Synchronize the RGBA picker after an eyedropper sample."""
        self._rgba_color = QColor(*color)
        self._rgba_alpha_spin.blockSignals(True)
        self._rgba_alpha_spin.setValue(color[3])
        self._rgba_alpha_spin.blockSignals(False)
        self._refresh_rgba_button()

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
                from src.gui.constants import MAP_LAYER_TYPE_RASTER

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
        for node_id, metadata in meta_by_id.items():
            mode = str(metadata.get("mode", ""))
            if mode in {"discrete", "continuous", "color"}:
                self._raster_mode_by_id.setdefault(node_id, mode)
        self._raster_name_map_by_id = name_map_by_id or {}
        # Refresh legend and picker if a raster is already selected
        if self._selected_node_id and self._model is not None:
            node = self._model.find_node_by_id(self._selected_node_id)
            if node is not None:
                from src.gui.constants import MAP_LAYER_TYPE_RASTER

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
                    self._refresh_edit_target_state(
                        self._selected_node_id, layer_meta
                    )
                    # Notify consumers to refresh the floating legend
                    self.raster_layer_selected.emit(self._selected_node_id, layer_meta)

    def _update_snapshot_count_label(self, layer_meta: Optional[Dict[str, Any]]) -> None:
        """Refresh the snapshot count label for the selected raster layer."""
        snap_count = len((layer_meta or {}).get("snapshots", {}))
        if snap_count:
            self._snapshot_count_label.setText(
                f"{snap_count} dated state{'s' if snap_count != 1 else ''}"
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
            if (
                mode == "continuous"
                and self._paint_value_spin.value()
                < _CONTINUOUS_DEFAULT_VISIBILITY_THRESHOLD
            ):
                self._set_paint_value(32768)
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
        self._btn_sample.setEnabled(True)
        if mode == "color":
            self._btn_sample.setToolTip(
                "Eyedropper — sample the stored RGBA pixel and make it active"
            )
        else:
            self._btn_sample.setToolTip(self._sample_tool_enabled_tooltip)

    @Slot()
    def _on_falloff_changed(self) -> None:
        """Update hardness label and emit settings changed."""
        value = self._falloff_slider.value()
        self._falloff_label.setText(f"{value}%")
        self._on_raster_setting_changed()

    @Slot(int)
    def _on_brush_opacity_changed(self, value: int) -> None:
        """Update opacity readout label and emit settings changed."""
        self._brush_opacity_label.setText(f"{value}%")
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
        self._apply_mode_tool_visibility()
        self.raster_settings_changed.emit()

    @Slot(bool)
    def _on_advanced_paint_toggled(self, checked: bool) -> None:
        """Apply explicit Manual-value semantics for discrete rasters."""
        mode = self._raster_mode_by_id.get(self._current_node_id, "discrete")
        if mode == "discrete" and not checked:
            allowed = self._discrete_paint_values_by_id.get(
                self._current_node_id, set()
            )
            if allowed and self._paint_value_spin.value() not in allowed:
                self._set_paint_value(min(allowed))
        self._apply_mode_tool_visibility()
        self._refresh_paint_action_state()
        self.raster_settings_changed.emit()

    def _apply_mode_tool_visibility(self) -> None:
        """Show only controls meaningful for the selected mode and tool."""
        mode = self._raster_mode_by_id.get(self._current_node_id, "discrete")
        tool = self.raster_tool_mode
        is_brush = tool == "brush"
        is_fill = tool == "fill"
        is_gradient = tool == "gradient"
        is_sample = tool == "sample"
        is_discrete = mode == "discrete"
        is_continuous = mode == "continuous"
        is_rgba = mode == "color"

        self._btn_gradient.setVisible(not is_discrete)
        if is_discrete and is_gradient:
            self._btn_brush.setChecked(True)
            is_brush, is_gradient = True, False

        self._brush_size_row.setVisible(is_brush or is_gradient)
        self._hardness_row.setVisible(is_brush and not is_discrete)
        self._brush_opacity_row.setVisible(is_brush and not is_discrete)
        self._falloff_curve_row.setVisible(is_brush and not is_discrete)
        self._gradient_sub_row.setVisible(is_gradient)
        self._gradient_endpoints_row.setVisible(is_gradient and is_continuous)
        self._rgba_gradient_row.setVisible(is_gradient and is_rgba)
        self._fill_tolerance_row.setVisible(is_fill and not is_discrete)
        self._rgba_color_row.setVisible(is_rgba and (is_brush or is_fill))
        self._display_value_row.setVisible(
            is_continuous and (is_brush or is_fill)
        )
        self._paint_value_stack.setVisible(
            not is_sample and not is_rgba and not is_gradient
        )
        self._recent_paint_values.setVisible(
            not is_sample
            and not is_rgba
            and not is_gradient
            and (
                is_continuous
                or (is_discrete and self._advanced_paint_toggle.isChecked())
            )
        )
        self._entity_picker_row.setVisible(
            is_discrete
            and not is_sample
            and self._entity_picker_combo.count() > 0
        )
        self._advanced_paint_toggle.setVisible(
            is_discrete or is_continuous
        )
        if is_discrete:
            self._advanced_paint_toggle.setText("Manual value")
            self._advanced_paint_toggle.setToolTip(
                "Allow raw class IDs that are not present in the class palette"
            )
        else:
            self._advanced_paint_toggle.setText("Advanced")
            self._advanced_paint_toggle.setToolTip(
                "Show the raw 0–65535 raster value"
            )
        self._raw_value_row.setVisible(
            not is_sample
            and not is_rgba
            and self._advanced_paint_toggle.isChecked()
        )
        self._refresh_paint_action_state()

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

    def set_raster_brush_size(self, size: int) -> None:
        """Set the brush size spinbox and slider without emitting settings_changed.

        Used by Ctrl+scroll in the view to keep the panel in sync.
        """
        clamped = max(1, min(128, int(size)))
        self._brush_size_spin.blockSignals(True)
        self._brush_size_spin.setValue(clamped)
        self._brush_size_spin.blockSignals(False)
        self._brush_size_slider.blockSignals(True)
        self._brush_size_slider.setValue(clamped)
        self._brush_size_slider.blockSignals(False)

    @Slot(str)
    def set_raster_tool_mode(self, mode: str) -> None:
        """Synchronize visible tool selection after a scoped shortcut."""
        buttons = {
            "brush": self._btn_brush,
            "fill": self._btn_fill,
            "gradient": self._btn_gradient,
            "sample": self._btn_sample,
        }
        button = buttons.get(mode)
        if button is not None and button.isVisible() and button.isEnabled():
            button.setChecked(True)

    @property
    def raster_paint_value(self) -> int:
        """Current paint value from the spin box."""
        return self._paint_value_spin.value()

    @property
    def raster_falloff(self) -> float:
        """Engine falloff derived from UI hardness (falloff = 1 - H)."""
        return 1.0 - self._falloff_slider.value() / 100.0

    @property
    def raster_brush_opacity(self) -> float:
        """Current brush opacity (0.0–1.0) from the slider."""
        return self._brush_opacity_slider.value() / 100.0

    @property
    def raster_falloff_curve(self) -> str:
        """Current falloff curve name (lowercase) from the combo box."""
        return self._falloff_curve_combo.currentText().lower()

    @property
    def raster_gradient_sub_mode(self) -> str:
        """Current gradient sub-mode (lowercase) from the combo box."""
        return self._gradient_sub_combo.currentText().lower()

    @property
    def raster_fill_tolerance(self) -> int:
        """Mode-aware raw connected-fill tolerance."""
        mode = self._raster_mode_by_id.get(self._current_node_id, "discrete")
        if mode == "discrete":
            return 0
        maximum = 255 if mode == "color" else 65535
        return round(self._fill_tolerance_slider.value() / 100.0 * maximum)

    @staticmethod
    def _qcolor_rgba(color: QColor) -> tuple[int, int, int, int]:
        return color.red(), color.green(), color.blue(), color.alpha()

    @property
    def raster_paint_color(self) -> tuple[int, int, int, int]:
        """Active straight-alpha RGBA paint colour."""
        return self._qcolor_rgba(self._rgba_color)

    @property
    def raster_gradient_from(
        self,
    ) -> int | tuple[int, int, int, int]:
        """Return the active gradient's starting value or colour."""
        mode = self._raster_mode_by_id.get(self._current_node_id, "discrete")
        if mode == "color":
            return self._qcolor_rgba(self._rgba_gradient_from)
        return self._gradient_from_spin.value()

    @property
    def raster_gradient_to(
        self,
    ) -> int | tuple[int, int, int, int]:
        """Return the active gradient's ending value or colour."""
        mode = self._raster_mode_by_id.get(self._current_node_id, "discrete")
        if mode == "color":
            return self._qcolor_rgba(self._rgba_gradient_to)
        return self._gradient_to_spin.value()

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

    @Slot()
    def _on_edit_base_clicked(self) -> None:
        """Explicitly select the base raster as the current edit target."""
        if self._current_node_id:
            self.raster_base_edit_requested.emit(self._current_node_id)

    @Slot()
    def _on_edit_state_clicked(self) -> None:
        """Select the visibly chosen dated raster state as the edit target."""
        node_id = self._current_node_id
        lore_date = self._selected_snapshot_date_by_node.get(node_id)
        if node_id and lore_date is not None:
            self.raster_snapshot_edit_requested.emit(node_id, lore_date)

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

        snapshots = (layer_meta or {}).get("snapshots", {})
        if not snapshots:
            self._selected_snapshot_date_by_node.pop(node_id, None)
            self._refresh_edit_state_action(node_id)
            self._model.set_virtual_snapshot_children(node_id, [])
            return

        parsed: List[Tuple[str, float]] = []
        for key in snapshots:
            try:
                parsed.append((str(key), float(key)))
            except (TypeError, ValueError):
                continue

        parsed.sort(key=lambda s: s[1], reverse=True)
        selected_date = self._selected_snapshot_date_by_node.get(node_id)
        if selected_date is not None and all(
            lore_date != selected_date for _key, lore_date in parsed
        ):
            self._selected_snapshot_date_by_node.pop(node_id, None)

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
        self._refresh_edit_state_action(node_id)

        raster_node = self._model.find_node_by_id(node_id)
        if raster_node is not None:
            raster_index = self._model.index_from_node(raster_node)
            if raster_index.isValid():
                self._tree.setExpanded(
                    self._proxy_model.mapFromSource(raster_index), True
                )

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
        self._set_paint_value(preset.paint_value)

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
