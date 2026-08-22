"""Interaction Handler for the Map Graphics View.

Manages context menus, drag-and-drop, icon/color pickers, and feature
style dialogs. Keeps UI interaction logic separate from the core view.
"""

import json
import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QColorDialog,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QToolButton,
    QWidget,
)

from src.core.marker_appearance import (
    MARKER_ICON_ANCHOR_ATTRIBUTE,
    MARKER_ICON_ID_ATTRIBUTE,
    MarkerAppearance,
    MarkerIconAnchor,
)
from src.core.marker_icon import MarkerIconDefinition
from src.core.marker_sizing import (
    MARKER_SIZING_ATTRIBUTE,
    MARKER_SIZING_SOURCE_ATTRIBUTE,
    MarkerSizingSettings,
    MarkerSizingSource,
)
from src.core.style_constants import (
    MAX_BORDER_WIDTH,
    MIN_BORDER_WIDTH,
    V_BORDER,
    V_BORDER_WIDTH,
    V_FILL,
)
from src.core.theme_manager import ThemeManager
from src.gui.dialogs.icon_picker_dialog import IconPickerDialog
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.map.feature_items import PathItem, RegionItem
from src.gui.widgets.map.marker_item import MarkerItem
from src.services.marker_icon_catalog import MarkerIconCatalog

if TYPE_CHECKING:
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent

    from src.gui.widgets.map.map_graphics_view import MapGraphicsView

logger = logging.getLogger(__name__)


PATH_LINE_STYLES: tuple[tuple[str, list[float]], ...] = (
    ("Solid", []),
    ("Dotted", [1.0, 3.0]),
    ("Short Dash", [4.0, 3.0]),
    ("Long Dash", [10.0, 4.0]),
    ("Dash Dot", [8.0, 3.0, 1.0, 3.0]),
)
"""Named dash patterns available for persisted path strokes."""


def _build_compact_stroke_width_control(
    initial_value: float,
) -> tuple[QWidget, QDoubleSpinBox]:
    """Build a normal-height width field with full-size decrement buttons."""
    width_spin = QDoubleSpinBox()
    width_spin.setRange(0.5, 20.0)
    width_spin.setSingleStep(0.5)
    width_spin.setValue(initial_value)
    width_spin.setObjectName("pathStrokeWidthSpin")
    width_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    width_spin.setMinimumHeight(28)

    width_control = QWidget()
    width_layout = QHBoxLayout(width_control)
    width_layout.setContentsMargins(0, 0, 0, 0)
    width_layout.setSpacing(2)
    width_layout.addWidget(width_spin, 1)

    decrease_width = QToolButton()
    decrease_width.setObjectName("pathStrokeWidthDecreaseButton")
    decrease_width.setText("−")
    decrease_width.setToolTip("Decrease stroke width")
    increase_width = QToolButton()
    increase_width.setObjectName("pathStrokeWidthIncreaseButton")
    increase_width.setText("+")
    increase_width.setToolTip("Increase stroke width")
    for button in (decrease_width, increase_width):
        button.setFixedSize(28, 28)
        button.setAutoRepeat(True)
        button.setAutoRepeatDelay(300)
        button.setStyleSheet(StyleHelper.get_icon_button_style())
    decrease_width.clicked.connect(width_spin.stepDown)
    increase_width.clicked.connect(width_spin.stepUp)
    width_layout.addWidget(decrease_width)
    width_layout.addWidget(increase_width)
    return width_control, width_spin


