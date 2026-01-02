from unittest.mock import MagicMock, patch

import pytest

from src.app.main import MainWindow


@pytest.fixture
def main_window(qtbot):
    """Fixture to create the MainWindow."""
    # Mock services to avoid full initialization
    # We use multiple patches. Note: main.py uses specific imports so we patch where they are used.
    with patch("src.app.main_window.DatabaseService"):
        window = MainWindow()
        qtbot.addWidget(window)
        return window


def test_data_handler_signal_wiring(qtbot, main_window):
    """Verify that DataHandler signals are connected to MainWindow slots."""

    # 1. Mock the slot we expect to be called
    # Note: connect_all() is called in __init__, so signals should be wired.
    main_window._on_events_ready = MagicMock()

    # 2. Emit the signal (ensure we pass expected arguments if any)
    # _on_events_ready expects a list
    main_window.data_handler.events_ready.emit([])

    # 3. Verify slot was called
    main_window._on_events_ready.assert_called_once()


def test_timeline_provider_wiring(qtbot, main_window):
    """Verify that TimelineView has a data provider configured."""

    timeline_widget = main_window.timeline
    assert timeline_widget is not None

    # The view should have a _data_provider attribute (even if None initially)
    # In the new architecture, it's defined in TimelineView.__init__
    assert hasattr(timeline_widget.view, "_data_provider")


def test_map_and_longform_wiring(qtbot, main_window):
    """Verify MapHandler and LongformManager wiring."""
    # 1. Mock the slots
    main_window.map_handler.on_maps_ready = MagicMock()
    main_window.map_handler.on_markers_ready = MagicMock()
    main_window.longform_manager.on_longform_sequence_loaded = MagicMock()

    # 2. Emit signals
    main_window.data_handler.maps_ready.emit([])
    main_window.data_handler.markers_ready.emit("map_id", [])
    main_window.data_handler.longform_sequence_ready.emit([])

    # 3. Verify slots called
    main_window.map_handler.on_maps_ready.assert_called_once()
    main_window.map_handler.on_markers_ready.assert_called_once()
    main_window.longform_manager.on_longform_sequence_loaded.assert_called_once()
