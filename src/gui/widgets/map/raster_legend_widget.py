"""Raster layer legend widget.

Displays a collapsible legend panel showing class colour swatches (discrete)
or a gradient bar (continuous) for the currently selected raster layer.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.widgets.map.raster_mapping import normalize_value_entity_map

logger = logging.getLogger(__name__)

_SWATCH_SIZE = 16  # pixels
_GRADIENT_BAR_WIDTH = 24  # pixels


class RasterLegendWidget(QWidget):
    """Collapsible legend panel for a raster layer.

    Shows colour swatches and labels for discrete layers, or a gradient bar
    with min/max labels for continuous layers.  Collapses/expands via a
    toggle button.

    Usage::

        legend = RasterLegendWidget(parent)
        legend.set_layer(layer_meta_dict)   # call when selected layer changes

    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header row with collapse toggle
        header = QHBoxLayout()
        header.setContentsMargins(0, 4, 0, 2)
        self._toggle_btn = QToolButton()
        self._toggle_btn.setText("▼ Legend")
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(True)
        self._toggle_btn.setAutoRaise(True)
        self._toggle_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        theme = ThemeManager().get_theme()
        self._toggle_btn.setStyleSheet(
            f"QToolButton {{ text-align: left; padding: 3px 6px; "
            f"color: {theme.get('text_main', '#E8E8E8')}; "
            f"font-weight: bold; font-size: 9pt; }}"
        )
        self._toggle_btn.toggled.connect(self._on_toggle)
        header.addWidget(self._toggle_btn)
        outer.addLayout(header)

        # Scrollable content area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(4, 4, 4, 4)
        self._content_layout.setSpacing(4)
        self._content_layout.addStretch()

        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_layer(self, layer_meta: Optional[Dict[str, Any]]) -> None:
        """Populate the legend from *layer_meta*.

        Args:
            layer_meta: The raster layer metadata dict, or ``None`` to clear.

        """
        self._clear_content()
        if not layer_meta:
            return

        color_map = layer_meta.get("color_map", {})
        cm_type = (
            color_map.get("type", "palette")
            if isinstance(color_map, dict)
            else "palette"
        )

        if cm_type == "gradient":
            self._build_continuous_legend(color_map)
        else:
            self._build_discrete_legend(
                color_map, layer_meta.get("value_entity_map", {})
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _clear_content(self) -> None:
        while self._content_layout.count() > 1:  # keep trailing stretch
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _build_discrete_legend(
        self,
        color_map: Dict[str, Any],
        vem_raw: Any,
    ) -> None:
        # Build value → label dict from value_entity_map
        label_by_value: Dict[int, str] = {}
        vem = normalize_value_entity_map(vem_raw)
        for entry in vem.get("mappings", []):
            v = entry.get("value")
            if v is not None and entry.get("label"):
                label_by_value[int(v)] = entry["label"]

        # Build (value, color, label) triples from palette entries
        entries: List[Tuple[int, str, str]] = []
        for ce in color_map.get("entries", []):
            v = ce.get("value")
            if v is None:
                continue
            color = ce.get("color", "#888888")
            label = label_by_value.get(int(v), f"Value {v}")
            entries.append((int(v), color, label))

        # Fallback: if no color_map entries, use vem labels only
        if not entries:
            for entry in vem.get("mappings", []):
                v = entry.get("value")
                if v is not None:
                    entries.append(
                        (int(v), "#888888", entry.get("label") or f"Value {v}")
                    )

        if not entries:
            self._add_placeholder("No classes defined")
            return

        insert_pos = 0
        self._content_layout.insertWidget(insert_pos, self._make_no_data_row())
        insert_pos += 1

        for value, color_hex, label in sorted(entries, key=lambda x: x[0]):
            self._content_layout.insertWidget(
                insert_pos, self._make_swatch_row(color_hex, str(value), label)
            )
            insert_pos += 1

    def _build_continuous_legend(self, color_map: Dict[str, Any]) -> None:
        gradient_start = color_map.get("gradient_start", "#000000")
        gradient_end = color_map.get("gradient_end", "#FFFFFF")
        stretch_min = color_map.get("stretch_min")
        stretch_max = color_map.get("stretch_max")
        display_min = color_map.get("display_min")
        display_max = color_map.get("display_max")
        unit = color_map.get("unit", "")
        format_str = color_map.get("format_str", "{:.2f}")
        scale = color_map.get("scale", "linear")
        bar = _GradientBarWidget(
            gradient_start,
            gradient_end,
            stretch_min,
            stretch_max,
            display_min=display_min,
            display_max=display_max,
            unit=unit,
            format_str=format_str,
            scale=scale,
        )
        self._content_layout.insertWidget(0, bar)

    def _make_swatch_row(self, color_hex: str, value_str: str, label: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)

        swatch = QLabel()
        swatch.setFixedSize(_SWATCH_SIZE, _SWATCH_SIZE)
        pixmap = QPixmap(_SWATCH_SIZE, _SWATCH_SIZE)
        try:
            pixmap.fill(QColor(color_hex))
        except Exception:
            pixmap.fill(QColor("#888888"))
        p = QPainter(pixmap)
        p.setPen(QColor(0, 0, 0, 60))
        p.drawRect(0, 0, _SWATCH_SIZE - 1, _SWATCH_SIZE - 1)
        p.end()
        swatch.setPixmap(pixmap)

        # Merge label and value: "Forest  (3)" or just "Value 3" as fallback
        display = (
            f"{label}  ({value_str})"
            if label and not label.startswith("Value ")
            else label
        )
        theme = ThemeManager().get_theme()
        combined_lbl = QLabel(display)
        combined_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        combined_lbl.setStyleSheet(f"color: {theme.get('text_main', '#E8E8E8')};")

        layout.addWidget(swatch)
        layout.addWidget(combined_lbl)
        return row

    def _make_no_data_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)

        swatch = QLabel()
        swatch.setFixedSize(_SWATCH_SIZE, _SWATCH_SIZE)
        pixmap = QPixmap(_SWATCH_SIZE, _SWATCH_SIZE)
        pixmap.fill(Qt.GlobalColor.transparent)
        theme = ThemeManager().get_theme()
        border_color = QColor(theme.get("text_dim", "#666666"))
        p = QPainter(pixmap)
        p.setPen(border_color)
        p.drawRect(0, 0, _SWATCH_SIZE - 1, _SWATCH_SIZE - 1)
        p.drawLine(0, 0, _SWATCH_SIZE - 1, _SWATCH_SIZE - 1)
        p.drawLine(0, _SWATCH_SIZE - 1, _SWATCH_SIZE - 1, 0)
        p.end()
        swatch.setPixmap(pixmap)

        dim_color = theme.get("text_dim", "#888888")
        label_lbl = QLabel("No data  (0)")
        label_lbl.setStyleSheet(f"color: {dim_color}; font-style: italic;")

        layout.addWidget(swatch)
        layout.addWidget(label_lbl)
        return row

    def _add_placeholder(self, text: str) -> None:
        lbl = QLabel(text)
        dim_color = ThemeManager().get_theme().get("text_dim", "#888888")
        lbl.setStyleSheet(f"color: {dim_color}; font-style: italic;")
        self._content_layout.insertWidget(0, lbl)

    def _on_toggle(self, checked: bool) -> None:
        self._scroll.setVisible(checked)
        self._toggle_btn.setText("▼ Legend" if checked else "▶ Legend")

        # Delegate sizing/positioning to the hosting MapWidget so the
        # collapsed-aware logic in _position_legend_overlay() runs.
        try:
            view = self.parent()
            if view is not None:
                map_widget = view.parent()
                if map_widget is not None and hasattr(
                    map_widget, "_position_legend_overlay"
                ):
                    map_widget._position_legend_overlay(animated=True)
                    return
            # Fallback: anchor to top-left of the viewport.
            if view is not None and hasattr(view, "viewport"):
                vp_rect = view.viewport().geometry()
                _MARGIN = 12
                self.move(
                    vp_rect.x() + _MARGIN,
                    vp_rect.y() + _MARGIN,
                )
        except Exception:
            pass


