import pytest
from PySide6.QtCore import Qt

from src.core.events import Event
from src.gui.widgets.unified_list import UnifiedListWidget


class TestUnifiedListAdvancedFiltering:
    @pytest.fixture
    def list_widget(self, qtbot):
        widget = UnifiedListWidget()
        qtbot.addWidget(widget)
        return widget

    def test_advanced_filter_logic(self, list_widget, qtbot):
        """
        Verify that _passes_advanced_filters correctly handles tags.
        """
        # Inject private method if not exposed, but ideally we test via public behavior
        # We will test via set_advanced_filter + set_data + visuals

        e1 = Event(name="In", lore_date=100, attributes={"_tags": ["A", "B"]})
        e2 = Event(name="Out", lore_date=200, attributes={"_tags": ["A"]})

        list_widget.set_data([e1, e2], [])

        model = list_widget._proxy_model

        # 1. Test Match All
        config = {"include": ["A", "B"], "include_mode": "all"}
        list_widget.set_advanced_filter(config)

        # Should only show e1
        assert model.rowCount() == 1
        text = model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole)
        assert "In" in text

        # 2. Test Exclude
        config = {"exclude": ["B"]}
        list_widget.set_advanced_filter(config)
        # Should only show e2 (e1 has B)
        assert model.rowCount() == 1
        text = model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole)
        assert "Out" in text

    def test_filter_persists_on_update(self, list_widget, qtbot):
        """
        Verify that filter persists when set_data is called again.
        """
        e1 = Event(name="Target", lore_date=100, attributes={"_tags": ["T"]})
        e2 = Event(name="Noise", lore_date=200, attributes={"_tags": ["N"]})

        list_widget.set_data([e1, e2], [])
        list_widget.set_advanced_filter({"include": ["T"]})

        model = list_widget._proxy_model
        assert model.rowCount() == 1

        # Reload data
        e3 = Event(name="New Target", lore_date=300, attributes={"_tags": ["T"]})
        list_widget.set_data([e1, e2, e3], [])

        # Filter should still be active: Target + New Target = 2 items
        items = [
            model.data(model.index(i, 0), Qt.ItemDataRole.DisplayRole)
            for i in range(model.rowCount())
        ]
        assert len(items) == 2
        assert any("Target" in x for x in items)
        assert any("New Target" in x for x in items)
        assert not any("Noise" in x for x in items)

    def test_clear_advanced_filter(self, list_widget, qtbot):
        """
        Verify clearing the filter shows everything.
        """
        e1 = Event(name="A", lore_date=1, attributes={"_tags": ["A"]})
        list_widget.set_data([e1], [])
        list_widget.set_advanced_filter({"include": ["B"]})
        
        model = list_widget._proxy_model
        assert model.rowCount() == 0

        # Set empty config
        list_widget.set_advanced_filter({})
        assert model.rowCount() == 1