class InteractionHandler:
    """Manages context menus, drag-and-drop, and picker dialogs.

    Args:
        view: The parent MapGraphicsView.
    """

    def __init__(self, view: "MapGraphicsView") -> None:
        """Initialize map pointer and keyboard interaction handling."""
        self._view = view
        self._copied_marker_appearance: Optional[dict] = None

    # ------------------------------------------------------------------
    # Context Menus
    # ------------------------------------------------------------------

    def show_marker_context_menu(self, item: MarkerItem, global_pos: QPoint) -> None:
        """Shows context menu for a marker.

        Args:
            item: The marker item.
            global_pos: Screen position for the menu.
        """
        menu = QMenu(self._view)

        if item.is_locked:
            self._populate_unlock_menu(menu, item.marker_id)
            menu.exec(global_pos)
            return

        self._populate_lock_menu(menu, item.marker_id)
        menu.addSeparator()

        if item.is_temporal_ghost:
            self._populate_temporal_ghost_menu(menu, item.marker_id)
            menu.exec(global_pos)
            return

        if item.object_type != "event":
            has_trajectory = item.marker_id in self._view._trajectory_marker_ids
            edit_trajectory_action = QAction(
                "Edit Trajectory" if has_trajectory else "Create Trajectory",
                self._view,
            )
            edit_trajectory_action.triggered.connect(
                lambda: self._view.trajectory_edit_requested.emit(item.marker_id)
            )
            menu.addAction(edit_trajectory_action)
            menu.addSeparator()

        change_icon_action = QAction(self._view)
        change_icon_action.setText("Change Icon...")
        change_icon_action.triggered.connect(lambda: self.show_icon_picker(item))
        menu.addAction(change_icon_action)

        # --- Visual Styling sub-menu ---
        style_menu = QMenu("Visual Styling", self._view)

        edit_appearance_action = QAction("Edit Appearance...", self._view)
        edit_appearance_action.setStatusTip(
            "Drag the corner to resize and the centre handle to set the anchor; "
            "press Enter to apply or Escape to cancel"
        )
        edit_appearance_action.triggered.connect(
            lambda: self._view.start_marker_appearance_edit(item.marker_id)
        )
        style_menu.addAction(edit_appearance_action)

        copy_appearance_action = QAction("Copy Appearance", self._view)
        copy_appearance_action.triggered.connect(
            lambda: self._copy_marker_appearance(item)
        )
        style_menu.addAction(copy_appearance_action)

        paste_appearance_action = QAction("Paste Appearance", self._view)
        paste_appearance_action.setEnabled(self._copied_marker_appearance is not None)
        paste_appearance_action.triggered.connect(
            lambda: self._paste_marker_appearance(item)
        )
        style_menu.addAction(paste_appearance_action)

        reset_anchor_action = QAction("Reset Anchor to Centre", self._view)
        reset_anchor_action.setEnabled(
            not MarkerAppearance.from_attributes(
                item._visual_attributes
            ).anchor.is_centered
        )
        reset_anchor_action.triggered.connect(
            lambda: self._reset_marker_anchor(item)
        )
        style_menu.addAction(reset_anchor_action)

        style_menu.addSeparator()

        scale_action = QAction("Size & Zoom...", self._view)
        scale_action.triggered.connect(lambda: self.show_scale_dialog(item))
        style_menu.addAction(scale_action)

        reset_size_action = QAction("Reset Size to Icon Default", self._view)
        reset_size_action.setEnabled(
            self._view.marker_icon_catalog.resolve_attributes(
                item._visual_attributes
            )
            is not None
        )
        reset_size_action.triggered.connect(
            lambda: self._reset_size_to_icon_default(item)
        )
        style_menu.addAction(reset_size_action)

        border_action = QAction("Set Border Strength...", self._view)
        border_action.triggered.connect(lambda: self.show_border_strength_dialog(item))
        style_menu.addAction(border_action)

        fill_action = QAction("Set Fill Color...", self._view)
        fill_action.triggered.connect(lambda: self.show_fill_color_picker(item))
        style_menu.addAction(fill_action)

        border_color_action = QAction("Set Border Color...", self._view)
        border_color_action.triggered.connect(
            lambda: self.show_border_color_picker(item)
        )
        style_menu.addAction(border_color_action)

        style_menu.addSeparator()

        no_fill_action = QAction("No Fill (Transparent)", self._view)
        no_fill_action.triggered.connect(lambda: self._apply_no_fill(item))
        style_menu.addAction(no_fill_action)

        no_border_action = QAction("No Border", self._view)
        no_border_action.triggered.connect(lambda: self._apply_no_border(item))
        style_menu.addAction(no_border_action)

        self._configure_vector_style_actions(
            item,
            (
                border_action,
                fill_action,
                border_color_action,
                no_fill_action,
                no_border_action,
            ),
        )

        menu.addMenu(style_menu)

        temporal_action = QAction("Temporal Validity...", self._view)
        temporal_action.triggered.connect(
            lambda: self._view.temporal_validity_requested.emit(item.marker_id)
        )
        menu.addAction(temporal_action)

        menu.addSeparator()

        delete_action = QAction(self._view)
        delete_action.setText("Delete Marker")
        delete_action.triggered.connect(
            lambda: self._view.delete_marker_requested.emit(item.marker_id)
        )
        menu.addAction(delete_action)
        menu.exec(global_pos)

    def show_trajectory_context_menu(
        self, marker_id: str, global_pos: QPoint
    ) -> None:
        """Show actions for a passive trajectory path."""
        menu = QMenu(self._view)
        edit_action = QAction("Edit Trajectory", self._view)
        edit_action.triggered.connect(
            lambda: self._view.trajectory_edit_requested.emit(marker_id)
        )
        menu.addAction(edit_action)
        menu.exec(global_pos)

    def show_map_background_context_menu(
        self, scene_pos: QPointF, global_pos: QPoint
    ) -> None:
        """Shows context menu for adding features at a specific location.

        Args:
            scene_pos: Scene position where the menu was triggered.
            global_pos: Screen position for the menu.
        """
        norm_x, norm_y = self._view.coord_system.to_normalized(scene_pos)
        menu = QMenu(self._view)

        add_action = QAction(self._view)
        add_action.setText("Add Marker Here")
        add_action.triggered.connect(
            lambda: self._view.add_marker_requested.emit(norm_x, norm_y)
        )
        menu.addAction(add_action)

        menu.addSeparator()

        draw_path_action = QAction(self._view)
        draw_path_action.setText("Draw Path Here...")
        draw_path_action.triggered.connect(lambda: self._view.start_drawing("path"))
        menu.addAction(draw_path_action)

        draw_region_action = QAction(self._view)
        draw_region_action.setText("Draw Region Here...")
        draw_region_action.triggered.connect(lambda: self._view.start_drawing("region"))
        menu.addAction(draw_region_action)

        menu.exec(global_pos)

    def show_feature_context_menu(
        self, item: PathItem | RegionItem, global_pos: QPoint
    ) -> None:
        """Shows context menu for a path or region feature.

        Args:
            item: The PathItem or RegionItem.
            global_pos: Screen position for the menu.
        """
        menu = QMenu(self._view)

        if item.is_locked:
            self._populate_unlock_menu(menu, item.marker_id)
            menu.exec(global_pos)
            return

        self._populate_lock_menu(menu, item.marker_id)
        menu.addSeparator()

        if item.is_temporal_ghost:
            self._populate_temporal_ghost_menu(menu, item.marker_id)
            menu.exec(global_pos)
            return

        feature_label = "Path" if isinstance(item, PathItem) else "Region"

        edit_style_action = QAction(self._view)
        edit_style_action.setText(f"Edit {feature_label} Style...")
        edit_style_action.triggered.connect(
            lambda: self.show_feature_style_dialog(item)
        )
        menu.addAction(edit_style_action)

        edit_vertices_action = QAction(self._view)
        edit_vertices_action.setText("Edit Geometry at Playhead...")
        edit_vertices_action.triggered.connect(
            lambda: self._view.feature_geometry_edit_requested.emit(item.marker_id)
        )
        menu.addAction(edit_vertices_action)

        manage_states_action = QAction(self._view)
        manage_states_action.setText("Manage Geometry States...")
        manage_states_action.triggered.connect(
            lambda: self._view.feature_geometry_manage_requested.emit(item.marker_id)
        )
        menu.addAction(manage_states_action)

        temporal_action = QAction("Temporal Validity...", self._view)
        temporal_action.triggered.connect(
            lambda: self._view.temporal_validity_requested.emit(item.marker_id)
        )
        menu.addAction(temporal_action)

        menu.addSeparator()

        delete_action = QAction(self._view)
        delete_action.setText(f"Delete {feature_label}")
        delete_action.triggered.connect(
            lambda: self._view.delete_marker_requested.emit(item.marker_id)
        )
        menu.addAction(delete_action)
        menu.exec(global_pos)

    def _populate_unlock_menu(self, menu: QMenu, marker_id: str) -> None:
        """Add the sole permitted action for a locked canvas feature."""
        action = QAction("Unlock", self._view)
        action.triggered.connect(lambda: self._view.unlock_feature(marker_id))
        menu.addAction(action)

    def _populate_lock_menu(self, menu: QMenu, marker_id: str) -> None:
        """Add the canvas action that locks an otherwise interactive feature."""
        action = QAction("Lock", self._view)
        action.triggered.connect(
            lambda: self._view.set_feature_locked(marker_id, True)
        )
        menu.addAction(action)

    def _copy_marker_appearance(self, item: MarkerItem) -> None:
        """Store a validated, semantic-data-free marker appearance snapshot."""
        self._copied_marker_appearance = item.appearance_payload()

    def _paste_marker_appearance(self, item: MarkerItem) -> None:
        """Preview and persist one exact copied appearance."""
        if self._copied_marker_appearance is None:
            return
        if self._view.is_editing_marker_appearance:
            self._view.cancel_marker_appearance_edit()
        payload = dict(self._copied_marker_appearance)
        item.apply_appearance_payload(payload)
        self._view._schedule_label_layout()
        self._view.marker_appearance_changed.emit(item.marker_id, payload)

    def _reset_marker_anchor(self, item: MarkerItem) -> None:
        """Restore the legacy centred anchor as one undoable appearance change."""
        if self._view.is_editing_marker_appearance:
            self._view.cancel_marker_appearance_edit()
        payload = item.appearance_payload()
        payload[MARKER_ICON_ANCHOR_ATTRIBUTE] = MarkerIconAnchor().to_dict()
        item.apply_appearance_payload(payload)
        self._view._schedule_label_layout()
        self._view.marker_appearance_changed.emit(item.marker_id, payload)

    @staticmethod
    def _configure_vector_style_actions(
        item: MarkerItem, actions: tuple[QAction, ...]
    ) -> None:
        """Disable SVG/fallback styling actions for raster marker artwork."""
        enabled = not item.is_raster_icon
        for action in actions:
            action.setEnabled(enabled)
            if not enabled:
                action.setStatusTip("Available for SVG and fallback markers only")

    def _populate_temporal_ghost_menu(self, menu: QMenu, marker_id: str) -> None:
        """Add the restricted authoring actions available for a ghost."""
        jump_action = QAction("Jump to Valid Time", self._view)
        jump_action.triggered.connect(
            lambda: self._view.temporal_jump_requested.emit(marker_id)
        )
        menu.addAction(jump_action)

        validity_action = QAction("Temporal Validity...", self._view)
        validity_action.triggered.connect(
            lambda: self._view.temporal_validity_requested.emit(marker_id)
        )
        menu.addAction(validity_action)

        show_action = QAction("Show in Layers", self._view)
        show_action.triggered.connect(
            lambda: self._view.temporal_show_in_layers_requested.emit(marker_id)
        )
        menu.addAction(show_action)

    # ------------------------------------------------------------------
    # Picker Dialogs
    # ------------------------------------------------------------------

    def show_icon_picker(self, marker_item: MarkerItem) -> None:
        """Shows the icon picker dialog for a marker.

        Args:
            marker_item: The marker to change the icon for.
        """
        dialog = IconPickerDialog(
            self._view,
            world_root=self._view._world_root,
            catalog=self._view.marker_icon_catalog,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._view.marker_icon_catalog = MarkerIconCatalog.load(
                self._view._world_root
            )
            definition = dialog.selected_definition
            if definition is None:
                return
            updates = self._icon_definition_updates(marker_item, definition)

            attributes = dict(marker_item._visual_attributes)
            attributes.update(updates)
            marker_item.set_visual_attributes(attributes)
            marker_item.set_icon_definition(definition)
            self._view.marker_visual_style_changed.emit(
                marker_item.marker_id,
                updates,
            )

    @staticmethod
    def _icon_definition_updates(
        marker_item: MarkerItem,
        definition: MarkerIconDefinition,
    ) -> dict[str, object]:
        """Build stable-ID and conditional icon-default size updates."""
        updates: dict[str, object] = {MARKER_ICON_ID_ATTRIBUTE: definition.id}
        if (
            marker_item._visual_attributes.get(MARKER_SIZING_SOURCE_ATTRIBUTE)
            != MarkerSizingSource.ICON_DEFAULT.value
        ):
            return updates
        image_width = marker_item.pixmap_item.boundingRect().width()
        sizing = MarkerSizingSettings.for_map_image_width(
            image_width,
            native_diameter_px=definition.default_native_diameter_px,
        )
        updates[MARKER_SIZING_ATTRIBUTE] = sizing.to_dict()
        updates[MARKER_SIZING_SOURCE_ATTRIBUTE] = MarkerSizingSource.ICON_DEFAULT.value
        return updates

    # ------------------------------------------------------------------
    # Visual Styling Dialogs
    # ------------------------------------------------------------------

    def show_scale_dialog(self, marker_item: MarkerItem) -> None:
        """Show the per-marker size and zoom behavior dialog.

        Args:
            marker_item: The marker to change the scale for.
        """
        from src.gui.widgets.map.marker_size_dialog import MarkerSizeDialog

        pixmap_item = self._view.pixmap_item
        image_width = (
            pixmap_item.boundingRect().width() if pixmap_item is not None else 0.0
        )
        dialog = MarkerSizeDialog(
            MarkerSizingSettings.from_attributes(marker_item._visual_attributes),
            self._view.map_width_meters,
            image_width,
            self._view.transform().m11(),
            self._view,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updates = {
                MARKER_SIZING_ATTRIBUTE: dialog.get_settings().to_dict(),
                MARKER_SIZING_SOURCE_ATTRIBUTE: MarkerSizingSource.CUSTOM.value,
            }
            new_attrs = dict(marker_item._visual_attributes)
            new_attrs.update(updates)
            marker_item.set_visual_attributes(new_attrs)
            self._view._schedule_label_layout()
            self._view.marker_visual_style_changed.emit(
                marker_item.marker_id,
                updates,
            )

    def _reset_size_to_icon_default(self, marker_item: MarkerItem) -> None:
        """Restore the current icon's canonical native-scale diameter."""
        definition = self._view.marker_icon_catalog.resolve_attributes(
            marker_item._visual_attributes
        )
        if definition is None:
            return
        image_width = marker_item.pixmap_item.boundingRect().width()
        sizing = MarkerSizingSettings.for_map_image_width(
            image_width,
            native_diameter_px=definition.default_native_diameter_px,
        )
        updates = {
            MARKER_SIZING_ATTRIBUTE: sizing.to_dict(),
            MARKER_SIZING_SOURCE_ATTRIBUTE: MarkerSizingSource.ICON_DEFAULT.value,
        }
        attributes = dict(marker_item._visual_attributes)
        attributes.update(updates)
        marker_item.set_visual_attributes(attributes)
        self._view._schedule_label_layout()
        self._view.marker_visual_style_changed.emit(marker_item.marker_id, updates)

    def show_border_strength_dialog(self, marker_item: MarkerItem) -> None:
        """Shows a dialog to set the marker's border width.

        Args:
            marker_item: The marker to change the border for.
        """
        from PySide6.QtWidgets import (
            QDialogButtonBox,
            QFormLayout,
            QSpinBox,
        )

        dialog = QDialog(self._view)
        dialog.setWindowTitle("Set Border Strength")
        dialog.setMinimumWidth(250)
        layout = QFormLayout(dialog)

        spin = QSpinBox()
        spin.setRange(MIN_BORDER_WIDTH, MAX_BORDER_WIDTH)
        current = marker_item._visual_attributes.get(V_BORDER_WIDTH, 2)
        spin.setValue(int(current))
        layout.addRow("Border Width (px):", spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            updates = {V_BORDER_WIDTH: spin.value()}
            new_attrs = dict(marker_item._visual_attributes)
            new_attrs.update(updates)
            marker_item.set_visual_attributes(new_attrs)
            self._view.marker_visual_style_changed.emit(
                marker_item.marker_id,
                updates,
            )

    def show_fill_color_picker(self, marker_item: MarkerItem) -> None:
        """Shows a color picker for the marker's visual fill color.

        Args:
            marker_item: The marker to change the fill color for.
        """
        from src.services.visual_resolver import VisualResolver

        initial = VisualResolver.resolve_fill(
            marker_item._visual_attributes, marker_item.object_type
        )
        color = QColorDialog.getColor(QColor(initial), self._view, "Select Fill Color")
        if color.isValid():
            color_hex = color.name().upper()
            updates = {V_FILL: color_hex}
            new_attrs = dict(marker_item._visual_attributes)
            new_attrs.update(updates)
            marker_item._custom_color = color_hex
            marker_item._color = QColor(color_hex)
            marker_item.set_visual_attributes(new_attrs)
            self._view.marker_visual_style_changed.emit(
                marker_item.marker_id,
                updates,
            )

    def show_border_color_picker(self, marker_item: MarkerItem) -> None:
        """Shows a color picker for the marker's border color.

        Args:
            marker_item: The marker to change the border color for.
        """
        from src.services.visual_resolver import VisualResolver

        initial = VisualResolver.resolve_border_color(
            marker_item._visual_attributes, marker_item.object_type
        )
        color = QColorDialog.getColor(
            QColor(initial), self._view, "Select Border Color"
        )
        if color.isValid():
            color_hex = color.name().upper()
            updates = {V_BORDER: color_hex}
            new_attrs = dict(marker_item._visual_attributes)
            new_attrs.update(updates)
            marker_item.set_visual_attributes(new_attrs)
            self._view.marker_visual_style_changed.emit(
                marker_item.marker_id,
                updates,
            )

    def show_feature_style_dialog(self, item: PathItem | RegionItem) -> None:
        """Opens an inline dialog to edit a feature's visual style.

        Args:
            item: The PathItem or RegionItem to edit.
        """
        from PySide6.QtWidgets import (
            QComboBox,
            QDialogButtonBox,
            QFormLayout,
        )

        from src.gui.widgets.map.feature_items import (
            DEFAULT_REGION_FILL_COLOR,
            DEFAULT_STROKE_COLOR,
            DEFAULT_STROKE_WIDTH,
        )

        dialog = QDialog(self._view)
        dialog.setWindowTitle(f"Edit {item.label} Style")
        dialog.setMinimumWidth(300)
        layout = QFormLayout(dialog)

        # Stroke color
        stroke_init = _safe_color_css(
            item._style.get("stroke_color", DEFAULT_STROKE_COLOR)
        )
        stroke_btn = QPushButton(stroke_init)
        stroke_btn.setStyleSheet(
            f"background-color: {stroke_init}; color: white; padding: 4px 12px;"
        )
        _stroke_color = [stroke_init]

        def _pick_stroke() -> None:
            c = QColorDialog.getColor(QColor(_stroke_color[0]), dialog, "Stroke Color")
            if c.isValid():
                safe = c.name()
                _stroke_color[0] = safe
                stroke_btn.setText(safe)
                stroke_btn.setStyleSheet(
                    f"background-color: {safe}; color: white; padding: 4px 12px;"
                )

        stroke_btn.clicked.connect(_pick_stroke)
        layout.addRow("Stroke Color:", stroke_btn)

        # Stroke width
        width_control, width_spin = _build_compact_stroke_width_control(
            item._style.get("stroke_width", DEFAULT_STROKE_WIDTH)
        )
        layout.addRow("Stroke Width:", width_control)

        line_style_combo: QComboBox | None = None
        if isinstance(item, PathItem):
            line_style_combo = QComboBox()
            current_pattern = item._dash_pattern()
            if current_pattern not in [pattern for _, pattern in PATH_LINE_STYLES]:
                pattern_text = ", ".join(str(value) for value in current_pattern)
                line_style_combo.addItem(
                    f"Custom ({pattern_text})" if pattern_text else "Custom (solid)",
                    list(current_pattern),
                )
            for name, pattern in PATH_LINE_STYLES:
                line_style_combo.addItem(name, pattern)

            for index in range(line_style_combo.count()):
                if line_style_combo.itemData(index) == current_pattern:
                    line_style_combo.setCurrentIndex(index)
                    break
            layout.addRow("Line Style:", line_style_combo)

        # Fill color (regions only)
        fill_btn: Optional[QPushButton] = None
        _fill_color: list = [None]
        if isinstance(item, RegionItem):
            fill_init = _safe_color_css(
                item._style.get("fill_color", DEFAULT_REGION_FILL_COLOR),
                preserve_alpha=True,
            )
            fill_btn = QPushButton(fill_init)
            fill_btn.setStyleSheet(
                f"background-color: {fill_init}; color: white; padding: 4px 12px;"
            )
            _fill_color = [fill_init]

            def _pick_fill() -> None:
                c = QColorDialog.getColor(
                    QColor(_fill_color[0]),
                    dialog,
                    "Fill Color",
                    QColorDialog.ColorDialogOption.ShowAlphaChannel,
                )
                if c.isValid():
                    _fill_color[0] = c.name(QColor.NameFormat.HexArgb)
                    fill_btn.setText(_fill_color[0])
                    fill_btn.setStyleSheet(
                        f"background-color: {c.name()}; color: white; "
                        f"padding: 4px 12px;"
                    )

            fill_btn.clicked.connect(_pick_fill)
            layout.addRow("Fill Color:", fill_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_style = dict(item._style)
            new_style["stroke_color"] = _stroke_color[0]
            new_style["stroke_width"] = width_spin.value()
            if line_style_combo is not None:
                selected_pattern = line_style_combo.currentData()
                if isinstance(selected_pattern, list):
                    new_style["dash_pattern"] = list(selected_pattern)
            if isinstance(item, RegionItem) and _fill_color[0]:
                new_style["fill_color"] = _fill_color[0]

            item._style = new_style
            item.update()
            self._view.feature_style_changed.emit(item.marker_id, new_style)
            logger.info(f"Style updated for {item.marker_id}: {new_style}")

    def _apply_no_fill(self, marker_item: MarkerItem) -> None:
        """Sets the marker fill to transparent (no fill).

        Args:
            marker_item: The marker to update.
        """
        updates = {V_FILL: "none"}
        new_attrs = dict(marker_item._visual_attributes)
        new_attrs.update(updates)
        marker_item._custom_color = "none"
        marker_item.set_visual_attributes(new_attrs)
        self._view.marker_visual_style_changed.emit(marker_item.marker_id, updates)
        logger.info(f"No fill applied to marker {marker_item.marker_id}")

    def _apply_no_border(self, marker_item: MarkerItem) -> None:
        """Sets the marker border to invisible (no border).

        Args:
            marker_item: The marker to update.
        """
        updates = {V_BORDER: "none", V_BORDER_WIDTH: 0}
        new_attrs = dict(marker_item._visual_attributes)
        new_attrs.update(updates)
        marker_item.set_visual_attributes(new_attrs)
        self._view.marker_visual_style_changed.emit(marker_item.marker_id, updates)
        logger.info(f"No border applied to marker {marker_item.marker_id}")

    # ------------------------------------------------------------------
    # Drag and Drop
    # ------------------------------------------------------------------

    def handle_drag_enter(self, event: "QDragEnterEvent") -> None:
        """Accept drag events with our custom MIME type.

        Args:
            event: The drag enter event.
        """
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        if event.mimeData().hasFormat(KRAKEN_ITEM_MIME_TYPE):
            event.acceptProposedAction()
            self._show_drop_hint()
        else:
            event.ignore()

    def handle_drag_move(self, event: "QDragMoveEvent") -> None:
        """Allow drop only over the map pixmap.

        Args:
            event: The drag move event.
        """
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        if not event.mimeData().hasFormat(KRAKEN_ITEM_MIME_TYPE):
            event.ignore()
            return

        if not self._view.pixmap_item:
            event.ignore()
            return

        scene_pos = self._view.mapToScene(event.position().toPoint())
        item_pos = self._view.pixmap_item.mapFromScene(scene_pos)
        if self._view.pixmap_item.contains(item_pos):
            event.acceptProposedAction()
            self._show_drop_hint()
        else:
            event.ignore()
            self._hide_drop_hint()

    def handle_drag_leave(self) -> None:
        """Handle drag leave event."""
        self._hide_drop_hint()

    def handle_drop(self, event: "QDropEvent") -> None:
        """Handle drop of item from Project Explorer.

        Args:
            event: The drop event.
        """
        self._hide_drop_hint()
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        if not event.mimeData().hasFormat(KRAKEN_ITEM_MIME_TYPE):
            event.ignore()
            return

        if not self._view.pixmap_item:
            event.ignore()
            return

        scene_pos = self._view.mapToScene(event.position().toPoint())
        item_pos = self._view.pixmap_item.mapFromScene(scene_pos)
        if not self._view.pixmap_item.contains(item_pos):
            event.ignore()
            return

        norm_x, norm_y = self._view.coord_system.to_normalized(scene_pos)
        norm_x, norm_y = self._view.coord_system.clamp_normalized(norm_x, norm_y)

        if not self._handle_drop_data(event, norm_x, norm_y):
            event.ignore()

    def _show_drop_hint(self) -> None:
        """Show the drag-and-drop overlay."""
        overlay = self._view._drop_hint_overlay
        if overlay:
            overlay.setGeometry(self._view.viewport().rect())
            overlay.show()
            overlay.raise_()

    def _hide_drop_hint(self) -> None:
        """Hide the drag-and-drop overlay."""
        overlay = self._view._drop_hint_overlay
        if overlay:
            overlay.hide()

    def _handle_drop_data(
        self, event: "QDropEvent", norm_x: float, norm_y: float
    ) -> bool:
        """Parses drop data and emits marker request.

        Args:
            event: The drop event.
            norm_x: Normalized X coordinate.
            norm_y: Normalized Y coordinate.

        Returns:
            True if the drop was handled.
        """
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        try:
            data_bytes = event.mimeData().data(KRAKEN_ITEM_MIME_TYPE).data()
            data = json.loads(bytes(data_bytes).decode("utf-8"))

            item_id = data.get("id")
            item_type = data.get("type")
            item_name = data.get("name", "Unknown")

            if item_id and item_type:
                self._view.marker_drop_requested.emit(
                    item_id, item_type, item_name, norm_x, norm_y
                )
                event.acceptProposedAction()
                logger.info(
                    f"Dropped {item_type} '{item_name}' at ({norm_x:.3f}, {norm_y:.3f})"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to parse drop data: {e}")

        return False


def _safe_color_css(color_str: str, *, preserve_alpha: bool = False) -> str:
    """Validates a color string for safe use in QSS stylesheets.

    Args:
        color_str: A candidate color string.
        preserve_alpha: Return Qt's ``#AARRGGBB`` form instead of dropping
            the alpha channel.

    Returns:
        A validated hex color safe for use in CSS.
    """
    c = QColor(color_str)
    if c.isValid():
        name_format = (
            QColor.NameFormat.HexArgb
            if preserve_alpha
            else QColor.NameFormat.HexRgb
        )
        return c.name(name_format)
    return ThemeManager().get_theme().get("text_dim", "#808080").lower()
