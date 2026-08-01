"""Raster Stats Panel — QDialog for displaying coverage statistics.

Shows per-class pixel counts and coverage percentages for discrete
raster layers, and a histogram with descriptive statistics for
continuous layers.
"""

from typing import Optional

import shiboken6
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.widgets.map.map_data_buffer import CoverageStats


class _HistogramWidget(QWidget):
    """Simple histogram bar chart painted with QPainter.

    Args:
        counts: List of bucket counts (32 items).
        edges: List of bucket edges (33 items).
        parent: Parent widget.
    """

    def __init__(
        self,
        counts: list,
        edges: list,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._counts = counts
        self._edges = edges
        self.setMinimumHeight(120)
        self.setMinimumWidth(300)

        # Cache theme colors at construction; refresh on theme change.
        self._bar_color: QColor = QColor("#5C82FF")
        self._border_color: QColor = QColor("#3A5ACC")
        self._bg_color: QColor = QColor("#1E1E2E")
        self._refresh_theme_colors()
        ThemeManager().theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, _: dict) -> None:
        if shiboken6.isValid(self):
            self._refresh_theme_colors()

    def _refresh_theme_colors(self) -> None:
        """Update cached bar/border/background colors from the active theme.

        Retrieves the full theme dict via ``ThemeManager().get_theme()`` and
        caches the resolved QColor values so ``paintEvent()`` stays free of
        per-frame theme lookups.
        """
        theme = ThemeManager().get_theme()
        self._bar_color = QColor(theme.get("primary", "#5C82FF"))
        self._border_color = QColor(theme.get("primary_dark", "#3A5ACC"))
        self._bg_color = QColor(theme.get("app_bg", "#1E1E2E"))
        self.update()

    def paintEvent(self, event: object) -> None:  # type: ignore[override]
        """Draw proportional vertical bars for each histogram bucket."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        w = self.width()
        h = self.height()
        padding = 4

        if not self._counts:
            painter.end()
            return

        max_count = max(self._counts) if self._counts else 1
        n = len(self._counts)
        bar_w = max(1, (w - padding * 2) // n)

        painter.fillRect(0, 0, w, h, self._bg_color)
        painter.setPen(QPen(self._border_color, 1))

        for i, count in enumerate(self._counts):
            bar_h = int((count / max_count) * (h - padding * 2)) if max_count > 0 else 0
            x = padding + i * bar_w
            y = h - padding - bar_h
            painter.fillRect(x, y, bar_w - 1, bar_h, self._bar_color)
            painter.drawRect(x, y, bar_w - 1, bar_h)

        painter.end()


class RasterStatsPanel(QDialog):
    """Dialog for displaying raster layer coverage statistics.

    For discrete layers: shows a table of class, value, pixel count, and
    coverage percentage.  For continuous layers: shows min/max/mean/median
    labels and a histogram bar chart.

    Args:
        stats: Computed :class:`CoverageStats` instance.
        layer_name: Human-readable layer name for the dialog title.
        parent: Parent widget.
    """

    def __init__(
        self,
        stats: CoverageStats,
        layer_name: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        title = f"Layer Stats — {layer_name}" if layer_name else "Layer Stats"
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Summary header
        summary_lbl = QLabel(
            f"Total pixels: {stats.total_pixels:,}   |   Mode: {stats.mode}"
        )
        summary_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(summary_lbl)

        if stats.mode == "discrete":
            self._build_discrete_view(layout, stats)
        else:
            self._build_continuous_view(layout, stats)

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        from PySide6.QtWidgets import QPushButton

        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.setToolTip("Close the statistics panel")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Private — builders
    # ------------------------------------------------------------------

    def _build_discrete_view(self, layout: QVBoxLayout, stats: CoverageStats) -> None:
        """Build the table view for discrete layers.

        Args:
            layout: Parent layout to add the table into.
            stats: Coverage statistics to display.
        """
        table = QTableWidget(self)
        table.setObjectName("RasterStatsTable")
        headers = ["Class", "Value", "Pixels", "Coverage %"]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)

        rows = stats.classes
        table.setRowCount(len(rows) + 1)  # +1 for total row

        for row_idx, cs in enumerate(rows):
            table.setItem(row_idx, 0, QTableWidgetItem(cs.label))
            table.setItem(row_idx, 1, QTableWidgetItem(str(cs.value)))
            table.setItem(
                row_idx,
                2,
                QTableWidgetItem(f"{cs.pixel_count:,}"),
            )
            table.setItem(
                row_idx,
                3,
                QTableWidgetItem(f"{cs.percentage:.2f}%"),
            )

        # Total row
        total_row = len(rows)
        total_px = sum(cs.pixel_count for cs in rows)
        total_pct = sum(cs.percentage for cs in rows)
        total_item = QTableWidgetItem("TOTAL")
        total_item.setTextAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
        )
        table.setItem(total_row, 0, total_item)
        table.setItem(total_row, 1, QTableWidgetItem("—"))
        table.setItem(total_row, 2, QTableWidgetItem(f"{total_px:,}"))
        table.setItem(total_row, 3, QTableWidgetItem(f"{total_pct:.2f}%"))

        table.resizeColumnsToContents()
        self._table = table
        layout.addWidget(table)

    def _build_continuous_view(self, layout: QVBoxLayout, stats: CoverageStats) -> None:
        """Build the stats + histogram view for continuous layers.

        Args:
            layout: Parent layout to add the view into.
            stats: Coverage statistics to display.
        """
        # Descriptive stats row
        stats_row = QHBoxLayout()
        stat_labels = [
            ("Min", stats.min_val, "Lowest raw pixel value in this layer"),
            ("Max", stats.max_val, "Highest raw pixel value in this layer"),
            ("Mean", stats.mean_val, "Average raw pixel value across all non-zero pixels"),
            ("Median", stats.median_val, "Median raw pixel value (50th percentile)"),
        ]
        for name, val, tip in stat_labels:
            val_str = f"{val:.1f}" if val is not None else "—"
            lbl = QLabel(f"<b>{name}:</b> {val_str}")
            lbl.setToolTip(tip)
            stats_row.addWidget(lbl)
        stats_row.addStretch()
        layout.addLayout(stats_row)

        # Histogram
        layout.addWidget(QLabel("Value distribution (32 buckets):"))
        hist_widget: QWidget
        if stats.histogram_counts and stats.histogram_edges:
            hist_widget = _HistogramWidget(
                stats.histogram_counts,
                stats.histogram_edges,
                self,
            )
        else:
            hist_widget = QWidget(self)
            hist_widget.setMinimumHeight(120)

        scroll = QScrollArea(self)
        scroll.setWidget(hist_widget)
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(140)
        layout.addWidget(scroll)

    @property
    def table(self) -> Optional[QTableWidget]:
        """The QTableWidget for discrete stats, or ``None`` for continuous."""
        return getattr(self, "_table", None)
