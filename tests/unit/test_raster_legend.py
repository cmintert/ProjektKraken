"""Tests for RasterLegendWidget improvements.

Covers:
- Layer name title row
- Draggable overlay
- Gradient bar tick marks at 25 / 50 / 75 %
- No 30 % height floor in _position_legend_overlay
- Toolbar legend toggle button on MapWidget

Requires QT_QPA_PLATFORM=offscreen.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget

from src.gui.widgets.map.raster_legend_widget import (
    RasterLegendWidget,
    _GradientBarWidget,
)

# ── Helpers ────────────────────────────────────────────────────────────────


def _discrete_meta(name: str = "Test Layer", n_classes: int = 1) -> dict:
    entries = [{"value": i + 1, "color": "#FF0000"} for i in range(n_classes)]
    return {
        "name": name,
        "color_map": {"type": "palette", "entries": entries},
        "value_entity_map": {"mappings": [{"value": i + 1, "label": f"Class {i+1}"} for i in range(n_classes)]},
    }


def _continuous_meta(name: str = "Temperature") -> dict:
    return {
        "name": name,
        "color_map": {
            "type": "gradient",
            "gradient_start": "#0000FF",
            "gradient_end": "#FF0000",
            "stretch_min": 0,
            "stretch_max": 1000,
            "display_min": -10.0,
            "display_max": 40.0,
            "unit": "°C",
            "format_str": "{:.1f}",
            "scale": "linear",
        },
    }


def _make_press(local: QPoint, global_: QPoint) -> QMouseEvent:
    return QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(local),
        QPointF(global_),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _make_move(local: QPoint, global_: QPoint) -> QMouseEvent:
    return QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(local),
        QPointF(global_),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _make_release(local: QPoint, global_: QPoint) -> QMouseEvent:
    return QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(local),
        QPointF(global_),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


# ── Layer name title row ───────────────────────────────────────────────────


class TestLegendTitle:
    """Legend must show the layer name as a title row."""

    def test_title_label_exists_on_widget(self, qtbot) -> None:
        legend = RasterLegendWidget()
        qtbot.addWidget(legend)
        assert hasattr(legend, "_title_label"), "_title_label attribute missing"

    def test_title_shows_layer_name_discrete(self, qtbot) -> None:
        legend = RasterLegendWidget()
        qtbot.addWidget(legend)
        legend.set_layer(_discrete_meta("Climate Zones"))
        assert "Climate Zones" in legend._title_label.text()

    def test_title_shows_layer_name_continuous(self, qtbot) -> None:
        legend = RasterLegendWidget()
        qtbot.addWidget(legend)
        legend.set_layer(_continuous_meta("Temperature"))
        assert "Temperature" in legend._title_label.text()

    def test_title_hidden_when_no_name(self, qtbot) -> None:
        legend = RasterLegendWidget()
        qtbot.addWidget(legend)
        meta = _discrete_meta(name="")
        legend.set_layer(meta)
        assert not legend._title_label.isVisible()

    def test_title_hidden_after_clear(self, qtbot) -> None:
        legend = RasterLegendWidget()
        qtbot.addWidget(legend)
        legend.set_layer(_discrete_meta("My Layer"))
        legend.set_layer(None)
        assert not legend._title_label.isVisible()


# ── Draggable overlay ──────────────────────────────────────────────────────


class TestLegendDrag:
    """Legend overlay must be repositionable by click-dragging."""

    def test_drag_moves_widget(self, qtbot) -> None:
        parent = QWidget()
        parent.resize(600, 500)
        qtbot.addWidget(parent)

        legend = RasterLegendWidget(parent)
        legend.resize(200, 150)
        legend.move(10, 10)
        legend.show()

        initial_pos = QPoint(legend.pos())

        # Simulate drag: press at global (110, 110), move to global (160, 140)
        legend.mousePressEvent(_make_press(QPoint(5, 5), QPoint(110, 110)))
        legend.mouseMoveEvent(_make_move(QPoint(5, 5), QPoint(160, 140)))
        legend.mouseReleaseEvent(_make_release(QPoint(5, 5), QPoint(160, 140)))

        assert legend.pos() != initial_pos, "Widget did not move during drag"
        assert legend.pos().x() == initial_pos.x() + 50
        assert legend.pos().y() == initial_pos.y() + 30

    def test_drag_clamped_to_parent_right_edge(self, qtbot) -> None:
        parent = QWidget()
        parent.resize(300, 300)
        qtbot.addWidget(parent)

        legend = RasterLegendWidget(parent)
        legend.resize(100, 100)
        legend.move(10, 10)
        legend.show()

        # Try to drag far past the right edge (parent width 300, legend width 100 → max x = 200)
        legend.mousePressEvent(_make_press(QPoint(5, 5), QPoint(100, 100)))
        legend.mouseMoveEvent(_make_move(QPoint(5, 5), QPoint(1000, 100)))

        assert legend.pos().x() <= 300 - 100, "Widget escaped right edge of parent"

    def test_drag_clamped_to_parent_bottom_edge(self, qtbot) -> None:
        parent = QWidget()
        parent.resize(300, 300)
        qtbot.addWidget(parent)

        legend = RasterLegendWidget(parent)
        legend.resize(100, 100)
        legend.move(10, 10)
        legend.show()

        legend.mousePressEvent(_make_press(QPoint(5, 5), QPoint(100, 100)))
        legend.mouseMoveEvent(_make_move(QPoint(5, 5), QPoint(100, 1000)))

        assert legend.pos().y() <= 300 - 100, "Widget escaped bottom edge of parent"

    def test_release_clears_drag_state(self, qtbot) -> None:
        parent = QWidget()
        parent.resize(600, 500)
        qtbot.addWidget(parent)

        legend = RasterLegendWidget(parent)
        legend.resize(200, 150)
        legend.move(10, 10)
        legend.show()

        legend.mousePressEvent(_make_press(QPoint(5, 5), QPoint(110, 110)))
        legend.mouseReleaseEvent(_make_release(QPoint(5, 5), QPoint(110, 110)))

        assert legend._drag_last_global is None


# ── Gradient bar tick marks ────────────────────────────────────────────────


class TestGradientBarTicks:
    """_GradientBarWidget must show three intermediate tick marks."""

    def _make_bar(self, qtbot) -> _GradientBarWidget:
        bar = _GradientBarWidget(
            gradient_stops=[
                {"position": 0.0, "color": "#0000FF"},
                {"position": 1.0, "color": "#FF0000"},
            ],
            stretch_min=0,
            stretch_max=1000,
            display_min=0.0,
            display_max=100.0,
            unit="%",
            format_str="{:.0f}",
            scale="linear",
        )
        qtbot.addWidget(bar)
        return bar

    def test_tick_labels_attribute_exists(self, qtbot) -> None:
        bar = self._make_bar(qtbot)
        assert hasattr(bar, "_tick_labels"), "_tick_labels attribute missing"

    def test_tick_labels_count_is_three(self, qtbot) -> None:
        bar = self._make_bar(qtbot)
        assert len(bar._tick_labels) == 3, f"Expected 3 tick labels, got {len(bar._tick_labels)}"

    def test_tick_labels_are_not_empty(self, qtbot) -> None:
        bar = self._make_bar(qtbot)
        for lbl in bar._tick_labels:
            assert lbl.text().strip(), "A tick label is empty"

    def test_tick_label_midpoint_shows_50pct_value(self, qtbot) -> None:
        """The middle tick (50 %) should display the midpoint of the display range."""
        bar = self._make_bar(qtbot)
        # display range 0–100 %, midpoint = 50 %
        mid_label = bar._tick_labels[1]
        assert "50" in mid_label.text(), (
            f"Middle tick should show ~50, got '{mid_label.text()}'"
        )

    def test_tick_labels_exist_without_display_mapping(self, qtbot) -> None:
        """Tick labels should render even without real-world display mapping."""
        bar = _GradientBarWidget(
            gradient_stops=[
                {"position": 0.0, "color": "#000000"},
                {"position": 1.0, "color": "#FFFFFF"},
            ],
            stretch_min=0,
            stretch_max=65535,
        )
        qtbot.addWidget(bar)
        assert hasattr(bar, "_tick_labels")
        assert len(bar._tick_labels) == 3


# ── 30 % height floor fix ─────────────────────────────────────────────────


class TestLegendInitialSizing:
    """Legend must be correctly sized on first show, not just after toggling."""

    def test_height_consistent_after_toggle(self, qtbot) -> None:
        """First Legend-button click must produce same height as a second click.

        The legend is NOT auto-shown when a layer is selected.  The user
        controls visibility via the toolbar toggle.  On first click the
        layout must already be settled so the displayed height is correct.
        """
        from src.gui.widgets.map_widget import MapWidget

        widget = MapWidget()
        qtbot.addWidget(widget)
        widget.show()
        widget.resize(800, 600)
        QApplication.processEvents()

        # Populate legend data; legend must NOT auto-show.
        widget._on_raster_layer_selected("n1", _discrete_meta("Test", n_classes=4))
        QApplication.processEvents()
        assert not widget.legend_overlay.isVisible(), (
            "Legend must not auto-show when a raster layer is selected."
        )

        # --- FIRST CLICK: user reveals the legend for the first time ---
        widget.btn_legend_toggle.click()
        QApplication.processEvents()
        assert widget.legend_overlay.isVisible(), "Legend must be visible after first click"
        h_first = widget.legend_overlay.height()

        # Hide and re-show.
        widget.btn_legend_toggle.click()
        QApplication.processEvents()
        widget.btn_legend_toggle.click()
        QApplication.processEvents()
        h_second = widget.legend_overlay.height()

        assert h_first == h_second, (
            f"Legend height differs: first click={h_first}px, second click={h_second}px. "
            "Sizing was not settled on the first Legend-toggle activation."
        )
        assert h_first > 50, (
            f"Legend height {h_first}px is suspiciously small — content not included."
        )

    def test_title_label_height_included_in_sizing(self, qtbot) -> None:
        """A named layer's title adds height; legend must not clip it."""
        from src.gui.widgets.map_widget import MapWidget

        widget = MapWidget()
        qtbot.addWidget(widget)
        widget.show()
        widget.resize(800, 600)
        QApplication.processEvents()

        # Named layer: title label is visible and adds height.
        # Legend is NOT auto-shown; user must toggle it.
        widget._on_raster_layer_selected("n1", _discrete_meta("My Named Layer", n_classes=2))
        QApplication.processEvents()
        widget.btn_legend_toggle.click()
        QApplication.processEvents()

        legend = widget.legend_overlay
        min_expected = (
            legend._header_label.sizeHint().height()
            + legend._title_label.sizeHint().height()
            + 20  # at least a sliver of content
        )
        assert legend.height() >= min_expected, (
            f"Legend height {legend.height()}px does not include title label "
            f"(expected >= {min_expected}px)"
        )

    """_position_legend_overlay must not inflate small legends to 30 % of viewport."""

    def test_small_legend_not_floored_to_30pct(self, qtbot) -> None:
        from src.gui.widgets.map_widget import MapWidget

        widget = MapWidget()
        qtbot.addWidget(widget)
        widget.show()
        widget.resize(800, 600)
        QApplication.processEvents()

        # 1-class discrete layer → very small ideal height (< 100 px).
        # Legend is NOT auto-shown; user must toggle it.
        layer_meta = _discrete_meta("Single Class", n_classes=1)
        widget._on_raster_layer_selected("n1", layer_meta)
        QApplication.processEvents()
        widget.btn_legend_toggle.click()
        QApplication.processEvents()

        legend = widget.legend_overlay
        assert legend.isVisible(), "Legend should be visible after toggle click"

        thirty_pct = int(widget.view.viewport().height() * 0.30)
        assert legend.height() < thirty_pct, (
            f"Legend height {legend.height()} should be < 30% of viewport ({thirty_pct}px)"
        )


