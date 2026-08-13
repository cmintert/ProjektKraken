"""WorkerManager - Handles database worker thread management for MainWindow.

This module contains all worker thread initialization and status management
functionality extracted from MainWindow to reduce its size and improve maintainability.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import (
    QObject,
    QSettings,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtWidgets import QApplication, QMessageBox

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
from src.core.world import World, WorldManager
from src.gui.dialogs.external_database_warning import external_database_warning
from src.services.worker import DatabaseWorker
from src.services.world_storage_settings import WorldStorageSettings

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
    rebuild_index_requested = Signal(str, list)  # → worker.rebuild_search_index
    _index_single_requested = Signal(str, str, list)  # → worker.index_object
    load_ai_preferences_requested = Signal()
    save_ai_preferences_requested = Signal(dict)
    initialize_history_requested = Signal(str)
    load_timeline_grouping_requested = Signal()
    save_world_theme_requested = Signal(str)
    load_embedding_stats_requested = Signal()

    # Delay (ms) after the last save before firing the re-embed request.
    # Prevents running ONNX/numpy-heavy embedding code on every keystroke-
    # triggered autosave, which crashes when native threads collide with
    # the Chromium WebEngine graph view running on the main thread.
    INDEX_DEBOUNCE_MS = 10_000

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize the WorkerManager.

        Args:
            main_window: Reference to the MainWindow instance.

        """
        super().__init__()
        self.window = main_window
        self.database_initialized: bool | None = None
        self.package_smoke_callback: Callable[[bool], None] | None = None

        self._pending_indices: set[tuple[str, str]] = set()
        self._index_timer = QTimer(self)
        self._index_timer.setSingleShot(True)
        self._index_timer.timeout.connect(self._flush_pending_index)

    def _load_active_world(
        self,
        world_manager: WorldManager,
        storage_settings: WorldStorageSettings,
        active_world_name: str | None,
    ) -> World | None:
        """Load the active world, prompting before an untrusted external path."""
        active_world_path = storage_settings.active_world_path()
        if active_world_path is not None:
            inspected = World.inspect(active_world_path)
            if inspected is not None and inspected.is_external_database:
                database_path = inspected.db_path
                if not database_path.is_file():
                    QMessageBox.warning(
                        self.window,
                        "External Database Missing",
                        "The approved external database is unavailable:\n\n"
                        f"{database_path}\n\n"
                        "Projekt Kraken will not create a replacement database. "
                        "Reconnect or restore the database, or select another "
                        "complete world folder in World Manager.",
                    )
                    storage_settings.clear_active_world_path()
                    return None

                if not storage_settings.is_external_path_approved(inspected):
                    response = QMessageBox.question(
                        self.window,
                        "Approve External World Database?",
                        external_database_warning(database_path),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if response != QMessageBox.StandardButton.Yes:
                        storage_settings.clear_active_world_path()
                        return None
                    storage_settings.approve_external_path(inspected)

            approved_path = (
                storage_settings.approved_external_path(inspected)
                if inspected is not None
                else None
            )
            approvals = [approved_path] if approved_path is not None else []
            world = World.load(active_world_path, approvals)
            if world is not None:
                return world
            storage_settings.clear_active_world_path()

        if active_world_name:
            return world_manager.get_world(active_world_name)
        return None

    def init_worker(self) -> None:
        """Initializes the DatabaseWorker and moves it to a separate thread. Connects
        all worker signals to MainWindow slots.

        Uses complete portable world folders by default and locally approved
        external database links when configured.
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

        storage_settings = WorldStorageSettings()
        world_manager = WorldManager(
            worlds_dir,
            additional_world_paths=storage_settings.registered_world_paths(),
            approved_external_paths=storage_settings.external_approvals(),
        )

        # Load active world name from settings
        settings = QSettings()
        active_world_name = cast(
            str | None,
            settings.value(SETTINGS_ACTIVE_DB_KEY, None, type=str),
        )

        world = self._load_active_world(
            world_manager,
            storage_settings,
            active_world_name,
        )

        if world is None:
            # No active world or world not found - discover or create default
            worlds = world_manager.discover_worlds()
            if worlds:
                world = worlds[0]  # Use first available world
                logger.info(f"Using first available world: {world.name}")
            else:
                # Create default world
                logger.info("No worlds found, creating default world")
                default_name = "Default World"
                suffix = 2
                while (worlds_dir / default_name).exists():
                    default_name = f"Default World {suffix}"
                    suffix += 1
                world = world_manager.create_world(
                    name=default_name,
                    description="Default worldbuilding workspace",
                )

            # Save as active world
            settings.setValue(SETTINGS_ACTIVE_DB_KEY, world.name)

        storage_settings.register_world_path(world.path)
        storage_settings.set_active_world_path(world.path)

        # Get database path from world
        db_path = str(world.db_path)
        logger.info(f"Initializing DatabaseWorker with: {db_path}")

        # Store db_path and world for main thread usage
        self.window.db_path = db_path
        self.window.current_world = world

        from src.commands.registry import get_command_types

        self.window.worker = DatabaseWorker(db_path, get_command_types())
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
            self.window.time_coordinator.on_calendar_config_loaded, connection_type
        )
        self.window.worker.current_time_loaded.connect(
            self.window.time_coordinator.on_current_time_loaded, connection_type
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
        self.window.worker.feature_geometry_states_loaded.connect(
            self.window.data_handler.on_feature_geometry_states_loaded,
            connection_type,
        )
        self.window.worker.filter_results_ready.connect(
            self.window.data_coordinator.on_filter_results_ready, connection_type
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
        self.window.worker.graph_lexicon_loaded.connect(
            self.window.data_handler.on_graph_lexicon_loaded, connection_type
        )
        self.window.worker.timeline_grouping_loaded.connect(
            self.on_timeline_grouping_loaded,
            connection_type,
        )
        self.window.worker.world_theme_loaded.connect(
            self.on_world_theme_loaded,
            connection_type,
        )
        self.window.worker.completer_data_loaded.connect(
            self.window.data_coordinator.on_completer_data_loaded, connection_type
        )
        self.window.worker.semantic_suggestions_ready.connect(
            self.window.data_coordinator.on_semantic_suggestions, connection_type
        )
        self.window.worker.import_finished.connect(
            self.window.import_coordinator.on_import_finished, connection_type
        )
        self.window.worker.obsidian_export_prepared.connect(
            self.window.import_coordinator.on_obsidian_export_prepared,
            connection_type,
        )
        self.window.worker.obsidian_export_finished.connect(
            self.window.import_coordinator.on_obsidian_export_finished,
            connection_type,
        )
        self.window.worker.summary_generated.connect(
            self.window.data_coordinator.on_summary_generated_result, connection_type
        )
        self.window.worker.summary_generation_failed.connect(
            self.window.data_coordinator.on_summary_generation_failed, connection_type
        )
        self.rebuild_index_requested.connect(
            self.window.worker.rebuild_search_index, connection_type
        )
        self._index_single_requested.connect(
            self.window.worker.index_object, connection_type
        )
        self.load_ai_preferences_requested.connect(
            self.window.worker.load_ai_generation_preferences,
            connection_type,
        )
        self.save_ai_preferences_requested.connect(
            self.window.worker.save_ai_generation_preferences,
            connection_type,
        )
        self.initialize_history_requested.connect(
            self.window.worker.initialize_history,
            connection_type,
        )
        self.load_timeline_grouping_requested.connect(
            self.window.worker.load_timeline_grouping_config,
            connection_type,
        )
        self.save_world_theme_requested.connect(
            self.window.worker.save_world_theme,
            connection_type,
        )
        self.load_embedding_stats_requested.connect(
            self.window.worker.load_embedding_stats,
            connection_type,
        )
        self.window.import_coordinator.run_import_requested.connect(
            self.window.worker.run_import,
            connection_type,
        )
        self.window.import_coordinator.run_markdown_import_requested.connect(
            self.window.worker.run_markdown_import,
            connection_type,
        )
        self.window.import_coordinator.run_markdown_batch_import_requested.connect(
            self.window.worker.run_markdown_batch_import,
            connection_type,
        )
        self.window.import_coordinator.prepare_obsidian_export_requested.connect(
            self.window.worker.prepare_single_obsidian_export,
            connection_type,
        )
        self.window.import_coordinator.run_obsidian_export_requested.connect(
            self.window.worker.run_single_obsidian_export,
            connection_type,
        )

        # Connect MainWindow signals to worker (cross-thread: main → worker)
        # All connections use QueuedConnection because worker is on a different thread
        self.window.filter_requested.connect(
            self.window.worker.apply_filter, connection_type
        )
        self.summary_requested.connect(
            self.window.worker.generate_summary, connection_type
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

    @Slot(str, str)
    def _on_index_object_requested(self, object_type: str, object_id: str) -> None:
        """Queue a re-embed request with debounce.

        Called when DataHandler emits ``index_object_requested`` after a
        Create/Update command finishes.  Instead of firing immediately
        (which would run ONNX-heavy code on the worker thread while the
        Chromium graph view is still updating), we debounce: each new
        request restarts a single-shot timer.  The actual embed fires
        only after :pyattr:`INDEX_DEBOUNCE_MS` of silence, by which time
        the UI has settled and the native-thread collision is avoided.

        Args:
            object_type: 'entity' or 'event'.
            object_id: UUID of the object to re-index.

        """
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        auto_index = settings.value("ai_auto_index_on_save", False)
        if isinstance(auto_index, str):
            auto_index = auto_index.lower() == "true"
        if not auto_index:
            return

        if getattr(self.window, "worker", None) is None:
            return

        self._pending_indices.add((object_type, object_id))
        self._index_timer.start(self.INDEX_DEBOUNCE_MS)
        logger.debug(
            "[WorkerManager] Re-embed debounced for %s %s (%d ms)",
            object_type,
            object_id,
            self.INDEX_DEBOUNCE_MS,
        )

    @Slot()
    def _flush_pending_index(self) -> None:
        """Fire the debounced re-embed requests now that the app is idle."""
        pending = self._pending_indices
        self._pending_indices = set()

        if not pending:
            return

        if getattr(self.window, "worker", None) is None:
            return

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        excluded_text = cast(
            str,
            settings.value("ai_search_excluded_attrs", "", type=str),
        )
        excluded = [attr.strip() for attr in excluded_text.split(",") if attr.strip()]

        for object_type, object_id in pending:
            logger.debug(
                "[WorkerManager] Flushing debounced re-embed: %s %s",
                object_type,
                object_id,
            )
            self._index_single_requested.emit(object_type, object_id, excluded)

    @Slot(bool)
    def on_db_initialized(self, success: bool) -> None:
        """Handler for database initialization result.

        Args:
            success: True if connection succeeded, False otherwise.

        """
        self.database_initialized = success
        if success:
            # Timeline callbacks read immutable snapshots cached on the GUI thread.
            self.window.timeline.set_data_provider(self.window)

            # Initialize backup service
            try:
                from src.core.backup_config import BackupConfig
                from src.services.backup_service import BackupService

                # Load backup config from settings or use defaults
                backup_config = BackupConfig()

                # Initialize backup service
                self.window.backup_service = BackupService(backup_config)
                self.window.backup_service.set_database_path(self.window.db_path)

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

            world_id = (
                self.window.current_world.id if self.window.current_world else "default"
            )
            self.initialize_history_requested.emit(world_id)

            self.window.data_coordinator.load_data()
            self.window.time_coordinator.request_calendar_config()
            self.window.time_coordinator.request_current_time()
            self.load_timeline_grouping_requested.emit()
            self.window.load_maps()
            self.load_ai_preferences_requested.emit()

            # Refresh AI search index status
            QTimer.singleShot(
                100, self.window.ai_search_manager.refresh_search_index_status
            )

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
        if self.package_smoke_callback is not None:
            self.package_smoke_callback(success)

    @Slot(object)
    def on_timeline_grouping_loaded(self, payload: object) -> None:
        """Forward worker-loaded grouping state to the grouping manager."""
        self.window.grouping_manager.on_grouping_snapshot_loaded(payload)

    @Slot(str)
    def on_world_theme_loaded(self, theme_name: str) -> None:
        """Apply the worker-loaded world theme on the GUI thread."""
        if not theme_name:
            return
        try:
            from src.core.theme_manager import ThemeManager

            ThemeManager().set_theme(theme_name)
            logger.info("Restored world theme: %s", theme_name)
        except Exception:
            logger.warning("Failed to restore world theme", exc_info=True)

    @Slot(object)
    def generate_summary(self, item: object) -> None:
        """Request summary generation from worker."""
        # Use signal instead of invokeMethod for reliability
        self.summary_requested.emit(item)
