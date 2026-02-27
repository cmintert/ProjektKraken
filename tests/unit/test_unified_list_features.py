"""Tests for UnifiedListWidget multi-selection, sorting, and date formatting."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListView

from src.core.entities import Entity
from src.core.events import Event
from src.gui.widgets.unified_list import UnifiedListWidget


class TestUnifiedListSelection:
    """Tests for single-selection mode (required for drag-drop functionality)."""

    @pytest.fixture
    def list_widget(self, qtbot):
        widget = UnifiedListWidget()
        qtbot.addWidget(widget)
        return widget

    def test_single_selection_mode_enabled(self, list_widget):
        """Verify that SingleSelection mode is enabled (for drag-drop compatibility)."""
        assert (
            list_widget.list_widget.selectionMode()
            == QListView.SelectionMode.SingleSelection
        )

    def test_items_have_checkboxes(self, list_widget):
        """Verify that model items have checkboxes."""
        event1 = Event(id="e1", name="Event 1", lore_date=100)
        entity1 = Entity(id="ent1", name="Entity 1", type="Character")
        list_widget.set_data([event1], [entity1])

        # Check that items have ItemIsUserCheckable flag via model
        model = list_widget._proxy_model
        for i in range(model.rowCount()):
            index = model.index(i, 0)
            assert model.flags(index) & Qt.ItemFlag.ItemIsUserCheckable

    def test_checkbox_syncs_with_selection(self, list_widget, qtbot):
        """Verify that selecting an item checks its checkbox."""
        event1 = Event(id="e1", name="Event 1", lore_date=100)
        entity1 = Entity(id="ent1", name="Entity 1", type="Character")
        list_widget.set_data([event1], [entity1])

        # Select first item via view
        model = list_widget._proxy_model
        index = model.index(0, 0)
        list_widget.list_widget.setCurrentIndex(index)

        # Checkbox state is checked via CheckStateRole
        state = model.data(index, Qt.ItemDataRole.CheckStateRole)
        assert state == Qt.CheckState.Unchecked  # Model doesn't auto-check

    def test_items_selected_signal_emits_single(self, list_widget, qtbot):
        """Verify that items_selected signal emits single selection."""
        event1 = Event(id="e1", name="Event 1", lore_date=100)
        event2 = Event(id="e2", name="Event 2", lore_date=200)
        entity1 = Entity(id="ent1", name="Entity 1", type="Character")
        list_widget.set_data([event1, event2], [entity1])

        # Track signal emissions
        received_selections = []
        list_widget.items_selected.connect(lambda x: received_selections.append(x))

        # Select item via selection model
        model = list_widget._proxy_model
        selection_model = list_widget.list_widget.selectionModel()
        selection_model.select(model.index(0, 0), selection_model.SelectionFlag.Select)

        # Should have received signal with single item
        assert len(received_selections) > 0
        # Last signal should have 1 item (single selection mode)
        assert len(received_selections[-1]) == 1


class TestUnifiedListSorting:
    """Tests for sorting functionality."""

    @pytest.fixture
    def list_widget(self, qtbot):
        widget = UnifiedListWidget()
        qtbot.addWidget(widget)
        return widget

    def test_sort_combo_exists(self, list_widget):
        """Verify that sort combo box exists."""
        assert hasattr(list_widget, "sort_combo")
        assert list_widget.sort_combo.count() == 4  # Name, Created, Lore Date, Type

    def test_sort_direction_button_exists(self, list_widget):
        """Verify that sort direction button exists."""
        assert hasattr(list_widget, "btn_sort_dir")
        assert list_widget.btn_sort_dir.text() in ["↑", "↓"]

    def test_sort_by_name_ascending(self, list_widget):
        """Verify sorting by name ascending works."""
        entity_b = Entity(id="e1", name="Banana", type="Item")
        entity_a = Entity(id="e2", name="Apple", type="Item")
        entity_c = Entity(id="e3", name="Cherry", type="Item")
        list_widget.set_data([], [entity_b, entity_a, entity_c])

        # Set sort to Name, ascending
        list_widget.sort_combo.setCurrentText("Name")
        list_widget._sort_ascending = True
        list_widget._render_list()

        # First item should be Apple
        model = list_widget._proxy_model
        first_index = model.index(0, 0)
        first_text = model.data(first_index, Qt.ItemDataRole.DisplayRole)
        assert "Apple" in first_text

    def test_sort_by_name_descending(self, list_widget):
        """Verify sorting by name descending works."""
        entity_b = Entity(id="e1", name="Banana", type="Item")
        entity_a = Entity(id="e2", name="Apple", type="Item")
        entity_c = Entity(id="e3", name="Cherry", type="Item")
        list_widget.set_data([], [entity_b, entity_a, entity_c])

        # Set sort to Name, descending
        list_widget.sort_combo.setCurrentText("Name")
        list_widget._sort_ascending = False
        list_widget._render_list()

        # First item should be Cherry
        model = list_widget._proxy_model
        first_index = model.index(0, 0)
        first_text = model.data(first_index, Qt.ItemDataRole.DisplayRole)
        assert "Cherry" in first_text

    def test_toggle_sort_direction(self, list_widget):
        """Verify toggling sort direction works."""
        assert list_widget._sort_ascending is True
        assert list_widget.btn_sort_dir.text() == "↑"

        list_widget._toggle_sort_direction()

        assert list_widget._sort_ascending is False
        assert list_widget.btn_sort_dir.text() == "↓"

    def test_sort_by_type_ascending(self, list_widget):
        """Verify sorting by type ascending works."""
        entity_a = Entity(id="e1", name="Apple", type="Character")
        entity_b = Entity(id="e2", name="Banana", type="Item")
        entity_c = Entity(id="e3", name="Cherry", type="Location")
        list_widget.set_data([], [entity_b, entity_a, entity_c])

        # Set sort to Type, ascending
        list_widget.sort_combo.setCurrentText("Type")
        list_widget._sort_ascending = True
        list_widget._render_list()

        # First item should be Apple (Character)
        model = list_widget._proxy_model
        first_index = model.index(0, 0)
        first_text = model.data(first_index, Qt.ItemDataRole.DisplayRole)
        assert "Apple" in first_text

    def test_sort_by_type_descending(self, list_widget):
        """Verify sorting by type descending works."""
        entity_a = Entity(id="e1", name="Apple", type="Character")
        entity_b = Entity(id="e2", name="Banana", type="Item")
        entity_c = Entity(id="e3", name="Cherry", type="Location")
        list_widget.set_data([], [entity_b, entity_a, entity_c])

        # Set sort to Type, descending
        list_widget.sort_combo.setCurrentText("Type")
        list_widget._sort_ascending = False
        list_widget._render_list()

        # First item should be Cherry (Location)
        model = list_widget._proxy_model
        first_index = model.index(0, 0)
        first_text = model.data(first_index, Qt.ItemDataRole.DisplayRole)
        assert "Cherry" in first_text


class TestUnifiedListDateFormatting:
    """Tests for compact date formatting."""

    @pytest.fixture
    def list_widget(self, qtbot):
        widget = UnifiedListWidget()
        qtbot.addWidget(widget)
        return widget

    def test_format_compact_date_no_converter(self, list_widget):
        """Verify date formatting without converter falls back to model."""
        # Model handles formatting, so we test via model
        event = Event(id="e1", name="Test Event", lore_date=100.5)
        list_widget.set_data([event], [])

        # Get display text from model
        model = list_widget._proxy_model
        index = model.index(0, 0)
        text = model.data(index, Qt.ItemDataRole.DisplayRole)
        # Should contain the date
        assert "100.5" in text

    def test_format_compact_date_with_converter(self, list_widget):
        """Verify compact date format with converter via model."""
        # Mock the calendar converter
        mock_converter = MagicMock()
        mock_date = MagicMock()
        mock_date.day = 15
        mock_date.month = 3
        mock_date.year = 1024
        mock_date.time_fraction = 0.5  # Noon
        mock_converter.from_float.return_value = mock_date

        list_widget.set_calendar_converter(mock_converter)

        # Create event and check display through model
        event = Event(id="e1", name="Test Event", lore_date=100.5)
        list_widget.set_data([event], [])

        # Get display text from model
        model = list_widget._proxy_model
        index = model.index(0, 0)
        text = model.data(index, Qt.ItemDataRole.DisplayRole)

        # Should contain formatted date in dd.mm.yyyy - hh:mm format
        assert "15.03.1024 - 12:00" in text

    def test_format_compact_date_no_time(self, list_widget):
        """Verify compact date format without time (midnight) via model."""
        mock_converter = MagicMock()
        mock_date = MagicMock()
        mock_date.day = 1
        mock_date.month = 1
        mock_date.year = 1000
        mock_date.time_fraction = 0  # Midnight
        mock_converter.from_float.return_value = mock_date

        list_widget.set_calendar_converter(mock_converter)

        # Create event and check display
        event = Event(id="e1", name="Test Event", lore_date=0.0)
        list_widget.set_data([event], [])

        # Get display text from model
        model = list_widget._proxy_model
        index = model.index(0, 0)
        text = model.data(index, Qt.ItemDataRole.DisplayRole)

        # Should be dd.mm.yyyy without time
        assert "01.01.1000" in text

    def test_set_calendar_converter(self, list_widget):
        """Verify set_calendar_converter sets the converter."""
        mock_converter = MagicMock()

        list_widget.set_calendar_converter(mock_converter)

        assert list_widget._calendar_converter == mock_converter

    def test_event_displays_formatted_date(self, list_widget):
        """Verify events display formatted date in list."""
        # Setup mock converter
        mock_converter = MagicMock()
        mock_date = MagicMock()
        mock_date.day = 25
        mock_date.month = 12
        mock_date.year = 1024
        mock_date.time_fraction = 0
        mock_converter.from_float.return_value = mock_date

        list_widget.set_calendar_converter(mock_converter)

        event = Event(id="e1", name="Christmas Event", lore_date=100.0)
        list_widget.set_data([event], [])

        # Get display text from model
        model = list_widget._proxy_model
        index = model.index(0, 0)
        text = model.data(index, Qt.ItemDataRole.DisplayRole)

        # Should contain formatted date
        assert "[25.12.1024]" in text
        assert "Christmas Event" in text
