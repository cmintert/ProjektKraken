import pytest
from unittest.mock import patch
from src.gui.widgets.longform_editor import LongformContentWidget


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
        mock_scroll.assert_called_with("item-1")
