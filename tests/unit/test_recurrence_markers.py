"""Recurring circles identify actual dates using the ordinary Event paint grammar."""

import json
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QWidget

from src.core.events import Event
from src.core.recurrence import RECURRENCE_ATTRIBUTE, RecurrenceRule
from src.core.theme_manager import ThemeManager
from src.gui.widgets.timeline import TimelineWidget
from src.gui.widgets.timeline.occurrence_marker import OccurrenceMarker
from src.gui.widgets.timeline.temporal_geometry import TemporalGeometry
from src.gui.widgets.timeline.temporal_painter import paint_occurrence

pytestmark = pytest.mark.ci_fast


@pytest.mark.parametrize("date_x", [0, 12, 160, 315, 319])
def test_circle_stays_at_date_when_label_needs_edge_space(qtbot, date_x):
    parent = QWidget()
    qtbot.addWidget(parent)
    marker = OccurrenceMarker("New Year's Eve", "Year 1, December 31", parent)
    marker.place_at(date_x, 320)
    assert marker.x() + marker.anchor_x == date_x
    assert marker.geometry().left() >= 0
    assert marker.geometry().right() < 320
    if date_x > 270:
        assert marker.x() + marker._label_x < date_x


def test_shared_event_painter_defaults_to_diamond_and_supports_circle(qapp):
    samples = []
    for circle in (False, True):
        image = QImage(40, 40, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.translate(16, 16)
        kwargs = {"shape": "circle"} if circle else {}
        paint_occurrence(
            painter,
            TemporalGeometry("exact", -8, 8),
            QColor(Qt.GlobalColor.red),
            QColor(Qt.GlobalColor.red),
            **kwargs,
        )
        painter.end()
        samples.append(image.pixelColor(21, 21).alpha())
    assert samples[0] == 0
    assert samples[1] > 0


@pytest.mark.parametrize("theme", json.loads(Path("themes.json").read_text("utf-8")))
def test_circle_uses_event_identity_in_each_theme(qtbot, isolated_theme_manager, theme):
    manager = isolated_theme_manager
    manager.set_theme(theme, persist=False)
    parent = QWidget()
    qtbot.addWidget(parent)
    marker = OccurrenceMarker("Festival", "Year 1", parent)
    marker.place_at(100, 320)
    image = marker.grab().toImage()
    assert image.pixelColor(round(marker.anchor_x), 20) == QColor(
        ThemeManager().get_theme()["event_main"]
    )


def test_strip_pins_source_date_without_a_calendar_icon_button(qtbot):
    widget = TimelineWidget()
    qtbot.addWidget(widget)
    widget.resize(900, 400)
    widget.show()
    event = Event(
        "New Year's Eve",
        0,
        attributes={
            RECURRENCE_ATTRIBUTE: RecurrenceRule(
                frequency="days", interval=10000
            ).to_dict()
        },
    )
    widget.set_events([event])
    widget.view._apply_zoom(4)
    widget.view.center_on_date(0)
    strip = widget.view.recurrence_strip
    strip.refresh()
    marker = strip._buttons[0]
    expected_x = widget.view.mapFromScene(0, 0).x()
    assert isinstance(marker, OccurrenceMarker)
    assert marker.x() + marker.anchor_x == expected_x
    assert marker.icon().isNull()
