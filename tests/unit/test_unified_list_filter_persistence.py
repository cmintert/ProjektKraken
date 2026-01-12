import pytest

from src.core.events import Event
from src.gui.widgets.unified_list import UnifiedListWidget


class TestUnifiedListFilterPersistence:
    @pytest.fixture
    def list_widget(self, qtbot):
        widget = UnifiedListWidget()
        qtbot.addWidget(widget)
        return widget

    def test_filter_persists_after_set_data(self, list_widget, qtbot):
        """
        Verify that search filter persists and is applied after set_data (reload).
        """
        # 1. Setup initial data
        e1 = Event(id="e1", name="Alpha Event", lore_date=100)
        e2 = Event(id="e2", name="Beta Event", lore_date=200)
        list_widget.set_data([e1, e2], [])

        # 2. Apply Filter (Search "Alpha")
        list_widget.search_bar.setText("Alpha")

        # Verify filtering worked
        assert list_widget.list_widget.count() == 1
        assert list_widget.list_widget.item(0).text().endswith("Alpha Event")

        # 3. Simulate "Save" -> Reload Data
        # User changes e2 (Beta) -> e2_updated
        e2_updated = Event(id="e2", name="Beta Event Updated", lore_date=200)

        # set_data called with new list
        list_widget.set_data([e1, e2_updated], [])

        # 4. Verify Filter is STILL applied
        # Should still only show Alpha
        # If bug exists: might show both (filter lost)
        assert list_widget.list_widget.count() == 1
        assert list_widget.list_widget.item(0).text().endswith("Alpha Event")

        # Verify search bar text is preserved
        assert list_widget.search_bar.text() == "Alpha"

    def test_select_filtered_item_preserves_filter_visuals(self, list_widget, qtbot):
        """
        Verify that selecting a filtered-out item via select_item:
        1. Clears selection (due to our previous fix).
        2. DOES NOT reset the filter (list should not show hidden items).
        """
        e1 = Event(id="e1", name="Alpha", lore_date=100)
        e2 = Event(id="e2", name="Beta", lore_date=200)
        list_widget.set_data([e1, e2], [])

        # Filter "Alpha"
        list_widget.search_bar.setText("Alpha")
        assert list_widget.list_widget.count() == 1

        # Try to select filtered-out "Beta" (e2)
        list_widget.select_item("event", "e2")

        # Assert selection is cleared (Fix 1 verification)
        assert len(list_widget.list_widget.selectedItems()) == 0

        # Assert filter is still active (Fix 2 check)
        # Should still only count 1 item (Alpha)
        assert list_widget.list_widget.count() == 1
        assert list_widget.list_widget.item(0).text().endswith("Alpha")
