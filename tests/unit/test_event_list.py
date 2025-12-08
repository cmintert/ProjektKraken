"""
Unit tests for EventListWidget.
"""

import pytest
from PySide6.QtCore import Qt
from src.gui.widgets.event_list import EventListWidget
from src.core.events import Event


@pytest.fixture
def event_list(qtbot):
    """Create EventListWidget for testing."""
    widget = EventListWidget()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def sample_events():
    """Sample events for testing."""
    return [
        Event(id="event1", name="Event 1", lore_date=1000.0, type="generic"),
        Event(id="event2", name="Event 2", lore_date=2000.0, type="combat"),
        Event(id="event3", name="Event 3", lore_date=3000.0, type="session"),
    ]


def test_init(event_list):
    """Test widget initialization."""
    assert event_list.btn_refresh is not None
    assert event_list.btn_delete is not None
    assert event_list.list_widget is not None
    assert event_list.empty_label is not None
    assert event_list.btn_delete.isEnabled() is False


def test_set_events_empty(event_list):
    """Test setting empty event list."""
    event_list.set_events([])

    assert event_list.list_widget.isHidden()
    assert not event_list.empty_label.isHidden()
    assert event_list.list_widget.count() == 0


def test_set_events_with_data(event_list, sample_events):
    """Test setting event list with data."""
    event_list.set_events(sample_events)

    assert not event_list.list_widget.isHidden()
    assert event_list.empty_label.isHidden()
    assert event_list.list_widget.count() == 3

    # Check first item
    item = event_list.list_widget.item(0)
    assert "Event 1" in item.text()
    assert item.data(100) == "event1"


def test_selection_changed_signal(event_list, sample_events, qtbot):
    """Test event_selected signal is emitted on selection."""
    event_list.set_events(sample_events)

    with qtbot.waitSignal(event_list.event_selected, timeout=1000) as blocker:
        event_list.list_widget.setCurrentRow(0)

    assert blocker.args[0] == "event1"
    assert event_list.btn_delete.isEnabled()


def test_selection_cleared(event_list, sample_events):
    """Test delete button disabled when selection cleared."""
    event_list.set_events(sample_events)
    event_list.list_widget.setCurrentRow(0)
    assert event_list.btn_delete.isEnabled()

    event_list.list_widget.clearSelection()

    assert event_list.btn_delete.isEnabled() is False


def test_delete_clicked_signal(event_list, sample_events, qtbot):
    """Test delete_requested signal is emitted."""
    event_list.set_events(sample_events)
    event_list.list_widget.setCurrentRow(1)

    with qtbot.waitSignal(event_list.delete_requested, timeout=1000) as blocker:
        event_list.btn_delete.click()

    assert blocker.args[0] == "event2"


def test_delete_clicked_no_selection(event_list, qtbot):
    """Test delete does nothing without selection."""
    with qtbot.assertNotEmitted(event_list.delete_requested):
        event_list.btn_delete.click()


def test_refresh_clicked_signal(event_list, qtbot):
    """Test refresh_requested signal is emitted."""
    with qtbot.waitSignal(event_list.refresh_requested, timeout=1000):
        event_list.btn_refresh.click()


def test_set_events_clears_previous(event_list, sample_events):
    """Test that set_events clears previous items."""
    event_list.set_events(sample_events)
    assert event_list.list_widget.count() == 3

    new_events = [Event(id="new1", name="New Event", lore_date=5000.0, type="generic")]
    event_list.set_events(new_events)

    assert event_list.list_widget.count() == 1
    assert "New Event" in event_list.list_widget.item(0).text()


def test_widget_styling(event_list):
    """Test that styled background attribute is set."""
    assert event_list.testAttribute(Qt.WA_StyledBackground)


def test_empty_to_populated_transition(event_list, sample_events):
    """Test transition from empty to populated state."""
    # Start empty
    event_list.set_events([])
    assert not event_list.empty_label.isHidden()

    # Populate
    event_list.set_events(sample_events)
    assert not event_list.list_widget.isHidden()
    assert event_list.empty_label.isHidden()


def test_populated_to_empty_transition(event_list, sample_events):
    """Test transition from populated to empty state."""
    # Start populated
    event_list.set_events(sample_events)
    assert not event_list.list_widget.isHidden()

    # Clear
    event_list.set_events([])
    assert event_list.list_widget.isHidden()
    assert not event_list.empty_label.isHidden()
