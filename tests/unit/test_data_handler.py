"""
Unit Tests for DataHandler.

Tests the refactored DataHandler to ensure it correctly emits signals
instead of directly manipulating MainWindow.
"""

import pytest
from PySide6.QtCore import QObject, Signal

from src.app.data_handler import DataHandler
from src.commands.base_command import CommandResult
from src.core.entities import Entity
from src.core.events import Event


@pytest.fixture
def data_handler():
    """Create a DataHandler instance for testing."""
    return DataHandler()


@pytest.fixture
def sample_events():
    """Create sample events for testing."""
    return [
        Event(id="event1", name="Event 1", lore_date=100.0),
        Event(id="event2", name="Event 2", lore_date=200.0),
    ]


@pytest.fixture
def sample_entities():
    """Create sample entities for testing."""
    return [
        Entity(id="entity1", name="Entity 1", type="character"),
        Entity(id="entity2", name="Entity 2", type="location"),
    ]


class TestDataHandlerSignals:
    """Test that DataHandler emits correct signals."""

    def test_events_loaded_emits_signals(self, data_handler, sample_events, qtbot):
        """Test that on_events_loaded emits the correct signals."""
        # Track emitted signals
        events_ready_signal = []
        status_message_signal = []
        suggestions_update_signal = []

        data_handler.events_ready.connect(lambda e: events_ready_signal.append(e))
        data_handler.status_message.connect(lambda m: status_message_signal.append(m))
        data_handler.suggestions_update_requested.connect(
            lambda items: suggestions_update_signal.append(items)
        )

        # Trigger the slot
        data_handler.on_events_loaded(sample_events)

        # Verify signals were emitted
        assert len(events_ready_signal) == 1
        assert events_ready_signal[0] == sample_events
        assert len(status_message_signal) == 1
        assert "Loaded 2 events" in status_message_signal[0]
        assert len(suggestions_update_signal) == 1

    def test_entities_loaded_emits_signals(self, data_handler, sample_entities, qtbot):
        """Test that on_entities_loaded emits the correct signals."""
        # Track emitted signals
        entities_ready_signal = []
        status_message_signal = []
        suggestions_update_signal = []

        data_handler.entities_ready.connect(lambda e: entities_ready_signal.append(e))
        data_handler.status_message.connect(lambda m: status_message_signal.append(m))
        data_handler.suggestions_update_requested.connect(
            lambda items: suggestions_update_signal.append(items)
        )

        # Trigger the slot
        data_handler.on_entities_loaded(sample_entities)

        # Verify signals were emitted
        assert len(entities_ready_signal) == 1
        assert entities_ready_signal[0] == sample_entities
        assert len(status_message_signal) == 1
        assert "Loaded 2 entities" in status_message_signal[0]
        assert len(suggestions_update_signal) == 1

    def test_suggestions_include_both_events_and_entities(
        self, data_handler, sample_events, sample_entities, qtbot
    ):
        """Test that suggestions include both events and entities."""
        suggestions = []
        data_handler.suggestions_update_requested.connect(
            lambda items: suggestions.append(items)
        )

        # Load events first
        data_handler.on_events_loaded(sample_events)
        # Then load entities
        data_handler.on_entities_loaded(sample_entities)

        # Check that the latest suggestions include both
        latest_suggestions = suggestions[-1]
        assert len(latest_suggestions) == 4
        
        # Verify format: (id, name, type)
        ids = [item[0] for item in latest_suggestions]
        assert "event1" in ids
        assert "event2" in ids
        assert "entity1" in ids
        assert "entity2" in ids

    def test_event_details_loaded_emits_signals(self, data_handler, sample_events, qtbot):
        """Test that on_event_details_loaded emits the correct signals."""
        dock_raise_signal = []
        event_details_signal = []

        data_handler.dock_raise_requested.connect(lambda d: dock_raise_signal.append(d))
        data_handler.event_details_ready.connect(
            lambda e, r, i: event_details_signal.append((e, r, i))
        )

        # Trigger the slot
        event = sample_events[0]
        relations = []
        incoming = []
        data_handler.on_event_details_loaded(event, relations, incoming)

        # Verify signals were emitted
        assert len(dock_raise_signal) == 1
        assert dock_raise_signal[0] == "event"
        assert len(event_details_signal) == 1
        assert event_details_signal[0] == (event, relations, incoming)

    def test_command_finished_handles_success(self, data_handler, qtbot):
        """Test that on_command_finished handles successful commands."""
        reload_events_signal = []
        data_handler.reload_events.connect(lambda: reload_events_signal.append(True))

        # Create a successful command result
        result = CommandResult(
            success=True,
            command_name="UpdateEventCommand",
            message="Event updated",
            data={}
        )

        data_handler.on_command_finished(result)

        # Verify reload signal was emitted
        assert len(reload_events_signal) == 1

    def test_command_finished_handles_failure(self, data_handler, qtbot):
        """Test that on_command_finished handles failed commands."""
        command_failed_signal = []
        data_handler.command_failed.connect(lambda m: command_failed_signal.append(m))

        # Create a failed command result
        result = CommandResult(
            success=False,
            command_name="UpdateEventCommand",
            message="Update failed",
            data={}
        )

        data_handler.on_command_finished(result)

        # Verify failure signal was emitted
        assert len(command_failed_signal) == 1
        assert command_failed_signal[0] == "Update failed"

    def test_pending_selection_after_create(self, data_handler, sample_events, qtbot):
        """Test that pending selection is tracked and signaled after create."""
        selection_signal = []
        data_handler.selection_requested.connect(
            lambda t, i: selection_signal.append((t, i))
        )

        # Simulate create event command success
        result = CommandResult(
            success=True,
            command_name="CreateEventCommand",
            message="Event created",
            data={"id": "new_event_id"}
        )
        data_handler.on_command_finished(result)

        # Load events (should trigger selection)
        data_handler.on_events_loaded(sample_events)

        # Verify selection was requested
        assert len(selection_signal) == 1
        assert selection_signal[0] == ("event", "new_event_id")


class TestDataHandlerDecoupling:
    """Test that DataHandler is properly decoupled from MainWindow."""

    def test_no_mainwindow_reference(self, data_handler):
        """Test that DataHandler does not have a MainWindow reference."""
        assert not hasattr(data_handler, "window")
        assert not hasattr(data_handler, "main_window")

    def test_uses_internal_cache(self, data_handler, sample_events, sample_entities):
        """Test that DataHandler maintains its own cache."""
        data_handler.on_events_loaded(sample_events)
        data_handler.on_entities_loaded(sample_entities)

        # Verify internal cache
        assert data_handler._cached_events == sample_events
        assert data_handler._cached_entities == sample_entities
