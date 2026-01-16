"""
Integration tests for MainWindow signal wiring.

These tests verify that MainWindow initializes successfully and has the
expected components configured.

Note: PySide6 doesn't expose a public API to check if signals are connected
to specific slots, so we test that the components exist and are configured
correctly rather than verifying specific connections.
"""

from unittest.mock import patch

from src.app.main import MainWindow

# Common patches needed for headless MainWindow testing
# These prevent segfaults in Qt C++ code during menu creation
MAIN_WINDOW_PATCHES = [
    patch("src.app.worker_manager.DatabaseWorker"),
    patch("src.app.worker_manager.QThread"),
    patch("src.app.main_window.QTimer"),
    patch("src.app.ui_manager.UIManager.create_timeline_menu"),
    patch("src.app.ui_manager.UIManager.create_settings_menu"),
    patch("src.app.ui_manager.UIManager.create_file_menu"),
    patch("src.app.ui_manager.UIManager.create_view_menu"),
    patch("src.app.ui_manager.UIManager.create_layouts_menu"),
]


def _start_patches():
    """Start all common patches."""
    for p in MAIN_WINDOW_PATCHES:
        p.start()


def _stop_patches():
    """Stop all common patches."""
    for p in MAIN_WINDOW_PATCHES:
        p.stop()


def test_data_handler_exists(qtbot):
    """Verify that DataHandler is created and accessible on MainWindow."""
    _start_patches()
    try:
        window = MainWindow()
        qtbot.addWidget(window)

        # Verify data_handler exists and has expected signals
        assert hasattr(window, "data_handler"), "MainWindow has no data_handler"
        assert hasattr(window.data_handler, "events_ready"), (
            "data_handler has no events_ready signal"
        )
        assert hasattr(window.data_handler, "entities_ready"), (
            "data_handler has no entities_ready signal"
        )
    finally:
        _stop_patches()


def test_timeline_provider_wiring(qtbot):
    """Verify that TimelineView has a data provider configured."""
    _start_patches()
    try:
        window = MainWindow()
        qtbot.addWidget(window)

        timeline_widget = window.timeline
        assert timeline_widget is not None
        assert hasattr(timeline_widget.view, "_data_provider")
    finally:
        _stop_patches()


def test_map_and_longform_handlers_exist(qtbot):
    """Verify MapHandler and LongformManager are created."""
    _start_patches()
    try:
        window = MainWindow()
        qtbot.addWidget(window)

        # Verify handlers exist
        assert hasattr(window, "map_handler"), "MainWindow has no map_handler"
        assert hasattr(window, "longform_manager"), "MainWindow has no longform_manager"

        # Verify data_handler has expected signals
        assert hasattr(window.data_handler, "maps_ready"), (
            "data_handler has no maps_ready signal"
        )
        assert hasattr(window.data_handler, "markers_ready"), (
            "data_handler has no markers_ready signal"
        )
        assert hasattr(window.data_handler, "longform_sequence_ready"), (
            "data_handler has no longform_sequence_ready signal"
        )
    finally:
        _stop_patches()
