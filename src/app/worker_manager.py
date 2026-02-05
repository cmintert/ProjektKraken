"""WorkerManager - Handles database worker thread management for MainWindow.

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
    Signal,
    Slot,
)
from PySide6.QtWidgets import QApplication

from src.app.constants import (
    SETTINGS_ACTIVE_DB_KEY,
    SETTINGS_FILTER_CONFIG_KEY,
    STATUS_DB_INIT_FAIL,
    STATUS_ERROR_PREFIX,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.core.logging_config import get_logger
from src.core.paths import ensure_worlds_directory
from src.core.world import WorldManager
from src.services.db_service import DatabaseService
from src.services.worker import DatabaseWorker

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = get_logger(__name__)


class WorkerManager(QObject):
    """Manages database worker thread operations for the MainWindow.

    This class encapsulates all functionality related to:
    - Initializing the database worker thread
    - Connecting worker signals to MainWindow slots
    - Status message management (operation started/finished/error)
    - Database initialization handling
    """

    summary_requested = Signal(object)

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize the WorkerManager.

        Args:
            main_window: Reference to the MainWindow instance.

        """
        super().__init__()
        self.window = main_window

    def init_worker(self) -> None:
        """Initializes the DatabaseWorker and moves it to a separate thread. Connects
        all worker signals to MainWindow slots.

        Uses portable-only mode: worlds are stored in worlds/ directory
        next to the executable.
        """
        self.window.worker_thread = QThread()

        # Ensure worlds directory exists and is writable
        try:
            worlds_dir = ensure_worlds_directory()
            logger.info(f"Using worlds directory: {worlds_dir}")
        except OSError as e:
            logger.critical(f"Cannot initialize worlds directory: {e}")
            # Let the UI handle showing the error
            self.window.status_bar.showMessage(
                f"CRITICAL: Cannot create worlds directory. {e}"
            )
            return

        # Initialize world manager
        world_manager = WorldManager(worlds_dir)

        # Load active world name from settings
        settings = QSettings()
        active_world_name = settings.value(SETTINGS_ACTIVE_DB_KEY, None)

        # Get or create default world
        world = None
        if active_world_name:
            world = world_manager.get_world(active_world_name)

        if world is None:
            # No active world or world not found - discover or create default
            worlds = world_manager.discover_worlds()
            if worlds:
                world = worlds[0]  # Use first available world
                logger.info(f"Using first available world: {world.name}")
            else:
                # Create default world
                logger.info("No worlds found, creating default world")
                world = world_manager.create_world(
                    name="Default World", description="Default worldbuilding workspace"
                )

            # Save as active world
            settings.setValue(SETTINGS_ACTIVE_DB_KEY, world.name)

        # Get database path from world
        db_path = str(world.db_path)
        logger.info(f"Initializing DatabaseWorker with: {db_path}")

        # Store db_path and world for main thread usage
        self.window.db_path = db_path
        self.window.current_world = world

        self.window.worker = DatabaseWorker(db_path)
        self.window.worker.moveToThread(self.window.worker_thread)

        # Connect Worker Signals (explicit QueuedConnection for cross-thread safety)
        # All connections use QueuedConnection because worker is on a different thread
        connection_type = Qt.ConnectionType.QueuedConnection

        self.window.worker.initialized.connect(self.on_db_initialized, connection_type)
        self.window.worker.events_loaded.connect(
            self.window.data_handler.on_events_loaded, connection_type
        )
        self.window.worker.entities_loaded.connect(
            self.window.data_handler.on_entities_loaded, connection_type
        )
        self.window.worker.event_details_loaded.connect(
            self.window.data_handler.on_event_details_loaded, connection_type
        )
        self.window.worker.entity_details_loaded.connect(
            self.window.data_handler.on_entity_details_loaded, connection_type
        )
        self.window.worker.command_finished.connect(
            self.window.data_handler.on_command_finished, connection_type
        )
        self.window.worker.operation_started.connect(
            self.update_status_message, connection_type
        )
        self.window.worker.operation_finished.connect(
            self.clear_status_message, connection_type
        )
        self.window.worker.error_occurred.connect(
            self.show_error_message, connection_type
        )
        self.window.worker.longform_sequence_loaded.connect(
            self.window.data_handler.on_longform_sequence_loaded, connection_type
        )
        self.window.worker.calendar_config_loaded.connect(
            self.window.on_calendar_config_loaded, connection_type
        )
        self.window.worker.current_time_loaded.connect(
            self.window.on_current_time_loaded, connection_type
        )
        self.window.worker.grouping_dialog_data_loaded.connect(
            self.window.on_grouping_dialog_data_loaded, connection_type
        )
        self.window.worker.maps_loaded.connect(
            self.window.data_handler.on_maps_loaded, connection_type
        )
        self.window.worker.markers_loaded.connect(
            self.window.data_handler.on_markers_loaded, connection_type
        )
        self.window.worker.trajectories_loaded.connect(
            self.window.data_handler.on_trajectories_loaded, connection_type
        )
        self.window.worker.filter_results_ready.connect(
            self.window._on_filter_results_ready, connection_type
        )
        self.window.worker.entity_state_resolved.connect(
            self.window.data_handler.on_entity_state_resolved, connection_type
        )
        self.window.worker.graph_data_loaded.connect(
            self.window.data_handler.on_graph_data_loaded, connection_type
        )
        self.window.worker.graph_metadata_loaded.connect(
            self.window.data_handler.on_graph_metadata_loaded, connection_type
        )
        self.window.worker.completer_data_loaded.connect(
            self.window.on_completer_data_loaded, connection_type
        )
        self.window.worker.completer_data_loaded.connect(
            self.window.on_completer_data_loaded, connection_type
        )
        self.window.worker.import_finished.connect(
            self.window._on_import_finished, connection_type
        )
        self.window.worker.summary_generated.connect(
            self.window._on_summary_generated_result, connection_type
        )

        # Connect MainWindow signals to worker (cross-thread: main → worker)
        # All connections use QueuedConnection because worker is on a different thread
        self.window.filter_requested.connect(
            self.window.worker.apply_filter, connection_type
        )
        self.summary_requested.connect(
            self.window.worker.generate_summary, connection_type
        )
        self.window.command_requested.connect(
            self.window.worker.run_command, connection_type
        )
        self.window.load_graph_data_requested.connect(
            self.window.worker.load_graph_data, connection_type
        )

        # Connect Thread Start
        self.window.worker_thread.start()

    @Slot(str)
    def update_status_message(self, message: str) -> None:
        """Updates the status bar message and sets cursor to Wait.

        Args:
            message: The message to display.

        """
        self.window.status_bar.showMessage(message)
        # Busy cursor
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

    def clear_status_message(self, message: str) -> None:
        """Clears the status bar message after a delay and restores cursor.

        Args:
            message: The final completion message.

        """
        self.window.status_bar.showMessage(message, 3000)
        QApplication.restoreOverrideCursor()

    @Slot(str)
    def show_error_message(self, message: str) -> None:
        """Displays an error message in the status bar and logs it.

        Args:
            message: The error description.

        """
        self.window.status_bar.showMessage(f"{STATUS_ERROR_PREFIX}{message}", 5000)
        QApplication.restoreOverrideCursor()
        logger.error(message)

    @Slot(bool)
    def on_db_initialized(self, success: bool) -> None:
        """Handler for database initialization result.

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

            # Initialize backup service
            try:
                from src.core.backup_config import BackupConfig
                from src.services.backup_service import BackupService

                # Load backup config from settings or use defaults
                backup_config = BackupConfig()

                # Initialize backup service
                self.window.backup_service = BackupService(backup_config)
                self.window.backup_service.set_database_path(self.window.db_path)

                # Register with database service for integration
                if hasattr(self.window, "gui_db_service"):
                    self.window.gui_db_service.register_backup_service(
                        self.window.backup_service
                    )

                logger.info("Backup service initialized successfully")

                # Start auto-backup if enabled
                if (
                    backup_config.enabled
                    and backup_config.auto_save_interval_minutes > 0
                ):
                    self.window.backup_service.start_auto_backup()
                    logger.info(
                        f"Auto-backup enabled with {backup_config.auto_save_interval_minutes} minute interval"
                    )

            except Exception as e:
                logger.error(f"Failed to initialize backup service: {e}")
                # Don't fail the entire app if backup service fails to init
                self.window.backup_service = None

            # Initialize History Service for Phase 2 persistent undo/redo
            try:
                from src.services.history_service import HistoryService
                from src.commands.event_commands import (
                    CreateEventCommand,
                    UpdateEventCommand,
                    DeleteEventCommand,
                )
                from src.commands.entity_commands import (
                    CreateEntityCommand,
                    UpdateEntityCommand as UpdateEntityCmd,
                    DeleteEntityCommand as DeleteEntityCmd,
                )

                # Create history service with current world ID
                world_id = self.window.current_world.id if self.window.current_world else "default"
                self.window.history_service = HistoryService(
                    self.window.gui_db_service, world_id
                )

                # Register command types for deserialization
                # Event commands
                self.window.history_service.register_command_type(
                    "CreateEventCommand", CreateEventCommand
                )
                self.window.history_service.register_command_type(
                    "UpdateEventCommand", UpdateEventCommand
                )
                self.window.history_service.register_command_type(
                    "DeleteEventCommand", DeleteEventCommand
                )
                
                # Entity commands
                self.window.history_service.register_command_type(
                    "CreateEntityCommand", CreateEntityCommand
                )
                self.window.history_service.register_command_type(
                    "UpdateEntityCommand", UpdateEntityCmd
                )
                self.window.history_service.register_command_type(
                    "DeleteEntityCommand", DeleteEntityCmd
                )

                # Connect to command coordinator
                self.window.coordinator.set_history_service(self.window.history_service)

                # Load command history from database
                self.window.coordinator.load_history()

                logger.info("History service initialized successfully")

            except Exception as e:
                logger.error(f"Failed to initialize history service: {e}")
                # Don't fail the entire app if history service fails to init
                self.window.history_service = None

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
            QTimer.singleShot(
                200, self.window.navigation_coordinator.restore_last_selection
            )
        else:
            self.window.status_bar.showMessage(STATUS_DB_INIT_FAIL)

    @Slot(object)
    def generate_summary(self, item: object) -> None:
        """Request summary generation from worker."""
        # Use signal instead of invokeMethod for reliability
        self.summary_requested.emit(item)
