import pytest
from PySide6.QtCore import QPoint, Qt

from src.gui.widgets.longform.content import LongformContentWidget


@pytest.fixture
def content_widget(qtbot):
    widget = LongformContentWidget()
    qtbot.addWidget(widget)
    return widget


def test_card_click_emits_item_selected(content_widget, qtbot):
    """Test that clicking on a card table emits item_selected."""
    sequence = [
        {
            "table": "events",
            "id": "evt-123",
            "name": "Chapter 1",
            "heading_level": 1,
            "content": "Content of the first card.",
            "meta": {},
        },
    ]
    content_widget.load_content(sequence)
    content_widget.resize(600, 400)
    content_widget.show()
    qtbot.waitExposed(content_widget)

    with qtbot.waitSignal(content_widget.item_selected, timeout=5000) as blocker:
        # Click in the middle of where the card should be
        # (50, 100) should be inside the first card's table
        qtbot.mouseClick(
            content_widget.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(50, 100)
        )

    assert blocker.args == ["events", "evt-123"]

    assert blocker.args == ["events", "evt-123"]


def test_title_link_navigation(content_widget, qtbot):
    """Test that clicking the title link also works via anchorClicked."""
    sequence = [
        {
            "table": "entities",
            "id": "ent-456",
            "name": "Character Name",
            "heading_level": 1,
            "content": "Description",
            "meta": {},
        },
    ]
    content_widget.load_content(sequence)

    # In LongformContentWidget, titles are wrapped in <a href="id:ent-456">
    # anchorClicked is caught by _on_anchor_clicked which emits link_clicked

    with qtbot.waitSignal(content_widget.link_clicked) as blocker:
        from PySide6.QtCore import QUrl

        content_widget._on_anchor_clicked(QUrl("id:ent-456"))

    assert blocker.args == ["id:ent-456"]
