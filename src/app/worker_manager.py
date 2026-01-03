"""
WorkerManager - Handles database worker thread management for MainWindow.

This module contains all worker thread initialization and status management
functionality extracted from MainWindow to reduce its size and improve maintainability.
"""

from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QObject,
    QSettings,
    Qt,
    QThread,
    QTimer,
    Slot,
)
from PySide6.QtWidgets import QApplication

from src.app.constants import (
    DEFAULT_DB_NAME,
    SETTINGS_ACTIVE_DB_KEY,
    SETTINGS_FILTER_CONFIG_KEY,
    STATUS_DB_INIT_FAIL,
    STATUS_ERROR_PREFIX,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.core.logging_config import get_logger
from src.core.paths import get_user_data_path
from src.services.db_service import DatabaseService
from src.services.worker import DatabaseWorker

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = get_logger(__name__)


class WorkerManager(QObject):
    """
    Manages database worker thread operations for the MainWindow.

    This class encapsulates all functionality related to:
    - Initializing the database worker thread
    - Connecting worker signals to MainWindow slots
    - Status message management (operation started/finished/error)
    - Database initialization handling
    """

    def __init__(self, main_window: "MainWindow") -> None:
        """
        Initialize the WorkerManager.

        Args:
            main_window: Reference to the MainWindow instance.
        """
        super().__init__()
        self.window = main_window

    def init_worker(self) -> None:
        """
        Initializes the DatabaseWorker and moves it to a separate thread.
        Connects all worker signals to MainWindow slots.
        """
        self.window.worker_thread = QThread()

        # Load active database from settings
        settings = QSettings()
        active_db = settings.value(SETTINGS_ACTIVE_DB_KEY, DEFAULT_DB_NAME)

        db_path = get_user_data_path(active_db)
        logger.info(f"Initializing DatabaseWorker with: {db_path}")

        # Store db_path for main thread usage (path calculations)
        self.window.db_path = db_path

        self.window.worker = DatabaseWorker(db_path)
        self.window.worker.moveToThread(self.window.worker_thread)

        # Connect Worker Signals
        self.window.worker.initialized.connect(self.on_db_initialized)
        self.window.worker.events_loaded.connect(
            self.window.data_handler.on_events_loaded
        )
        self.window.worker.entities_loaded.connect(
            self.window.data_handler.on_entities_loaded
        )
        self.window.worker.event_details_loaded.connect(
            self.window.data_handler.on_event_details_loaded
        )
        self.window.worker.entity_details_loaded.connect(
            self.window.data_handler.on_entity_details_loaded
        )
        self.window.worker.command_finished.connect(
            self.window.data_handler.on_command_finished
        )
        self.window.worker.operation_started.connect(self.update_status_message)
        self.window.worker.operation_finished.connect(self.clear_status_message)
        self.window.worker.error_occurred.connect(self.show_error_message)
        self.window.worker.longform_sequence_loaded.connect(
            self.window.data_handler.on_longform_sequence_loaded
        )
        self.window.worker.calendar_config_loaded.connect(
            self.window.on_calendar_config_loaded
        )
        self.window.worker.current_time_loaded.connect(
            self.window.on_current_time_loaded
        )
        self.window.worker.grouping_dialog_data_loaded.connect(
            self.window.on_grouping_dialog_data_loaded
        )
        self.window.worker.maps_loaded.connect(self.window.data_handler.on_maps_loaded)
        self.window.worker.markers_loaded.connect(
            self.window.data_handler.on_markers_loaded
        )
        self.window.worker.filter_results_ready.connect(
            self.window._on_filter_results_ready
        )
        self.window.worker.entity_state_resolved.connect(
            self.window.data_handler.on_entity_state_resolved
        )
        # Connect filtering request
        self.window.filter_requested.connect(self.window.worker.apply_filter)

        # Connect MainWindow signal for sending commands to worker thread
        self.window.command_requested.connect(self.window.worker.run_command)

        # Connect Thread Start
        self.window.worker_thread.start()

    @Slot(str)
    def update_status_message(self, message: str) -> None:
        """
        Updates the status bar message and sets cursor to Wait.

        Args:
            message: The message to display.
        """
        self.window.status_bar.showMessage(message)
        # Busy cursor
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

    def clear_status_message(self, message: str) -> None:
        """
        Clears the status bar message after a delay and restores cursor.

        Args:
            message: The final completion message.
        """
        self.window.status_bar.showMessage(message, 3000)
        QApplication.restoreOverrideCursor()

    @Slot(str)
    def show_error_message(self, message: str) -> None:
        """
        Displays an error message in the status bar and logs it.

        Args:
            message: The error description.
        """
        self.window.status_bar.showMessage(f"{STATUS_ERROR_PREFIX}{message}", 5000)
        QApplication.restoreOverrideCursor()
        logger.error(message)

    @Slot(bool)
    def on_db_initialized(self, success: bool) -> None:
        """
        Handler for database initialization result.

        Args:
            success: True if connection succeeded, False otherwise.
        """
        if success:
            # Initialize GUI database connection for timeline data provider
            try:
                # Use the same db_path as the worker
                self.window.gui_db_service = DatabaseService(self.window.db_path)
                self.window.gui_db_service.connect()
                # Set MainWindow as data provider (implements the interface)
                self.window.timeline.set_data_provider(self.window)
            except Exception as e:
                logger.error(f"Failed to initialize GUI database service: {e}")

            self.window.load_data()
            self.window._request_calendar_config()
            self.window._request_current_time()
            self.window._request_grouping_config()
            self.window.load_maps()

            # Refresh AI search index status
            QTimer.singleShot(100, self.window.refresh_search_index_status)

            # Restore filter configuration
            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            filter_config = settings.value(SETTINGS_FILTER_CONFIG_KEY)
            if filter_config:
                self.window.filter_config = filter_config
                # Apply restored filter
                logger.info(f"Restoring filter config: {self.window.filter_config}")
                self.window.filter_requested.emit(self.window.filter_config)
                # Update UI state
                has_filter = bool(
                    self.window.filter_config.get("include")
                    or self.window.filter_config.get("exclude")
                )
                self.window.unified_list.set_filter_active(has_filter)

            # Restore last selected item (delayed to ensure data loaded)
            QTimer.singleShot(200, self.window._restore_last_selection)
        else:
            self.window.status_bar.showMessage(STATUS_DB_INIT_FAIL)
