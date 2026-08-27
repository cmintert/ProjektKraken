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


def test_non_empty_payload_shows_state_changes_badge(qtbot):
    """A relation carrying state changes is visibly marked."""
    widget = RelationItemWidget(
        label="\u2192 Frodo [involved]",
        target_id="id-2",
        target_name="Frodo",
        attributes={"payload": {"attributes": {"status": "Missing"}}},
    )
    qtbot.addWidget(widget)

    assert widget.state_changes_badge.text() == "State changes"
    assert "target entity" in widget.state_changes_badge.toolTip()
    assert not hasattr(widget, "attr_label")


@pytest.mark.parametrize(
    "attributes",
    [
        {},
        {"weight": 0.8},
        {"payload": {}},
        {"payload": {"attributes": {}, "unset_attributes": []}},
    ],
)
def test_relation_without_effective_payload_has_no_badge(qtbot, attributes):
    """Ordinary attributes and empty payloads do not create a marker."""
    widget = RelationItemWidget(
        label="\u2192 Frodo [involved]",
        target_id="id-2",
        target_name="Frodo",
        attributes=attributes,
    )
    qtbot.addWidget(widget)

    assert not hasattr(widget, "state_changes_badge")


def test_explicit_description_clear_shows_state_changes_badge(qtbot):
    """An empty description is still an intentional state change."""
    widget = RelationItemWidget(
        label="\u2192 Frodo [involved]",
        target_id="id-2",
        target_name="Frodo",
        attributes={"payload": {"description": ""}},
    )
    qtbot.addWidget(widget)

    assert widget.state_changes_badge.text() == "State changes"
