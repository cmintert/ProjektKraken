"""
Unit tests for widget size hints to prevent layout regressions.
"""

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWidget

from src.gui.widgets.unified_list import UnifiedListWidget
from src.gui.widgets.event_list import EventListWidget
from src.gui.widgets.entity_list import EntityListWidget
from src.gui.widgets.gallery_widget import GalleryWidget
from src.gui.widgets.compact_date_widget import CompactDateWidget
from src.gui.widgets.compact_duration_widget import CompactDurationWidget


@pytest.mark.parametrize(
    "widget_class, min_w, min_h",
    [
        (UnifiedListWidget, 250, 200),
        (EventListWidget, 250, 200),
        (EntityListWidget, 250, 200),
        (GalleryWidget, 250, 150),
        (CompactDateWidget, 250, 72),
        (CompactDurationWidget, 250, 72),
    ],
)
def test_widget_minimum_size_hints(qtbot, widget_class, min_w, min_h):
    """
    Ensure widgets report correct minimum size hints to prevent dock collapse.
    """
    # Create widget with a parent to simulate real usage if needed,
    # but for sizeHint checks, unparented is usually fine or valid.
    # Some widgets require args in __init__, let's handle them.

    if widget_class == GalleryWidget:
        # GalleryWidget needs a main_window with a worker and signals
        from PySide6.QtCore import QObject, Signal

        class MockWorker(QObject):
            attachments_loaded = Signal(str, str, list)
            command_finished = Signal(object)

        class MockMainWindow:
            def __init__(self):
                self.worker = MockWorker()

        widget = widget_class(MockMainWindow())
    else:
        widget = widget_class()

    qtbot.addWidget(widget)

    hint = widget.minimumSizeHint()
    assert isinstance(hint, QSize)
    assert (
        hint.width() >= min_w
    ), f"{widget_class.__name__} min width {hint.width()} < {min_w}"
    assert (
        hint.height() >= min_h
    ), f"{widget_class.__name__} min height {hint.height()} < {min_h}"


@pytest.mark.parametrize(
    "widget_class",
    [
        UnifiedListWidget,
        EventListWidget,
        EntityListWidget,
        GalleryWidget,
        CompactDateWidget,
        CompactDurationWidget,
    ],
)
def test_widget_size_hints_valid(qtbot, widget_class):
    """
    Ensure widgets report a valid preferred size hint.
    """
    if widget_class == GalleryWidget:
        # GalleryWidget needs a main_window with a worker and signals
        from PySide6.QtCore import QObject, Signal

        class MockWorker(QObject):
            attachments_loaded = Signal(str, str, list)
            command_finished = Signal(object)

        class MockMainWindow:
            def __init__(self):
                self.worker = MockWorker()

        widget = widget_class(MockMainWindow())
    else:
        widget = widget_class()

    qtbot.addWidget(widget)

    hint = widget.sizeHint()
    assert isinstance(hint, QSize)
    assert hint.isValid()
    assert hint.width() > 0
    assert hint.height() > 0
