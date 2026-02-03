import pytest
from PySide6.QtCore import Qt

from src.core.entities import Entity
from src.core.events import Event
from src.gui.widgets.unified_list import UnifiedListWidget


class TestUnifiedListSelection:
    @pytest.fixture
    def list_widget(self, qtbot):
        widget = UnifiedListWidget()
        qtbot.addWidget(widget)
        return widget

    def test_selection_clears_when_item_not_found(self, list_widget, qtbot):
        """
        Verify that select_item clears the selection if the target item
        is filtered out or does not exist.
        """
        # Setup data
        event1 = Event(id="e1", name="Event 1", lore_date=100)
        entity1 = Entity(id="ent1", name="Entity 1", type="Character")
        list_widget.set_data([event1], [entity1])

        # 1. Select the event (should succeed)
        list_widget.select_item("event", "e1")
        selection_model = list_widget.list_widget.selectionModel()
        assert len(selection_model.selectedIndexes()) == 1
        
        # Verify selected item is the event
        selected_index = selection_model.selectedIndexes()[0]
        source_index = list_widget._proxy_model.mapToSource(selected_index)
        item_id = list_widget._model.data(source_index, list_widget._model.ItemIdRole)
        assert item_id == "e1"

        # 2. Filter to "Entities Only" so event is hidden
        list_widget.filter_combo.setCurrentText("Entities Only")

        # 3. Use search filter to hide event
        list_widget.filter_combo.setCurrentText("All Items")
        list_widget.search_bar.setText("Entity")  # Matches Entity 1, hides Event 1

        # Verify event is gone from list via proxy model
        model = list_widget._proxy_model
        visible_count = model.rowCount()
        visible_items = []
        for i in range(visible_count):
            index = model.index(i, 0)
            text = model.data(index, Qt.ItemDataRole.DisplayRole)
            visible_items.append(text)
        
        assert any("Entity 1" in t for t in visible_items)
        assert not any("Event 1" in t for t in visible_items)

        # Pre-condition: Select entity to have *some* selection
        list_widget.select_item("entity", "ent1")
        assert len(selection_model.selectedIndexes()) == 1

        # 4. Try to select the hidden Event
        list_widget.select_item("event", "e1")

        # 5. Assert Selection is CLEARED
        assert len(selection_model.selectedIndexes()) == 0

    def test_selection_switches_filter_if_needed(self, list_widget, qtbot):
        """
        Verify that select_item DOES switch filter if it's a simple Type mismatch.
        """
        event1 = Event(id="e1", name="Event 1", lore_date=100)
        list_widget.set_data([event1], [])

        # Set to Entities Only
        list_widget.filter_combo.setCurrentText("Entities Only")
        model = list_widget._proxy_model
        assert model.rowCount() == 0

        # Try to select event
        list_widget.select_item("event", "e1")

        # Should have switched to All Items and selected it
        assert list_widget.filter_combo.currentText() == "All Items"
        selection_model = list_widget.list_widget.selectionModel()
        assert len(selection_model.selectedIndexes()) == 1
