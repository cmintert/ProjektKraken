import pytest
from PySide6.QtCore import Qt

from src.core.entities import Entity
from src.core.events import Event
from src.gui.widgets.unified_list import UnifiedListWidget


@pytest.fixture
def unified_list(qtbot):
    widget = UnifiedListWidget()
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_init(unified_list):
    assert unified_list.list_widget.count() == 0
    assert unified_list.empty_label.isVisible()
    # Check default filter
    assert unified_list.filter_combo.currentText() == "All Items"


def test_set_data(unified_list):
    events = [Event(id="e1", name="Event 1", lore_date=10.0)]
    entities = [Entity(id="n1", name="Entity 1", type="Person")]

    unified_list.set_data(events, entities)

    assert unified_list.list_widget.count() == 2
    assert unified_list.empty_label.isHidden()

    # Check items
    # Entity should be first based on logic (Entities loop first)
    item0 = unified_list.list_widget.item(0)
    assert "Entity 1" in item0.text()
    assert item0.data(Qt.UserRole) == "n1"
    assert item0.data(Qt.UserRole + 1) == "entity"

    item1 = unified_list.list_widget.item(1)
    assert "Event 1" in item1.text()
    assert item1.data(Qt.UserRole) == "e1"
    assert item1.data(Qt.UserRole + 1) == "event"


def test_filtering(unified_list):
    events = [Event(id="e1", name="Event 1", lore_date=10.0)]
    entities = [Entity(id="n1", name="Entity 1", type="Person")]
    unified_list.set_data(events, entities)

    # Filter Events Only
    unified_list.filter_combo.setCurrentText("Events Only")
    assert unified_list.list_widget.count() == 1
    assert "Event 1" in unified_list.list_widget.item(0).text()

    # Filter Entities Only
    unified_list.filter_combo.setCurrentText("Entities Only")
    assert unified_list.list_widget.count() == 1
    assert "Entity 1" in unified_list.list_widget.item(0).text()

    # Filter All
    unified_list.filter_combo.setCurrentText("All Items")
    assert unified_list.list_widget.count() == 2


def test_selection_signal(unified_list, qtbot):
    events = [Event(id="e1", name="Event 1", lore_date=10.0)]
    unified_list.set_data(events, [])

    with qtbot.waitSignal(unified_list.item_selected) as blocker:
        unified_list.list_widget.setCurrentRow(0)

    assert blocker.args == ["event", "e1"]
    assert unified_list.btn_delete.isEnabled()


def test_delete_signal(unified_list, qtbot):
    events = [Event(id="e1", name="Event 1", lore_date=10.0)]
    unified_list.set_data(events, [])
    unified_list.list_widget.setCurrentRow(0)

    with qtbot.waitSignal(unified_list.delete_requested) as blocker:
        unified_list.btn_delete.click()

    assert blocker.args == ["event", "e1"]


def test_create_signals(unified_list, qtbot):
    # Test Create Event
    with qtbot.waitSignal(unified_list.create_event_requested):
        # Trigger action manually since menu is harder to click in test
        for action in unified_list.new_menu.actions():
            if action.text() == "Create Event":
                action.trigger()
                break

    # Test Create Entity
    with qtbot.waitSignal(unified_list.create_entity_requested):
        for action in unified_list.new_menu.actions():
            if action.text() == "Create Entity":
                action.trigger()
                break


def test_refresh_signal(unified_list, qtbot):
    with qtbot.waitSignal(unified_list.refresh_requested):
        unified_list.btn_refresh.click()
