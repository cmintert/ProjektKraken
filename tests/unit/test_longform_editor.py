from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from src.gui.widgets.longform_editor import (
    LongformContentWidget,
    LongformEditorWidget,
    LongformOutlineWidget,
)


@pytest.fixture
def content_widget(qtbot):
    widget = LongformContentWidget()
    qtbot.addWidget(widget)
    return widget


def test_load_content_populates_text(content_widget):
    """Test that content is actually loaded."""
    sequence = [
        {
            "table": "events",
            "id": "1",
            "name": "Chapter 1",
            "heading_level": 1,
            "content": "Content 1",
            "meta": {},
        },
    ]
    content_widget.load_content(sequence)
    assert "Chapter 1" in content_widget.toPlainText()
    assert "Content 1" in content_widget.toPlainText()


def test_load_content_injects_anchors(content_widget):
    """Test that HTML anchors are injected for navigation."""
    sequence = [
        {
            "table": "events",
            "id": "1",
            "name": "Chapter 1",
            "heading_level": 1,
            "content": "Content 1",
            "meta": {},
        },
        {
            "table": "events",
            "id": "2",
            "name": "Chapter 2",
            "heading_level": 1,
            "content": "Content 2",
            "meta": {},
        },
    ]
    content_widget.load_content(sequence)

    html = content_widget.toHtml()
    # Check for anchors. Note: QWidget might normalize HTML, but anchors should persist as named anchors or IDs.
    # We check for simplest possible representations.
    assert 'name="item-0"' in html or 'id="item-0"' in html
    assert 'name="item-1"' in html or 'id="item-1"' in html


def test_scroll_to_item_calls_scroll_to_anchor(content_widget):
    """Test that scroll_to_item calls scrollToAnchor with correct name."""
    sequence = [
        {
            "table": "events",
            "id": "1",
            "name": "Chapter 1",
            "heading_level": 1,
            "content": "Content 1",
            "meta": {},
        },
        {
            "table": "events",
            "id": "2",
            "name": "Chapter 2",
            "heading_level": 1,
            "content": "Content 2",
            "meta": {},
        },
    ]
    content_widget.load_content(sequence)

    # Mock scrollToAnchor
    with patch.object(content_widget, "scrollToAnchor") as mock_scroll:
        # Scroll to second item
        content_widget.scroll_to_item(1)

        # Check call
        # Check call
        mock_scroll.assert_called_with("item-1")


@pytest.fixture
def outline_widget(qtbot):
    widget = LongformOutlineWidget()
    qtbot.addWidget(widget)
    return widget


def test_outline_load_sequence(outline_widget):
    sequence = [
        {
            "table": "events",
            "id": "1",
            "name": "Event 1",
            "meta": {"title_override": "Title 1"},
        },
        {
            "table": "entities",
            "id": "2",
            "name": "Entity 1",
            "meta": {},
            "heading_level": 1,
        },
    ]
    outline_widget.load_sequence(sequence)

    assert outline_widget.topLevelItemCount() == 2
    item1 = outline_widget.topLevelItem(0)
    assert item1.text(0) == "Title 1"

    # Check meta storage
    table, row_id, meta = outline_widget._item_meta[id(item1)]
    assert table == "events"
    assert row_id == "1"


def test_outline_promote_shortcut(outline_widget, qtbot):
    # Setup item
    sequence = [{"table": "events", "id": "1", "name": "Event 1", "meta": {}}]
    outline_widget.load_sequence(sequence)
    item = outline_widget.topLevelItem(0)
    outline_widget.setCurrentItem(item)

    # Spy on signal
    with qtbot.waitSignal(outline_widget.item_promoted) as blocker:
        # Simulate Ctrl+[
        qtbot.keyClick(outline_widget, Qt.Key_BracketLeft, modifier=Qt.ControlModifier)

    assert blocker.signal_triggered
    args = blocker.args
    assert args[0] == "events"
    assert args[1] == "1"


def test_outline_drag_mime_data(outline_widget):
    sequence = [{"table": "events", "id": "ev1", "name": "Event 1", "meta": {}}]
    outline_widget.load_sequence(sequence)
    item = outline_widget.topLevelItem(0)
    outline_widget.setCurrentItem(item)

    # Mock QDrag.exec to avoid blocking
    with patch("PySide6.QtGui.QDrag.exec", return_value=Qt.CopyAction):
        outline_widget.startDrag(Qt.CopyAction)

        # We can't easily inspect the mime data passed to QDrag inside startDrag
        # unless we mock QMimeData or QDrag.setMimeData.
        # But we can verify it runs without error.
        # To truly verify mime data, we'd need to mock QDrag and capture setMimeData args.
        pass


@patch("src.gui.widgets.longform_editor.QDrag")
def test_outline_drag_content(mock_qdrag, outline_widget):
    sequence = [{"table": "events", "id": "ev1", "name": "Event 1", "meta": {}}]
    outline_widget.load_sequence(sequence)
    item = outline_widget.topLevelItem(0)
    outline_widget.setCurrentItem(item)

    outline_widget.startDrag(Qt.CopyAction)

    # Verify dragging happened
    mock_qdrag.assert_called()
    drag_instance = mock_qdrag.return_value
    drag_instance.setMimeData.assert_called()

    # Inspect Mime Data
    mime_data = drag_instance.setMimeData.call_args[0][0]
    from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

    assert mime_data.hasFormat(KRAKEN_ITEM_MIME_TYPE)


@pytest.fixture
def editor_widget(qtbot):
    widget = LongformEditorWidget()
    qtbot.addWidget(widget)
    return widget


def test_editor_initialization(editor_widget):
    assert editor_widget.outline is not None
    assert editor_widget.content is not None
    assert editor_widget.findChild(LongformOutlineWidget) is not None
    assert editor_widget.findChild(LongformContentWidget) is not None


def test_editor_refresh_signal(editor_widget, qtbot):
    # Find refresh action (it's in toolbar)
    # We can trigger it via signal spy on the widget's signal if we can't easily find the action
    # Triggering the action via code:
    actions = editor_widget.findChildren(QAction)
    refresh_action = next((a for a in actions if a.text() == "Refresh"), None)
    assert refresh_action is not None

    with qtbot.waitSignal(editor_widget.refresh_requested):
        refresh_action.trigger()


def test_editor_selection_sync(editor_widget, qtbot):
    sequence = [
        {"table": "events", "id": "1", "name": "E1", "meta": {}, "heading_level": 1}
    ]
    editor_widget.load_sequence(sequence)

    with patch.object(editor_widget.content, "scroll_to_item") as mock_scroll:
        # Simulate outline selection
        editor_widget._on_item_selected("events", "1")

        mock_scroll.assert_called_with(0)
