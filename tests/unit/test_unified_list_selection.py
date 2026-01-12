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
        assert len(list_widget.list_widget.selectedItems()) == 1
        assert (
            list_widget.list_widget.selectedItems()[0].data(Qt.ItemDataRole.UserRole)
            == "e1"
        )

        # 2. Filter to "Entities Only" so event is hidden
        list_widget.filter_combo.setCurrentText("Entities Only")
        # List should now show only entity1
        # Selection restoration in _render_list might have failed, which is expected behavior for "hiding"
        # But we want to test the EXPLICIT jump behavior.

        # 3. Simulate the bug scenario:
        # User saves the event (which triggers a reload/reselect in main window)
        # MainWindow calls select_item("event", "e1")
        # BUT the filter is still "Entities Only"

        # NOTE: logic in select_item attempts to switch filter if it detects a mismatch.
        # "if item_type == 'event' and current_filter == 'Entities Only': should_switch = True"

        # So, to test the "clear selection" path, we need a scenario where it DOESN'T switch
        # but still can't find it (e.g. search filter).

        # Let's try search filter
        list_widget.filter_combo.setCurrentText("All Items")
        list_widget.search_bar.setText("Entity")  # Matches Entity 1, hides Event 1

        # Verify event is gone from list
        items = [
            list_widget.list_widget.item(i).text()
            for i in range(list_widget.list_widget.count())
        ]
        assert any("Entity 1" in t for t in items)
        assert not any("Event 1" in t for t in items)

        # Pre-condition: Select entity to have *some* selection (simulating jump target)
        list_widget.select_item("entity", "ent1")
        assert len(list_widget.list_widget.selectedItems()) == 1

        # 4. Try to select the hidden Event
        list_widget.select_item("event", "e1")

        # 5. Assert Selection is CLEARED (Fix check)
        # Without fix, it might have stayed on "ent1" or just done nothing (if not cleared)
        assert len(list_widget.list_widget.selectedItems()) == 0

    def test_selection_switches_filter_if_needed(self, list_widget, qtbot):
        """
        Verify that select_item DOES switch filter if it's a simple Type mismatch.
        """
        event1 = Event(id="e1", name="Event 1", lore_date=100)
        list_widget.set_data([event1], [])

        # Set to Entities Only
        list_widget.filter_combo.setCurrentText("Entities Only")
        assert list_widget.list_widget.count() == 0

        # Try to select event
        list_widget.select_item("event", "e1")

        # Should have switched to All Items (or Events Only) and selected it
        assert list_widget.filter_combo.currentText() == "All Items"
        assert len(list_widget.list_widget.selectedItems()) == 1
