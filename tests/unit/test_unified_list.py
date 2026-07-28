from unittest.mock import patch

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QMessageBox

from src.core.entities import Entity
from src.core.events import Event
from src.gui.widgets.unified_list import UnifiedListWidget


@pytest.fixture
def unified_list(qtbot):
    widget = UnifiedListWidget()
    qtbot.addWidget(widget)
    # widget.show()
    return widget


def test_init(unified_list):
    model = unified_list._proxy_model
    assert model.rowCount() == 0
    assert not unified_list.empty_state.isHidden()
    # Check default filter
    assert unified_list.filter_combo.currentText() == "All Items"


def test_set_data(unified_list):
    events = [Event(id="e1", name="Event 1", lore_date=10.0)]
    entities = [Entity(id="n1", name="Entity 1", type="Person")]

    unified_list.set_data(events, entities)

    model = unified_list._proxy_model
    assert model.rowCount() == 2
    assert unified_list.empty_state.isHidden()

    # Check items - get data from model
    index0 = model.index(0, 0)
    text0 = model.data(index0, Qt.ItemDataRole.DisplayRole)
    assert "Entity 1" in text0

    # Map to source for custom roles
    source_index0 = model.mapToSource(index0)
    source_model = model.sourceModel()
    assert source_model.data(source_index0, source_model.ItemIdRole) == "n1"
    assert source_model.data(source_index0, source_model.ItemTypeRole) == "entity"

    index1 = model.index(1, 0)
    text1 = model.data(index1, Qt.ItemDataRole.DisplayRole)
    assert "Event 1" in text1

    source_index1 = model.mapToSource(index1)
    assert source_model.data(source_index1, source_model.ItemIdRole) == "e1"
    assert source_model.data(source_index1, source_model.ItemTypeRole) == "event"


def test_filtering(unified_list):
    events = [Event(id="e1", name="Event 1", lore_date=10.0)]
    entities = [Entity(id="n1", name="Entity 1", type="Person")]
    unified_list.set_data(events, entities)

    model = unified_list._proxy_model

    # Filter Events Only
    unified_list.filter_combo.setCurrentText("Events Only")
    assert model.rowCount() == 1
    text = model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole)
    assert "Event 1" in text

    # Filter Entities Only
    unified_list.filter_combo.setCurrentText("Entities Only")
    assert model.rowCount() == 1
    text = model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole)
    assert "Entity 1" in text

    # Filter All
    unified_list.filter_combo.setCurrentText("All Items")
    assert model.rowCount() == 2


def test_selection_signal(unified_list, qtbot):
    events = [Event(id="e1", name="Event 1", lore_date=10.0)]
    unified_list.set_data(events, [])

    with qtbot.waitSignal(unified_list.item_selected) as blocker:
        model = unified_list._proxy_model
        unified_list.list_widget.setCurrentIndex(model.index(0, 0))

    assert blocker.args == ["event", "e1"]
    assert unified_list.btn_delete.isEnabled()


def test_delete_signal(unified_list, qtbot):
    events = [Event(id="e1", name="Event 1", lore_date=10.0)]
    unified_list.set_data(events, [])

    model = unified_list._proxy_model
    unified_list.list_widget.setCurrentIndex(model.index(0, 0))

    with patch(
        "PySide6.QtWidgets.QMessageBox.warning",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        with qtbot.waitSignal(unified_list.delete_requested) as blocker:
            unified_list.btn_delete.click()

    assert blocker.args == ["event", "e1"]


@pytest.mark.parametrize(
    ("events", "entities", "expected"),
    [
        ([Event(id="e1", name="Event 1", lore_date=10.0)], [], ["event", "e1"]),
        ([], [Entity(id="n1", name="Entity 1", type="Person")], ["entity", "n1"]),
    ],
)
def test_context_menu_delete_signal(
    unified_list, qtbot, monkeypatch, events, entities, expected
):
    """The context menu deletes the event or entity that was right-clicked."""
    unified_list.set_data(events, entities)
    unified_list.show()
    index = unified_list._proxy_model.index(0, 0)
    position = unified_list.list_widget.visualRect(index).center()

    def choose_delete(menu, _position):
        return next(action for action in menu.actions() if action.text() == "Delete")

    with (
        monkeypatch.context() as menu_patch,
        patch(
            "src.gui.widgets.unified_list.AutoClosingMessageBox.exec",
            return_value=QMessageBox.StandardButton.Ok,
        ),
        qtbot.waitSignal(unified_list.delete_requested) as blocker,
    ):
        menu_patch.setattr(
            unified_list,
            "_execute_context_menu",
            choose_delete,
        )
        unified_list._show_context_menu(position)

    assert blocker.args == expected


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


def test_deselect_on_empty_click(unified_list, qtbot):
    """Test that clicking on empty space deselects the current item."""
    unified_list.show()

    # Setup data
    events = [Event(id="e1", name="Event 1", lore_date=10.0)]
    unified_list.set_data(events, [])

    # Select the first item
    model = unified_list._proxy_model
    index = model.index(0, 0)
    unified_list.list_widget.setCurrentIndex(index)

    assert unified_list.list_widget.currentIndex().isValid()
    # assert len(unified_list.list_widget.selectedIndexes()) > 0

    # Simulate clicking on empty space
    # We need to find a point that is definitely not on an item
    viewport = unified_list.list_widget.viewport()
    item_rect = unified_list.list_widget.visualRect(index)

    # Click below the item
    click_point = QPoint(item_rect.center().x(), item_rect.bottom() + 20)

    # Ensure the point is within the viewport but not on the item
    # assert viewport.rect().contains(click_point)
    # assert not item_rect.contains(click_point)

    qtbot.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=click_point)

    # Assert selection is cleared
    assert not unified_list.list_widget.currentIndex().isValid()
    assert len(unified_list.list_widget.selectedIndexes()) == 0
