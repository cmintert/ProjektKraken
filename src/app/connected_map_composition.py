"""Composition boundary for connected-map display; no feature logic in facades."""

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QApplication

from src.app.coordinators.map_projection_coordinator import MapProjectionCoordinator
from src.core.theme_manager import ThemeManager
from src.gui.widgets.map.connected_features import ConnectedFeatures

if TYPE_CHECKING:
    from src.app.main_window import MainWindow


def compose_connected_maps(
    window: "MainWindow", owner: QObject
) -> MapProjectionCoordinator:
    """Wire existing public context signals to explicit feature-owned ports."""
    overlay = ConnectedFeatures(
        window.map_widget.view, window.map_widget.map_settings_menu
    )
    thread = window.worker_thread
    assert thread is not None
    coordinator = MapProjectionCoordinator(
        overlay,
        thread,
        lambda: window.worker.db_service,
        lambda: str(window.db_path),
        window.map_widget.get_selected_map_id,
        window.timeline.get_playhead_time,
        owner,
    )
    overlay.source_requested.connect(window.map_widget.select_map)
    window.map_widget.map_selected.connect(coordinator.refresh)
    window.timeline.playhead_time_changed.connect(coordinator.refresh_playhead)
    window.map_widget.view.zoom_factor_changed.connect(coordinator.refresh)
    ThemeManager().theme_changed.connect(coordinator.refresh)
    window.worker.calendar_config_loaded.connect(
        coordinator.invalidate, Qt.ConnectionType.QueuedConnection
    )
    window.data_handler.markers_ready.connect(coordinator.invalidate)
    window.worker.command_finished.connect(
        coordinator.invalidate, Qt.ConnectionType.QueuedConnection
    )
    window.worker.initialized.connect(
        coordinator.invalidate, Qt.ConnectionType.QueuedConnection
    )
    window.worker.maps_loaded.connect(
        coordinator.invalidate, Qt.ConnectionType.QueuedConnection
    )
    application = QApplication.instance()
    if application is not None:
        application.aboutToQuit.connect(coordinator.shutdown)
    return coordinator
