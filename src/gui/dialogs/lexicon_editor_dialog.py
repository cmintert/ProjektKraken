"""Lexicon Editor Dialog Module.

Provides a themed dialog for configuring the Visual Lexicon — custom colors,
shapes, and icons for entity types, and colors, widths, and dashes for
relation types in the relationship graph.
"""

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper

logger = logging.getLogger(__name__)

# Vis.js node shapes that are commonly useful
NODE_SHAPES = [
    "dot",
    "star",
    "triangle",
    "triangleDown",
    "diamond",
    "square",
    "box",
    "ellipse",
    "database",
    "image",
]


class _ColorButton(QPushButton):
    """A small button that displays and lets the user pick a color.

    Shows the current color as background; clicking opens QColorDialog.
    """

    def __init__(
        self, color: str = "#888888", parent: Optional[QWidget] = None
    ) -> None:
        """Initializes the color button.

        Args:
            color: Initial hex color string.
            parent: Parent widget.

        """
        super().__init__(parent)
        self._color = color
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to change color")
        self._apply_swatch()
        self.clicked.connect(self._pick_color)

    def _apply_swatch(self) -> None:
        """Updates the button background to reflect the current color."""
        self.setStyleSheet(
            f"QPushButton {{ background-color: {self._color}; "
            f"border: 1px solid #555; border-radius: 4px; }}"
            f"QPushButton:hover {{ border: 1px solid #aaa; }}"
        )

    def _pick_color(self) -> None:
        """Opens QColorDialog and updates the stored color."""
        dlg = QColorDialog(QColor(self._color), self)
        if dlg.exec() == QColorDialog.DialogCode.Accepted:
            self._color = dlg.selectedColor().name()
            self._apply_swatch()

    def color(self) -> str:
        """Returns the current hex color string.

        Returns:
            str: Hex color such as '#FF0000'.

        """
        return self._color


