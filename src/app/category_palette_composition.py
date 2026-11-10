"""Compose category settings without extending worker or shell facades."""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.app.coordinators.category_palette_coordinator import CategoryPaletteCoordinator

if TYPE_CHECKING:
    from src.app.main_window import MainWindow


def compose_category_palette(window: "MainWindow") -> CategoryPaletteCoordinator:
    """Refresh from saved-world events, never from Explorer's filtered rows."""
    thread = window.worker_thread
    assert thread is not None
    coordinator = CategoryPaletteCoordinator(
        thread,
        lambda: window.worker.db_service,
        lambda: str(window.db_path),
        window.unified_list.set_category_assignments,
        window,
    )
    window.worker.initialized.connect(
        coordinator.initialized, Qt.ConnectionType.QueuedConnection
    )
    for signal in (
        window.worker.events_loaded,
        window.worker.entities_loaded,
        window.worker.command_finished,
    ):
        signal.connect(coordinator.refresh, Qt.ConnectionType.QueuedConnection)
    app = QApplication.instance()
    if app is not None:
        app.aboutToQuit.connect(coordinator.shutdown)
    return coordinator