class _GradientBarWidget(QWidget):
    """Vertical gradient bar for continuous raster legend.

    Renders a colour ramp from *gradient_start* (bottom, value 0) to
    *gradient_end* (top, value 65535) with min/max labels alongside.
    When display mapping is provided, the labels show real-world values
    (e.g. ``"-10 °C"`` / ``"40 °C"``) instead of raw integers.
    """

    def __init__(
        self,
        gradient_start: str = "#000000",
        gradient_end: str = "#FFFFFF",
        stretch_min: Optional[int] = None,
        stretch_max: Optional[int] = None,
        display_min: Optional[float] = None,
        display_max: Optional[float] = None,
        unit: str = "",
        format_str: str = "{:.2f}",
        scale: str = "linear",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._gradient_start = gradient_start
        self._gradient_end = gradient_end
        self.setMinimumHeight(80)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        self._bar_label = QLabel()
        self._bar_label.setMinimumWidth(_GRADIENT_BAR_WIDTH)
        self._bar_label.setMaximumWidth(_GRADIENT_BAR_WIDTH)
        layout.addWidget(self._bar_label)

        theme = ThemeManager().get_theme()
        dim_style = f"font-size: 9pt; color: {theme.get('text_dim', '#aaaaaa')};"
        labels_layout = QVBoxLayout()
        labels_layout.setContentsMargins(0, 0, 0, 0)
        labels_layout.setSpacing(2)

        # Compute display labels using real-world mapping when available
        if display_min is not None and display_max is not None:
            from src.gui.widgets.map.map_data_buffer import (
                ColorMap,
                format_display_value,
            )

            temp_cmap = ColorMap(
                type="gradient",
                display_min=display_min,
                display_max=display_max,
                unit=unit,
                format_str=format_str,
                scale=scale,
                stretch_min=stretch_min if stretch_min is not None else 0,
                stretch_max=stretch_max if stretch_max is not None else 65535,
            )
            top_val = format_display_value(
                temp_cmap, stretch_max if stretch_max is not None else 65535
            )
            bottom_val = format_display_value(
                temp_cmap, stretch_min if stretch_min is not None else 0
            )
        else:
            top_val = str(stretch_max) if stretch_max is not None else "max"
            bottom_val = str(stretch_min) if stretch_min is not None else "0"

        top_label = QLabel(top_val)
        top_label.setStyleSheet(dim_style)
        bottom_label = QLabel(bottom_val)
        bottom_label.setStyleSheet(dim_style)
        labels_layout.addWidget(top_label)
        labels_layout.addStretch()
        labels_layout.addWidget(bottom_label)
        layout.addLayout(labels_layout)

    def resizeEvent(self, event: Any) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._redraw_bar()

    def showEvent(self, event: Any) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._redraw_bar()

    def _redraw_bar(self) -> None:
        h = max(self.height() - 8, 40)
        w = _GRADIENT_BAR_WIDTH
        pixmap = QPixmap(w, h)
        p = QPainter(pixmap)
        gradient = QLinearGradient(0, 0, 0, h)
        try:
            gradient.setColorAt(0.0, QColor(self._gradient_end))
            gradient.setColorAt(1.0, QColor(self._gradient_start))
        except Exception:
            gradient.setColorAt(0.0, QColor("#FFFFFF"))
            gradient.setColorAt(1.0, QColor("#000000"))
        p.fillRect(0, 0, w, h, gradient)
        theme = ThemeManager().get_theme()
        p.setPen(QColor(theme.get("border", "#444444")))
        p.drawRect(0, 0, w - 1, h - 1)
        p.end()
        self._bar_label.setPixmap(pixmap)
