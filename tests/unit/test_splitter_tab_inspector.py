"""Regression tests for transactional inspector-tab movement."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QMimeData, QPoint
from PySide6.QtWidgets import QLabel

from src.gui.widgets.splitter_tab_inspector import (
    INSPECTOR_TAB_MIME_TYPE,
    DraggableTabWidget,
    SplitterTabInspector,
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


@pytest.mark.ci_fast
@pytest.mark.parametrize("failure", ["reject", "raise", "partial"])
def test_failed_move_restores_source_and_metadata(qtbot, monkeypatch, failure):
    source = DraggableTabWidget()
    target = DraggableTabWidget()
    qtbot.addWidget(source)
    qtbot.addWidget(target)
    content = QLabel("Content")
    source.addTab(content, "Lore")
    source.setTabToolTip(0, "Retained tooltip")
    source.setTabEnabled(0, False)
    insert = target.insertTab

    def fail(*args):
        if failure == "reject":
            return -1
        if failure == "partial":
            insert(*args)
        raise RuntimeError("Rejected insertion")

    monkeypatch.setattr(target, "insertTab", fail)
    assert not _move_tab(source, target, 0, 0)
    assert source.widget(0) is content
    assert source.tabText(0) == "Lore"
    assert source.tabToolTip(0) == "Retained tooltip"
    assert not source.isTabEnabled(0)
    assert not target.count()


@pytest.mark.ci_fast
def test_move_between_independent_inspectors_is_rejected(qtbot):
    source = SplitterTabInspector()
    target = SplitterTabInspector()
    qtbot.addWidget(source)
    qtbot.addWidget(target)
    content = QLabel("Retained")
    source.add_tab(content, "Overview", section_id="overview")
    assert not _move_tab(source.main_tabs, target.main_tabs, 0, 0)
    source.activate_section_id("overview")
    assert source.main_tabs.currentWidget() is content
    assert not target.main_tabs.count()


@pytest.mark.ci_fast
def test_duplicate_destination_id_rejected_before_insertion(qtbot):
    inspector = SplitterTabInspector()
    qtbot.addWidget(inspector)
    content = QLabel("First")
    inspector.add_tab(content, "Overview", section_id="overview")
    with pytest.raises(ValueError, match="Duplicate"):
        inspector.add_tab(QLabel("Second", inspector), "Other", section_id="overview")
    assert inspector.main_tabs.count() == 1
    inspector.activate_section(content)
    assert inspector.main_tabs.currentWidget() is content