# ── Toolbar legend toggle button ───────────────────────────────────────────


class TestLegendToggleButton:
    """MapWidget must have a legend visibility toggle button in its toolbar."""

    def test_btn_legend_toggle_exists(self, qtbot) -> None:
        from src.gui.widgets.map_widget import MapWidget

        widget = MapWidget()
        qtbot.addWidget(widget)
        assert hasattr(widget, "btn_legend_toggle"), "btn_legend_toggle attribute missing"

    def test_btn_legend_toggle_is_checkable(self, qtbot) -> None:
        from src.gui.widgets.map_widget import MapWidget

        widget = MapWidget()
        qtbot.addWidget(widget)
        assert widget.btn_legend_toggle.isCheckable()

    def test_toggle_button_hides_visible_legend(self, qtbot) -> None:
        from src.gui.widgets.map_widget import MapWidget

        widget = MapWidget()
        qtbot.addWidget(widget)
        widget.show()
        widget.resize(800, 600)
        QApplication.processEvents()

        # Populate data then manually show the legend via the toggle button.
        widget._on_raster_layer_selected("n1", _discrete_meta("Test"))
        QApplication.processEvents()
        widget.btn_legend_toggle.click()  # show
        QApplication.processEvents()
        assert widget.legend_overlay.isVisible(), "Legend must be visible after first click"

        # Second click hides it.
        widget.btn_legend_toggle.click()
        QApplication.processEvents()
        assert not widget.legend_overlay.isVisible()

    def test_toggle_button_reshows_hidden_legend(self, qtbot) -> None:
        from src.gui.widgets.map_widget import MapWidget

        widget = MapWidget()
        qtbot.addWidget(widget)
        widget.show()
        widget.resize(800, 600)
        QApplication.processEvents()

        widget._on_raster_layer_selected("n1", _discrete_meta("Test"))
        QApplication.processEvents()

        # Show, hide, show again.
        widget.btn_legend_toggle.click()  # show
        QApplication.processEvents()
        assert widget.legend_overlay.isVisible()

        widget.btn_legend_toggle.click()  # hide
        QApplication.processEvents()
        assert not widget.legend_overlay.isVisible()

        widget.btn_legend_toggle.click()  # re-show
        QApplication.processEvents()
        assert widget.legend_overlay.isVisible()

    def test_toggle_button_not_auto_checked_on_layer_select(self, qtbot) -> None:
        """Selecting a raster layer must NOT auto-check the toggle button.

        The user controls legend visibility; it should never be forced on.
        """
        from src.gui.widgets.map_widget import MapWidget

        widget = MapWidget()
        qtbot.addWidget(widget)

        assert not widget.btn_legend_toggle.isChecked()

        widget._on_raster_layer_selected("n1", _discrete_meta("Test"))
        QApplication.processEvents()
        assert not widget.btn_legend_toggle.isChecked(), (
            "btn_legend_toggle must NOT be auto-checked when a raster layer is selected."
        )

    def test_toggle_button_unchecked_when_layer_deselected(self, qtbot) -> None:
        """Deselecting a layer hides the legend and unchecks the button."""
        from src.gui.widgets.map_widget import MapWidget

        widget = MapWidget()
        qtbot.addWidget(widget)
        widget.show()
        widget.resize(800, 600)
        QApplication.processEvents()

        widget._on_raster_layer_selected("n1", _discrete_meta("Test"))
        QApplication.processEvents()
        # Manually show the legend first.
        widget.btn_legend_toggle.click()
        QApplication.processEvents()
        assert widget.btn_legend_toggle.isChecked()

        # Deselecting the layer should hide the overlay and uncheck the button.
        widget._on_raster_layer_selected(None, None)
        QApplication.processEvents()
        assert not widget.legend_overlay.isVisible()
        assert not widget.btn_legend_toggle.isChecked()
