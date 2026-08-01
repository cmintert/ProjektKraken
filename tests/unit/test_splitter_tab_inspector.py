"""Regression tests for transactional inspector-tab movement."""

from unittest.mock import MagicMock

from PySide6.QtCore import QMimeData, QPoint
from PySide6.QtWidgets import QLabel

from src.gui.widgets.splitter_tab_inspector import (
    INSPECTOR_TAB_MIME_TYPE,
    DraggableTabWidget,
    _decode_source_index,
    _move_tab,
)


def _tab_mime(index: object) -> QMimeData:
    mime = QMimeData()
    mime.setData(INSPECTOR_TAB_MIME_TYPE, str(index).encode())
    return mime


def test_move_tab_preserves_widget_metadata(qtbot):
    """A validated move transfers the same widget and its tab metadata."""
    source = DraggableTabWidget()
    target = DraggableTabWidget()
    qtbot.addWidget(source)
    qtbot.addWidget(target)
    content = QLabel("Content")
    source.addTab(content, "Lore")
    source.setTabToolTip(0, "Lore tooltip")
    source.setTabEnabled(0, False)

    assert _move_tab(source, target, 0, 0) is True

    assert source.count() == 0
    assert target.widget(0) is content
    assert target.tabText(0) == "Lore"
    assert target.tabToolTip(0) == "Lore tooltip"
    assert target.isTabEnabled(0) is False


def test_move_tab_rejects_stale_index_without_mutation(qtbot):
    """A stale drag index cannot remove or orphan the source widget."""
    source = DraggableTabWidget()
    target = DraggableTabWidget()
    qtbot.addWidget(source)
    qtbot.addWidget(target)
    content = QLabel("Content")
    source.addTab(content, "Lore")

    assert _move_tab(source, target, 5, 0) is False
    assert source.count() == 1
    assert source.widget(0) is content
    assert target.count() == 0


def test_body_drop_without_splitter_keeps_source_tab(qtbot):
    """A detached drop target must reject before removing the source tab."""
    source = DraggableTabWidget()
    target = DraggableTabWidget()
    qtbot.addWidget(source)
    qtbot.addWidget(target)
    content = QLabel("Content")
    source.addTab(content, "Lore")
    target.resize(300, 200)

    event = MagicMock()
    event.mimeData.return_value = _tab_mime(0)
    event.source.return_value = source.tabBar()
    event.position.return_value.toPoint.return_value = QPoint(10, 100)

    target.dropEvent(event)

    event.ignore.assert_called_once()
    assert source.count() == 1
    assert source.widget(0) is content
    assert target.count() == 0


def test_decode_source_index_rejects_malformed_data():
    """Malformed drag payloads are rejected without raising."""
    assert _decode_source_index(_tab_mime("not-an-index")) is None