class LexiconEditorDialog(QDialog):
    """Dialog for editing the Visual Lexicon configuration.

    Provides two tabs: one for entity-type node styling (color, shape, icon)
    and another for relation-type edge styling (color, width, dashes).
    Uses StyleHelper for consistent dark-theme appearance.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        entity_types: Optional[List[str]] = None,
        relation_types: Optional[List[str]] = None,
        current_config: Optional[Dict[str, Any]] = None,
        assets_dir: Optional[str] = None,
    ) -> None:
        """Initializes the Lexicon Editor Dialog.

        Args:
            parent: Parent widget.
            entity_types: List of entity type strings from the schema.
            relation_types: List of relation type strings from the schema.
            current_config: Current lexicon configuration dictionary.
            assets_dir: World assets directory path for icon imports.

        """
        super().__init__(parent)
        self.setWindowTitle("Visual Lexicon Editor")
        self.setMinimumSize(520, 480)
        self.resize(560, 560)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

        self._entity_types = entity_types or []
        self._relation_types = relation_types or []
        self._config = current_config or {"nodes": {}, "edges": {}}
        self._assets_dir = assets_dir

        # Widgets for reading back edited values
        self._node_rows: Dict[str, Dict[str, Any]] = {}
        self._edge_rows: Dict[str, Dict[str, Any]] = {}

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Builds the dialog layout with tabs and buttons."""
        main_layout = QVBoxLayout(self)
        StyleHelper.apply_form_spacing(main_layout)

        # Info label
        info = QLabel(
            "Configure visual styles for each type. "
            "Changes apply on the next graph refresh."
        )
        info.setWordWrap(True)
        info.setStyleSheet(StyleHelper.get_preview_label_style())
        main_layout.addWidget(info)

        # Tabs
        tabs = QTabWidget()
        main_layout.addWidget(tabs, 1)

        # Node tab
        node_tab = self._build_node_tab()
        tabs.addTab(node_tab, "Entity Types")

        # Edge tab
        edge_tab = self._build_edge_tab()
        tabs.addTab(edge_tab, "Relation Types")

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = button_box.button(QDialogButtonBox.StandardButton.Save)
        if save_btn:
            save_btn.setStyleSheet(StyleHelper.get_primary_button_style())
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    # ------------------------------------------------------------------
    # Node (Entity Type) tab
    # ------------------------------------------------------------------

    def _build_node_tab(self) -> QWidget:
        """Constructs the scrollable grid for entity-type styling.

        Returns:
            QWidget: The node configuration tab widget.

        """
        container = QWidget()
        outer = QVBoxLayout(container)
        StyleHelper.apply_no_margins(outer)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(StyleHelper.get_scroll_area_style())

        inner_widget = QWidget()
        grid = QGridLayout(inner_widget)
        grid.setSpacing(6)
        grid.setContentsMargins(8, 8, 8, 8)

        # Header row
        for col, text in enumerate(["Type", "Color", "Shape", "Icon"]):
            lbl = QLabel(text)
            lbl.setStyleSheet(StyleHelper.get_section_header_style())
            grid.addWidget(lbl, 0, col)

        nodes_cfg = self._config.get("nodes", {})

        if not self._entity_types:
            empty = QLabel("No entity types found. Create entities first.")
            empty.setStyleSheet(StyleHelper.get_empty_state_style())
            grid.addWidget(empty, 1, 0, 1, 4)
        else:
            for row_idx, etype in enumerate(self._entity_types, start=1):
                style = nodes_cfg.get(etype, {})
                self._add_node_row(grid, row_idx, etype, style)

        scroll.setWidget(inner_widget)
        outer.addWidget(scroll)
        return container

    def _add_node_row(
        self,
        grid: QGridLayout,
        row: int,
        type_name: str,
        style: Dict[str, Any],
    ) -> None:
        """Adds a single entity-type configuration row.

        Args:
            grid: The grid layout to add widgets to.
            row: Grid row index.
            type_name: The entity type name.
            style: Current style dict for this type.

        """
        # Type label
        label = QLabel(type_name)
        grid.addWidget(label, row, 0)

        # Color button
        color_btn = _ColorButton(style.get("color", "#888888"))
        grid.addWidget(color_btn, row, 1, Qt.AlignmentFlag.AlignCenter)

        # Shape dropdown
        shape_combo = QComboBox()
        shape_combo.addItems(NODE_SHAPES)
        current_shape = style.get("shape", "dot")
        idx = shape_combo.findText(current_shape)
        if idx >= 0:
            shape_combo.setCurrentIndex(idx)
        shape_combo.setStyleSheet(StyleHelper.get_input_field_style())
        grid.addWidget(shape_combo, row, 2)

        # Icon import button
        icon_path = style.get("icon", "")
        icon_btn = QPushButton("📁 Import" if not icon_path else "✅ Change")
        icon_btn.setStyleSheet(StyleHelper.get_tool_button_style())
        icon_btn.setToolTip(icon_path if icon_path else "Import an SVG/PNG icon")
        icon_btn.clicked.connect(
            lambda checked, tn=type_name: self._on_import_icon(tn)
        )
        grid.addWidget(icon_btn, row, 3)

        self._node_rows[type_name] = {
            "color": color_btn,
            "shape": shape_combo,
            "icon_btn": icon_btn,
            "icon_path": icon_path,
        }

    def _on_import_icon(self, type_name: str) -> None:
        """Handles icon import for a given entity type.

        Args:
            type_name: The entity type to import an icon for.

        """
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Import Icon for '{type_name}'",
            "",
            "Image Files (*.svg *.png *.jpg *.jpeg);;All Files (*)",
        )
        if not file_path:
            return

        if self._assets_dir:
            from src.gui.widgets.map.icon_picker_dialog import import_asset_file

            relative = import_asset_file(file_path, Path(self._assets_dir))
            if relative:
                row_data = self._node_rows.get(type_name)
                if row_data:
                    row_data["icon_path"] = relative
                    row_data["icon_btn"].setText("✅ Change")
                    row_data["icon_btn"].setToolTip(relative)
                    # Auto-switch shape to 'image'
                    row_data["shape"].setCurrentText("image")
                logger.info(f"Imported icon for '{type_name}': {relative}")
        else:
            logger.warning("No assets directory set; cannot import icon.")

    # ------------------------------------------------------------------
    # Edge (Relation Type) tab
    # ------------------------------------------------------------------

    def _build_edge_tab(self) -> QWidget:
        """Constructs the scrollable grid for relation-type styling.

        Returns:
            QWidget: The edge configuration tab widget.

        """
        container = QWidget()
        outer = QVBoxLayout(container)
        StyleHelper.apply_no_margins(outer)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(StyleHelper.get_scroll_area_style())

        inner_widget = QWidget()
        grid = QGridLayout(inner_widget)
        grid.setSpacing(6)
        grid.setContentsMargins(8, 8, 8, 8)

        # Header row
        for col, text in enumerate(["Relation", "Color", "Width", "Dashed"]):
            lbl = QLabel(text)
            lbl.setStyleSheet(StyleHelper.get_section_header_style())
            grid.addWidget(lbl, 0, col)

        edges_cfg = self._config.get("edges", {})

        if not self._relation_types:
            empty = QLabel("No relation types found. Create relations first.")
            empty.setStyleSheet(StyleHelper.get_empty_state_style())
            grid.addWidget(empty, 1, 0, 1, 4)
        else:
            for row_idx, rtype in enumerate(self._relation_types, start=1):
                style = edges_cfg.get(rtype, {})
                self._add_edge_row(grid, row_idx, rtype, style)

        scroll.setWidget(inner_widget)
        outer.addWidget(scroll)
        return container

    def _add_edge_row(
        self,
        grid: QGridLayout,
        row: int,
        rel_type: str,
        style: Dict[str, Any],
    ) -> None:
        """Adds a single relation-type configuration row.

        Args:
            grid: The grid layout to add widgets to.
            row: Grid row index.
            rel_type: The relation type name.
            style: Current style dict for this relation type.

        """
        # Relation label
        label = QLabel(rel_type)
        grid.addWidget(label, row, 0)

        # Color button
        color_btn = _ColorButton(style.get("color", "#888888"))
        grid.addWidget(color_btn, row, 1, Qt.AlignmentFlag.AlignCenter)

        # Width spinner
        width_spin = QSpinBox()
        width_spin.setRange(1, 10)
        width_spin.setValue(style.get("width", 1))
        width_spin.setStyleSheet(StyleHelper.get_input_field_style())
        grid.addWidget(width_spin, row, 2)

        # Dashes checkbox
        dashes_cb = QCheckBox()
        dashes_cb.setChecked(style.get("dashes", False))
        dashes_cb.setStyleSheet(StyleHelper.get_checkbox_style())
        grid.addWidget(dashes_cb, row, 3, Qt.AlignmentFlag.AlignCenter)

        self._edge_rows[rel_type] = {
            "color": color_btn,
            "width": width_spin,
            "dashes": dashes_cb,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_lexicon_config(self) -> Dict[str, Any]:
        """Reads back the edited lexicon configuration from the UI widgets.

        Returns:
            Dict[str, Any]: The complete lexicon config with 'nodes' and
            'edges' keys.

        """
        nodes: Dict[str, Any] = {}
        for type_name, widgets in self._node_rows.items():
            entry: Dict[str, Any] = {
                "color": widgets["color"].color(),
                "shape": widgets["shape"].currentText(),
            }
            if widgets.get("icon_path"):
                entry["icon"] = widgets["icon_path"]
            nodes[type_name] = entry

        edges: Dict[str, Any] = {}
        for rel_type, widgets in self._edge_rows.items():
            edges[rel_type] = {
                "color": widgets["color"].color(),
                "width": widgets["width"].value(),
                "dashes": widgets["dashes"].isChecked(),
            }

        return {"nodes": nodes, "edges": edges}
