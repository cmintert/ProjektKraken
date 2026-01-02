import pytest
from PySide6.QtWidgets import QLabel

from src.gui.widgets.relation_item_widget import RelationItemWidget


@pytest.fixture
def relation_item(qtbot):
    """Fixture for RelationItemWidget."""
    widget = RelationItemWidget(
        label="→ Gandalf [involved]",
        target_id="id-1",
        target_name="Gandalf",
    )
    qtbot.addWidget(widget)
    return widget


def test_widget_init(relation_item):
    """Test widget initialization."""
    assert relation_item.label.text() == "→ Gandalf [involved]"


def test_attributes_display(qtbot):
    """Test that attributes are displayed in the widget."""
    attributes = {"weight": 0.8, "confidence": 0.5}
    widget = RelationItemWidget(
        label="→ Frodo [involved]",
        target_id="id-2",
        target_name="Frodo",
        attributes=attributes,
    )
    qtbot.addWidget(widget)

    # Find the attribute label (it should be the second label added)
    # The first one is self.label.
    # We expect the implementation to add a new QLabel for attributes.

    labels = widget.findChildren(QLabel)
    assert len(labels) == 2

    attr_label = labels[1]
    text = attr_label.text()

    assert "weight=0.8" in text
    assert "confidence=0.5" in text
