"""
Main Application Entry Point.
Responsible for initializing the MainWindow, Workers, and UI components.
"""

import os
import sys

from PySide6.QtCore import (
    Q_ARG,
    QMetaObject,
    QSettings,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtCore import (
    Qt as QtCore_Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QWidget,
)

from src.app.command_coordinator import CommandCoordinator
from src.app.connection_manager import ConnectionManager

# Refactor Imports
from src.app.constants import (
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    IMAGE_FILE_FILTER,
    STATUS_DB_INIT_FAIL,
    STATUS_ERROR_PREFIX,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
    WINDOW_TITLE,
)
from src.app.data_handler import DataHandler
from src.app.ui_manager import UIManager
from src.commands.entity_commands import (
    CreateEntityCommand,
    DeleteEntityCommand,
    UpdateEntityCommand,
)

# Commands
from src.commands.event_commands import (
    CreateEventCommand,
    DeleteEventCommand,
    UpdateEventCommand,
)
from src.commands.longform_commands import (
    DemoteLongformEntryCommand,
    MoveLongformEntryCommand,
    PromoteLongformEntryCommand,
)
from src.commands.map_commands import (
    CreateMapCommand,
    CreateMarkerCommand,
    DeleteMapCommand,
    DeleteMarkerCommand,
    UpdateMarkerColorCommand,
    UpdateMarkerIconCommand,
)
from src.commands.relation_commands import (
    AddRelationCommand,
    RemoveRelationCommand,
    UpdateRelationCommand,
)
from src.commands.wiki_commands import ProcessWikiLinksCommand
from src.core.logging_config import get_logger, setup_logging
from src.core.paths import get_resource_path, get_user_data_path
from src.core.theme_manager import ThemeManager
from src.gui.widgets.entity_editor import EntityEditorWidget

# UI Components
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.longform_editor import LongformEditorWidget
from src.gui.widgets.map_widget import MapWidget
from src.gui.widgets.timeline import TimelineWidget
from src.gui.widgets.unified_list import UnifiedListWidget
from src.services import longform_builder
from src.services.db_service import DatabaseService
from src.services.worker import DatabaseWorker

# Initialize Logging
setup_logging(debug_mode=True)
logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """
    The main application window.

    Acts as the central controller for the UI, managing:
    - Dockable widgets (Lists, Editors, Timeline).
    - DatabaseWorker thread for async operations.
    - Signal/Slot connections between UI and persistent storage.

    Adheres to "Dumb UI" philosophy: logic delegates to Worker/Commands.
    """

    # Signal to send commands to worker thread
    command_requested = Signal(object)

    def __init__(self):
        """
        Initializes the MainWindow.

        Sets up:
        - Window Geometry & Title.
        - UI Manager (Docks & Layouts).
        - Worker Thread & Service connections.
        - UI Signals.
        """
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # 0. Initialize Data Handler (signals-based, no window reference)
        self.data_handler = DataHandler()

        # 1. Init Services (Worker Thread)
        self.init_worker()

        # 2. Init Widgets
        self.unified_list = UnifiedListWidget()
        self.event_editor = EventEditorWidget(self)
        self.entity_editor = EntityEditorWidget(self)

        # Connect dirty signals to update dock titles
        self.event_editor.dirty_changed.connect(
            lambda dirty: self._on_editor_dirty_changed(self.event_editor, dirty)
        )
        self.entity_editor.dirty_changed.connect(
            lambda dirty: self._on_editor_dirty_changed(self.entity_editor, dirty)
        )
        self.timeline = TimelineWidget()
        self.map_widget = MapWidget()

        # Data Cache for Unified List
        self._cached_events = []
        self._cached_entities = []
        self._cached_longform_sequence = []
        self.calendar_converter = None

        # Pending Selection (for creation flow)
        # Pending Selection (for creation flow)
        self._pending_select_id = None
        self._pending_select_type = None

        # Track last selection for undoing on cancel
        self._last_selected_id = None
        self._last_selected_type = None

        # Mapping from object_id to marker.id for position updates
        self._marker_object_to_id = {}

        self.longform_editor = LongformEditorWidget()

        # 3. Setup UI Layout via UIManager
        self.ui_manager = UIManager(self)
        self.ui_manager.setup_docks(
            {
                "unified_list": self.unified_list,
                "event_editor": self.event_editor,
                "entity_editor": self.entity_editor,
                "timeline": self.timeline,
                "longform_editor": self.longform_editor,
                "map_widget": self.map_widget,
            }
        )

        # 4. Initialize Connection Manager
        self.connection_manager = ConnectionManager(self)
        self.connection_manager.connect_all()

        # 5. Initialize Command Coordinator
        self.command_coordinator = CommandCoordinator(self)
        self.command_coordinator.command_requested.connect(
            lambda cmd: self.command_requested.emit(cmd)
        )

        # Central Widget
        self.setCentralWidget(QWidget())
        self.centralWidget().hide()

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Status Bar Time Labels
        self.lbl_world_time = QLabel("World: --")
        self.lbl_world_time.setMinimumWidth(250)
        self.lbl_world_time.setStyleSheet("color: #3498db; font-weight: bold;")  # Blue
        self.status_bar.addPermanentWidget(self.lbl_world_time)

        self.lbl_playhead_time = QLabel("Playhead: --")
        self.lbl_playhead_time.setMinimumWidth(250)
        self.lbl_playhead_time.setStyleSheet(
            "color: #e74c3c; font-weight: bold;"
        )  # Red
        self.status_bar.addPermanentWidget(self.lbl_playhead_time)

        # View Menu
        self.ui_manager.create_view_menu(self.menuBar())

        # Settings Menu (New)
        self.ui_manager.create_settings_menu(self.menuBar())

        # 5. Initialize Database (deferred to ensure event loop is running)
        QTimer.singleShot(
            100,
            lambda: QMetaObject.invokeMethod(
                self.worker, "initialize_db", QtCore_Qt.QueuedConnection
            ),
        )

        # 6. Restore Window State
        self._restore_window_state()

    @property
    def list_dock(self):
        """
        Gets the project list dock widget.

        Returns:
            QDockWidget: The dock widget containing the unified list.
        """
        return self.ui_manager.docks.get("list")

    @property
    def editor_dock(self):
        """
        Gets the event editor dock widget.

        Returns:
            QDockWidget: The dock widget containing the event editor.
        """
        return self.ui_manager.docks.get("event")

    @property
    def entity_editor_dock(self):
        """
        Gets the entity editor dock widget.

        Returns:
            QDockWidget: The dock widget containing the entity editor.
        """
        return self.ui_manager.docks.get("entity")

    @property
    def timeline_dock(self):
        """
        Gets the timeline dock widget.

        Returns:
            QDockWidget: The dock widget containing the timeline.
        """
        return self.ui_manager.docks.get("timeline")

    @property
    def longform_dock(self):
        """
        Gets the longform editor dock widget.

        Returns:
            QDockWidget: The dock widget containing the longform editor.
        """
        return self.ui_manager.docks.get("longform")

    @property
    def map_dock(self):
        """
        Gets the map dock widget.

        Returns:
            QDockWidget: The dock widget containing the map.
        """
        return self.ui_manager.docks.get("map")

    def _restore_window_state(self):
        """Restores window geometry and state from settings."""
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        geometry = settings.value("geometry")
        state = settings.value("windowState")

        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)
        else:
            self.ui_manager.reset_layout()

    def update_item(self, data):
        """
        Placeholder for generalized update.

        Currently unused as we split update_event/entity.
        """
        pass

    def load_data(self):
        """Refreshes both events and entities."""
        self.load_events()
        self.load_entities()
        self.load_longform_sequence()

    def _on_item_selected(self, item_type: str, item_id: str):
        """Handles selection from unified list or longform editor."""
        # Handle plural table names from longform editor
        if item_type == "events":
            item_type = "event"
        elif item_type == "entities":
            item_type = "entity"

        if item_type == "event":
            if not self.check_unsaved_changes(self.event_editor):
                # Attempt to revert - simplified for now, strictly just return
                # Visually the list might differ from detailed view if we just return
                return

            self.ui_manager.docks["event"].raise_()
            self.load_event_details(item_id)
            self._last_selected_id = item_id
            self._last_selected_type = "event"

        elif item_type == "entity":
            if not self.check_unsaved_changes(self.entity_editor):
                return

            self.ui_manager.docks["entity"].raise_()
            self.load_entity_details(item_id)
            self._last_selected_id = item_id
            self._last_selected_type = "entity"

    def check_unsaved_changes(self, editor) -> bool:
        """
        Checks if the editor has unsaved changes and prompts the user.

        Args:
            editor: The editor widget to check.

        Returns:
            bool: True if safe to proceed (Saved, Discarded, or Clean).
                  False if User Cancelled.
        """
        if (
            not hasattr(editor, "has_unsaved_changes")
            or not editor.has_unsaved_changes()
        ):
            return True

        # Determine readable name
        editor_name = "Item"
        if editor == self.event_editor:
            editor_name = "Event"
        elif editor == self.entity_editor:
            editor_name = "Entity"

        reply = QMessageBox.warning(
            self,
            "Unsaved Changes",
            f"You have unsaved changes in the {editor_name} Editor.\n"
            "Do you want to save them before proceeding?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )

        if reply == QMessageBox.Save:
            # Trigger save
            # We assume _on_save calls standard save mechanism
            if hasattr(editor, "_on_save"):
                editor._on_save()
            return True
        elif reply == QMessageBox.Discard:
            return True
        else:  # Cancel
            return False

    def _on_editor_dirty_changed(self, editor, dirty):
        """Updates the dock title with an asterisk if dirty."""
        dock_key = None

        # Determine which dock
        if editor == self.event_editor:
            dock_key = "event"
            # Get base title from constants (need to import or hardcode fallback)
            # Assuming UIManager set it initially. We can read current and strip *.
            base_title = "Event Inspector"
        elif editor == self.entity_editor:
            dock_key = "entity"
            base_title = "Entity Inspector"

        if dock_key:
            dock = self.ui_manager.docks.get(dock_key)
            if dock:
                new_title = base_title + (" *" if dirty else "")
                dock.setWindowTitle(new_title)

    @Slot(str, str)
    def _on_item_delete_requested(self, item_type: str, item_id: str):
        """Handles deletion request from unified list."""
        if item_type == "event":
            self.delete_event(item_id)
        elif item_type == "entity":
            self.delete_entity(item_id)

    def init_worker(self):
        """
        Initializes the DatabaseWorker and moves it to a separate thread.
        Connects all worker signals to MainWindow slots.
        """
        self.worker_thread = QThread()
        db_path = get_user_data_path("world.kraken")
        self.worker = DatabaseWorker(db_path)
        self.worker.moveToThread(self.worker_thread)

        # Connect Worker Signals
        self.worker.initialized.connect(self.on_db_initialized)
        self.worker.events_loaded.connect(self.data_handler.on_events_loaded)
        self.worker.entities_loaded.connect(self.data_handler.on_entities_loaded)
        self.worker.event_details_loaded.connect(
            self.data_handler.on_event_details_loaded
        )
        self.worker.entity_details_loaded.connect(
            self.data_handler.on_entity_details_loaded
        )
        self.worker.command_finished.connect(self.data_handler.on_command_finished)
        self.worker.operation_started.connect(self.update_status_message)
        self.worker.operation_finished.connect(self.clear_status_message)
        self.worker.error_occurred.connect(self.show_error_message)
        self.worker.longform_sequence_loaded.connect(
            self.data_handler.on_longform_sequence_loaded
        )
        self.worker.calendar_config_loaded.connect(self.on_calendar_config_loaded)
        self.worker.current_time_loaded.connect(self.on_current_time_loaded)
        self.worker.grouping_dialog_data_loaded.connect(
            self.on_grouping_dialog_data_loaded
        )
        self.worker.maps_loaded.connect(self.data_handler.on_maps_loaded)
        self.worker.markers_loaded.connect(self.data_handler.on_markers_loaded)

        # Connect MainWindow signal for sending commands to worker thread
        self.command_requested.connect(self.worker.run_command)

        # Connect Thread Start
        self.worker_thread.start()

    @Slot(str)
    def update_status_message(self, message: str):
        """
        Updates the status bar message and sets cursor to Wait.

        Args:
            message (str): The message to display.
        """
        self.status_bar.showMessage(message)
        # Busy cursor
        QApplication.setOverrideCursor(Qt.WaitCursor)

    @Slot(str)
    def clear_status_message(self, message: str):
        """
        Clears the status bar message after a delay and restores cursor.

        Args:
            message (str): The final completion message.
        """
        self.status_bar.showMessage(message, 3000)
        QApplication.restoreOverrideCursor()

    @Slot(str)
    def show_error_message(self, message: str):
        """
        Displays an error message in the status bar and logs it.

        Args:
            message (str): The error description.
        """
        self.status_bar.showMessage(f"{STATUS_ERROR_PREFIX}{message}", 5000)
        QApplication.restoreOverrideCursor()
        logger.error(message)

    @Slot(bool)
    def on_db_initialized(self, success):
        """
        Handler for database initialization result.

        Args:
            success (bool): True if connection succeeded, False otherwise.
        """
        if success:
            # Initialize GUI database connection for UI components
            try:
                db_path = get_user_data_path("world.kraken")
                self.gui_db_service = DatabaseService(db_path)
                self.gui_db_service.connect()
                self.timeline.set_db_service(self.gui_db_service)
            except Exception as e:
                logger.error(f"Failed to initialize GUI database service: {e}")

            self.load_data()
            self._request_calendar_config()
            self._request_current_time()
            self._request_grouping_config()
            self.load_maps()
        else:
            self.status_bar.showMessage(STATUS_DB_INIT_FAIL)

    def _request_calendar_config(self):
        """Requests loading of the active calendar config from the worker."""
        QMetaObject.invokeMethod(
            self.worker, "load_calendar_config", QtCore_Qt.QueuedConnection
        )

    @Slot(object)
    def on_calendar_config_loaded(self, config):
        """
        Handler for calendar config loaded from worker.

        Args:
            config: CalendarConfig or None.
        """
        try:
            from src.core.calendar import CalendarConfig, CalendarConverter

            if config:
                converter = CalendarConverter(config)
            else:
                # Use default if no active config
                default_config = CalendarConfig.create_default()
                converter = CalendarConverter(default_config)

            self.event_editor.set_calendar_converter(converter)
            self.timeline.set_calendar_converter(converter)

            # Check if UIManager has a pending calendar dialog
            self.ui_manager.show_calendar_dialog(config)

            # Save converter for status bar formatting
            self.calendar_converter = converter

            # Refresh status bar labels now that we have a converter
            if hasattr(self, "timeline"):
                self.update_world_time_label(self.timeline.get_current_time())
                self.update_playhead_time_label(self.timeline.get_playhead_time())

        except Exception as e:
            logger.warning(f"Failed to initialize calendar converter: {e}")

    def _request_current_time(self):
        """Requests loading of the current time from the worker."""
        QMetaObject.invokeMethod(
            self.worker, "load_current_time", QtCore_Qt.QueuedConnection
        )

    @Slot(float)
    def on_current_time_loaded(self, time: float):
        """
        Handler for current time loaded from worker.

        Args:
            time (float): The current time in lore_date units.
        """
        self.timeline.set_current_time(time)
        logger.debug(f"Current time loaded: {time}")

    @Slot(float)
    def on_current_time_changed(self, time: float):
        """
        Handler for when current time is changed in the timeline.
        Saves the new value to the database.

        Args:
            time (float): The new current time in lore_date units.
        """
        QMetaObject.invokeMethod(
            self.worker,
            "save_current_time",
            QtCore_Qt.QueuedConnection,
            Q_ARG(float, time),
        )
        logger.debug(f"Current time changed to: {time}")
        self.update_world_time_label(time)

    def update_world_time_label(self, time_val: float):
        """Updates the blue world time label."""
        text = self._format_time_string(time_val)
        self.lbl_world_time.setText(f"World: {text}")

    def update_playhead_time_label(self, time_val: float):
        """Updates the red playhead time label."""
        text = self._format_time_string(time_val)
        self.lbl_playhead_time.setText(f"Playhead: {text}")

    def _format_time_string(self, time_val: float) -> str:
        """Formats time using calendar converter if available."""
        if self.calendar_converter:
            return self.calendar_converter.format_date(time_val)
        return f"{time_val:.2f}"

    def on_command_finished_reload_longform(self):
        """Handler to reload longform sequence after command completion."""
        self.load_longform_sequence()

    def _request_grouping_config(self):
        """Requests loading of the timeline grouping configuration."""
        try:
            # Load from GUI db_service (thread-safe main thread usage)
            if hasattr(self, "gui_db_service"):
                config = self.gui_db_service.get_timeline_grouping_config()
                self.on_grouping_config_loaded(config)
        except Exception as e:
            logger.warning(f"Failed to load grouping config: {e}")

    def on_grouping_config_loaded(self, config):
        """
        Handler for grouping config loaded.

        Args:
            config: Dictionary with 'tag_order' and 'mode', or None.
        """
        if config:
            tag_order = config.get("tag_order", [])
            mode = config.get("mode", "DUPLICATE")
            if tag_order:
                # Apply grouping (db_service is already set in on_db_initialized)
                self.timeline.set_grouping_config(tag_order, mode)
                logger.info(
                    f"Auto-loaded grouping: {len(tag_order)} tags in {mode} mode"
                )
        else:
            logger.debug("No grouping configuration found")

    def closeEvent(self, event):
        """
        Handles application close event.
        Saves window geometry/state and strictly cleans up worker thread.
        Also checks for unsaved changes.
        """
        # Check unsaved changes
        for editor in [self.event_editor, self.entity_editor]:
            if not self.check_unsaved_changes(editor):
                event.ignore()
                return

        # Save State
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())

        self.worker_thread.quit()
        self.worker_thread.wait()
        event.accept()

    # ----------------------------------------------------------------------
    # Methods that request data from Worker
    # ----------------------------------------------------------------------

    def seed_data(self):
        """
        Populate the database with initial data (Deprecated).
        Current implementation is a placeholder.
        """
        # Checking if empty is hard without async check.
        # For now, let's just skip automatic seeding in this refactor or make it
        # a command. Ideally, we should have a 'CheckEmpty' command or similar.
        pass

    def load_events(self):
        """Requests loading of all events."""
        QMetaObject.invokeMethod(self.worker, "load_events", QtCore_Qt.QueuedConnection)

    def load_entities(self):
        """Requests loading of all entities."""
        QMetaObject.invokeMethod(
            self.worker, "load_entities", QtCore_Qt.QueuedConnection
        )

    def load_event_details(self, event_id: str):
        """Requests loading details for a specific event."""
        # Note: If called from selection, we already checked.
        # But if called programmatically, we might want to check here too?
        # Actually _on_item_selected calls this.
        # But for robust safety, checking here is good, unless it causes double prompts.
        # Let's rely on the caller (selection/navigation) to guard,
        # as this is a "request" and checking UI state inside
        # a low-level request might be mixing concerns slightly.
        # However, to start simple, we guard at user-interaction points.

        QMetaObject.invokeMethod(
            self.worker,
            "load_event_details",
            QtCore_Qt.QueuedConnection,
            Q_ARG(str, event_id),
        )

    def load_entity_details(self, entity_id: str):
        """Requests loading details for a specific entity."""
        QMetaObject.invokeMethod(
            self.worker,
            "load_entity_details",
            QtCore_Qt.QueuedConnection,
            Q_ARG(str, entity_id),
        )

    # DataHandler signal handlers (loose coupling via signals)
    @Slot(list)
    def _on_events_ready(self, events):
        """
        Handle events ready signal from DataHandler.

        Args:
            events: List of Event objects.
        """
        self._cached_events = events
        self.unified_list.set_data(self._cached_events, self._cached_entities)
        self.timeline.set_events(events)

    @Slot(list)
    def _on_entities_ready(self, entities):
        """
        Handle entities ready signal from DataHandler.

        Args:
            entities: List of Entity objects.
        """
        self._cached_entities = entities
        self.unified_list.set_data(self._cached_events, self._cached_entities)

    @Slot(list)
    def _on_suggestions_update(self, items):
        """
        Handle suggestions update request from DataHandler.

        Args:
            items: List of (id, name, type) tuples for completion.
        """
        self.event_editor.update_suggestions(items=items)
        self.entity_editor.update_suggestions(items=items)

    @Slot(object, list, list)
    def _on_event_details_ready(self, event, relations, incoming):
        """
        Handle event details ready signal from DataHandler.

        Args:
            event: The Event object.
            relations: List of outgoing relations.
            incoming: List of incoming relations.
        """
        self.event_editor.load_event(event, relations, incoming)

    @Slot(object, list, list)
    def _on_entity_details_ready(self, entity, relations, incoming):
        """
        Handle entity details ready signal from DataHandler.

        Args:
            entity: The Entity object.
            relations: List of outgoing relations.
            incoming: List of incoming relations.
        """
        self.entity_editor.load_entity(entity, relations, incoming)

    @Slot(list)
    def _on_longform_sequence_ready(self, sequence):
        """
        Handle longform sequence ready signal from DataHandler.

        Args:
            sequence: List of longform items.
        """
        self._cached_longform_sequence = sequence
        self.longform_editor.load_sequence(sequence)

    @Slot(list)
    def _on_maps_ready(self, maps):
        """
        Handle maps ready signal from DataHandler.

        Args:
            maps: List of Map objects.
        """
        self.map_widget.set_maps(maps)
        
        # Auto-select first map if none selected
        if maps:
            current_id = self.map_widget.map_selector.currentData()
            if not current_id:
                self.map_widget.select_map(maps[0].id)

    @Slot(str, list)
    def _on_markers_ready(self, map_id, processed_markers):
        """
        Handle markers ready signal from DataHandler.

        Args:
            map_id: The map ID these markers belong to.
            processed_markers: List of dicts with marker data.
        """
        # Verify we are still looking at this map
        current_map_id = self.map_widget.map_selector.currentData()
        if current_map_id != map_id:
            return

        self.map_widget.clear_markers()
        self._marker_object_to_id.clear()  # Reset mapping

        for marker_data in processed_markers:
            # Add marker to map
            self.map_widget.add_marker(
                marker_id=marker_data["object_id"],
                object_type=marker_data["object_type"],
                label=marker_data["label"],
                x=marker_data["x"],
                y=marker_data["y"],
                icon=marker_data["icon"],
                color=marker_data["color"],
            )

            # Store mapping for later updates (object_id -> marker.id)
            self._marker_object_to_id[marker_data["object_id"]] = marker_data["id"]

    @Slot(str)
    def _on_dock_raise_requested(self, dock_name):
        """
        Handle dock raise request from DataHandler.

        Args:
            dock_name: Name of the dock to raise ("event", "entity", etc).
        """
        if dock_name in self.ui_manager.docks:
            self.ui_manager.docks[dock_name].raise_()

    @Slot(str, str)
    def _on_selection_requested(self, item_type, item_id):
        """
        Handle selection request from DataHandler.

        Args:
            item_type: Type of item ("event" or "entity").
            item_id: ID of the item to select.
        """
        self.unified_list.select_item(item_type, item_id)

    @Slot(str)
    def _on_command_failed(self, message):
        """
        Handle command failure notification from DataHandler.

        Args:
            message: Error message from the failed command.
        """
        QMessageBox.warning(self, "Command Failed", message)

    @Slot()
    def _on_reload_active_editor_relations(self):
        """
        Reload relations for whichever editor is currently active.

        This is called after relation or wiki link commands complete.
        """
        if self.event_editor._current_event_id:
            self.load_event_details(self.event_editor._current_event_id)
        if self.entity_editor._current_entity_id:
            self.load_entity_details(self.entity_editor._current_entity_id)

    def delete_event(self, event_id):
        """
        Deletes an event by emitting a delete command.

        Args:
            event_id (str): The ID of the event to delete.
        """
        cmd = DeleteEventCommand(event_id)
        self.command_requested.emit(cmd)

    def update_event(self, event_data: dict):
        """
        Updates an event with the provided data.

        Args:
            event_data (dict): Dictionary containing event data
                including the 'id' field.
        """
        event_id = event_data.get("id")
        if not event_id:
            logger.error("Attempted to update event without ID.")
            return

        cmd = UpdateEventCommand(event_id, event_data)
        self.command_requested.emit(cmd)

        if "description" in event_data:
            wiki_cmd = ProcessWikiLinksCommand(event_id, event_data["description"])
            self.command_requested.emit(wiki_cmd)

    @Slot(str, float)
    def _on_event_date_changed(self, event_id: str, new_lore_date: float):
        """
        Handles event date changes from timeline dragging.
        Persists the new lore_date via UpdateEventCommand.

        Args:
            event_id: The ID of the event that was dragged.
            new_lore_date: The new lore_date value.
        """
        logger.debug(f"Event {event_id} date changed to {new_lore_date}")
        cmd = UpdateEventCommand(event_id, {"lore_date": new_lore_date})
        self.command_requested.emit(cmd)

    def create_entity(self):
        """
        Creates a new entity by emitting a create command.
        """
        if not self.check_unsaved_changes(self.entity_editor):
            return

        name, ok = QInputDialog.getText(self, "New Entity", "Entity Name:")
        if not ok or not name.strip():
            return

        cmd = CreateEntityCommand({"name": name.strip(), "type": "Concept"})
        self.command_requested.emit(cmd)

    def create_event(self):
        """
        Creates a new event by emitting a create command.
        """
        if not self.check_unsaved_changes(self.event_editor):
            return

        name, ok = QInputDialog.getText(self, "New Event", "Event Name:")
        if not ok or not name.strip():
            return

        cmd = CreateEventCommand({"name": name.strip(), "lore_date": 0.0})
        self.command_requested.emit(cmd)

    def delete_entity(self, entity_id):
        """
        Deletes an entity by emitting a delete command.

        Args:
            entity_id (str): The ID of the entity to delete.
        """
        cmd = DeleteEntityCommand(entity_id)
        self.command_requested.emit(cmd)

    def update_entity(self, entity_data: dict):
        """
        Updates an entity with the provided data.

        Args:
            entity_data (dict): Dictionary containing entity data
                including the 'id' field.
        """
        entity_id = entity_data.get("id")
        if not entity_id:
            logger.error("Attempted to update entity without ID.")
            return

        cmd = UpdateEntityCommand(entity_id, entity_data)
        self.command_requested.emit(cmd)

        if "description" in entity_data:
            wiki_cmd = ProcessWikiLinksCommand(entity_id, entity_data["description"])
            self.command_requested.emit(wiki_cmd)

    def add_relation(self, source_id, target_id, rel_type, bidirectional: bool = False):
        """
        Adds a relation between entities.

        Args:
            source_id (str): The ID of the source entity.
            target_id (str): The ID of the target entity.
            rel_type (str): The type of relation.
            bidirectional (bool, optional): Whether the relation is
                bidirectional. Defaults to False.
        """
        cmd = AddRelationCommand(
            source_id, target_id, rel_type, bidirectional=bidirectional
        )
        self.command_requested.emit(cmd)

    def load_maps(self):
        """Requests loading of all maps."""
        QMetaObject.invokeMethod(self.worker, "load_maps", QtCore_Qt.QueuedConnection)

    @Slot(str)
    def on_map_selected(self, map_id):
        """
        Handler for when a map is selected in the widget.
        Loads the map image and requests markers.
        """
        # Find map object
        maps = self.map_widget._maps_data
        selected_map = next((m for m in maps if m.id == map_id), None)
        if selected_map and selected_map.image_path:
            # Resolve relative path against project directory
            from pathlib import Path

            image_path = selected_map.image_path
            if not Path(image_path).is_absolute():
                project_dir = Path(self.worker.db_service.db_path).parent
                image_path = str(project_dir / image_path)

            self.map_widget.load_map(image_path)

            # Request markers
            QMetaObject.invokeMethod(
                self.worker,
                "load_markers",
                QtCore_Qt.QueuedConnection,
                Q_ARG(str, map_id),
            )

    def create_map(self):
        """Creates a new map via dialogs."""
        import shutil
        import uuid
        from pathlib import Path

        # 1. Select Image
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Map Image", "", IMAGE_FILE_FILTER
        )
        if not file_path:
            return

        # 2. Enter Name
        name, ok = QInputDialog.getText(self, "New Map", "Map Name:")
        if not ok or not name.strip():
            return

        # 3. Copy image to project assets folder
        source_path = Path(file_path)
        project_dir = Path(self.worker.db_service.db_path).parent
        assets_dir = project_dir / "assets" / "maps"
        assets_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename to avoid conflicts
        unique_suffix = uuid.uuid4().hex[:8]
        dest_filename = f"{source_path.stem}_{unique_suffix}{source_path.suffix}"
        dest_path = assets_dir / dest_filename

        try:
            shutil.copy2(source_path, dest_path)
            logger.info(f"Copied map image to: {dest_path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to copy image: {e}")
            return

        # Store relative path
        relative_path = str(dest_path.relative_to(project_dir))

        cmd = CreateMapCommand({"name": name.strip(), "image_path": relative_path})
        self.command_requested.emit(cmd)

    def delete_map(self):
        """Deletes the currently selected map."""
        map_id = self.map_widget.map_selector.currentData()
        if not map_id:
            return

        confirm = QMessageBox.question(
            self,
            "Delete Map",
            "Are you sure you want to delete this map and all its markers?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            cmd = DeleteMapCommand(map_id)
            self.command_requested.emit(cmd)

    def create_marker(self, x, y):
        """
        Creates a new marker at the given normalized coordinates.
        Prompts user to select an Entity or Event.
        """
        map_id = self.map_widget.map_selector.currentData()
        if not map_id:
            QMessageBox.warning(self, "No Map", "Please create or select a map first.")
            return

        # Simple choice: Entity or Event?
        # For a better UX, we could use a custom dialog with a search box.
        # For now, using InputDialog is tricky because we need UUIDs.
        # Better: Use a simple list selection from cached items.

        items = []
        # Format: "Name (Type)" -> (id, type)
        for e in self._cached_entities:
            items.append(f"{e.name} (Entity)")
        for e in self._cached_events:
            items.append(f"{e.name} (Event)")

        items.sort()

        item_text, ok = QInputDialog.getItem(
            self, "Add Marker", "Select Object:", items, 0, False
        )
        if not ok or not item_text:
            return

        # Parse result
        # This is a bit brittle if names contain " (Entity)", assuming endmatch
        if item_text.endswith(" (Entity)"):
            name = item_text[:-9]
            obj_type = "entity"
            # Find ID
            obj = next((e for e in self._cached_entities if e.name == name), None)
        elif item_text.endswith(" (Event)"):
            name = item_text[:-8]
            obj_type = "event"
            obj = next((e for e in self._cached_events if e.name == name), None)
        else:
            return

        if not obj:
            return

        cmd = CreateMarkerCommand(
            {
                "map_id": map_id,
                "object_id": obj.id,
                "object_type": obj_type,
                "x": x,
                "y": y,
                "label": obj.name,
            }
        )
        self.command_requested.emit(cmd)

    def _on_marker_dropped(
        self, item_id: str, item_type: str, item_name: str, x: float, y: float
    ):
        """
        Handle marker creation from drag-drop.

        Args:
            item_id: ID of the dropped entity/event.
            item_type: 'entity' or 'event'.
            item_name: Display name of the item.
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].
        """
        map_id = self.map_widget.get_selected_map_id()
        if not map_id:
            QMessageBox.warning(self, "No Map", "Please select a map first.")
            return

        cmd = CreateMarkerCommand(
            {
                "map_id": map_id,
                "object_id": item_id,
                "object_type": item_type,
                "x": x,
                "y": y,
                "label": item_name,
            }
        )
        self.command_requested.emit(cmd)
        logger.info(f"Creating marker for {item_type} '{item_name}' via drag-drop")

    def delete_marker(self, marker_id):
        """
        Deletes a marker.

        Args:
            marker_id: The object_id from the UI (not the actual marker.id).
        """
        # Translate object_id to actual marker ID
        actual_marker_id = self._marker_object_to_id.get(marker_id)
        if not actual_marker_id:
            logger.warning(f"No marker mapping found for object_id: {marker_id}")
            return

        confirm = QMessageBox.question(
            self,
            "Delete Marker",
            "Remove this marker?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            # Remove marker from UI immediately for instant feedback
            self.map_widget.remove_marker(marker_id)
            # Also remove from mapping
            del self._marker_object_to_id[marker_id]
            # Then execute the database command
            cmd = DeleteMarkerCommand(actual_marker_id)
            self.command_requested.emit(cmd)

    @Slot(str, str)
    def _on_marker_clicked(self, marker_id: str, object_type: str):
        """
        Handle marker click from MapWidget.

        Args:
            marker_id: The ID of the item.
            object_type: 'event' or 'entity'.
        """
        logger.info(
            f"_on_marker_clicked called: marker_id={marker_id}, "
            f"object_type={object_type}"
        )
        if object_type == "event":
            if not self.check_unsaved_changes(self.event_editor):
                return
            self.load_event_details(marker_id)
            self._last_selected_id = marker_id
            self._last_selected_type = "event"
            self.ui_manager.docks["event"].raise_()

        elif object_type == "entity":
            if not self.check_unsaved_changes(self.entity_editor):
                return
            self.load_entity_details(marker_id)
            self._last_selected_id = marker_id
            self._last_selected_type = "entity"
            self.ui_manager.docks["entity"].raise_()

    @Slot(str, str)
    def _on_marker_icon_changed(self, marker_id: str, icon: str):
        """
        Handle marker icon change from MapWidget.

        Args:
            marker_id: ID of the marker (actually object_id from view)
            icon: New icon filename
        """
        # Translate object_id to actual marker ID
        actual_marker_id = self._marker_object_to_id.get(marker_id)
        if not actual_marker_id:
            logger.warning(f"No marker mapping found for object_id: {marker_id}")
            return
        cmd = UpdateMarkerIconCommand(marker_id=actual_marker_id, icon=icon)
        self.command_requested.emit(cmd)

    @Slot(str, str)
    def _on_marker_color_changed(self, marker_id: str, color: str):
        """
        Handle marker color change from MapWidget.

        Args:
            marker_id: ID of the marker (actually object_id from view)
            color: New color hex code
        """
        # Translate object_id to actual marker ID
        actual_marker_id = self._marker_object_to_id.get(marker_id)
        if not actual_marker_id:
            logger.warning(f"No marker mapping found for object_id: {marker_id}")
            return
        cmd = UpdateMarkerColorCommand(marker_id=actual_marker_id, color=color)
        self.command_requested.emit(cmd)

    @Slot(str, float, float)
    def _on_marker_position_changed(self, marker_id: str, x: float, y: float):
        """
        Handle marker position change from MapWidget.

        Args:
            marker_id: ID of the marker (actually object_id from view)
            x: New normalized X coordinate
            y: New normalized Y coordinate
        """
        # Translate object_id to actual marker ID
        actual_marker_id = self._marker_object_to_id.get(marker_id)
        if not actual_marker_id:
            logger.warning(f"No marker mapping found for object_id: {marker_id}")
            return
        # Import the command
        from src.commands.map_commands import UpdateMarkerPositionCommand

        cmd = UpdateMarkerPositionCommand(marker_id=actual_marker_id, x=x, y=y)
        self.command_requested.emit(cmd)

    # ----------------------------------------------------------------------
    # Timeline Grouping Methods
    # ----------------------------------------------------------------------

    def _on_configure_grouping_requested(self):
        """Opens grouping configuration dialog by requesting data from worker thread."""
        # Request data from worker thread (thread-safe)
        QMetaObject.invokeMethod(
            self.worker, "load_grouping_dialog_data", QtCore_Qt.QueuedConnection
        )

    @Slot(list, object)
    def on_grouping_dialog_data_loaded(self, tags_data, current_config):
        """
        Handler for grouping dialog data loaded from worker.

        Args:
            tags_data: List of dicts with 'name', 'color', 'count' for each tag.
            current_config: Current grouping config dict or None.
        """
        from src.gui.dialogs.grouping_config_dialog import GroupingConfigDialog

        try:
            # Create dialog with pre-loaded data
            dialog = GroupingConfigDialog(
                tags_data,
                current_config,
                self.command_coordinator,
                self,
            )
            dialog.grouping_applied.connect(self._on_grouping_applied)
            dialog.exec()

        except Exception as e:
            logger.error(f"Failed to open grouping dialog: {e}")
            self.show_error_message(f"Failed to open grouping dialog: {e}")

    @Slot(list, str)
    def _on_grouping_applied(self, tag_order: list, mode: str):
        """
        Handle grouping applied from dialog.

        Args:
            tag_order: List of tag names in order.
            mode: Grouping mode (DUPLICATE or FIRST_MATCH).
        """
        # Update timeline view
        self.timeline.set_grouping_config(tag_order, mode)
        logger.info(f"Grouping applied: {len(tag_order)} tags in {mode} mode")

    def _on_clear_grouping_requested(self):
        """Clears timeline grouping."""
        from src.commands.timeline_grouping_commands import ClearTimelineGroupingCommand

        cmd = ClearTimelineGroupingCommand()
        self.command_requested.emit(cmd)
        # Also clear UI
        self.timeline.clear_grouping()
        logger.info("Timeline grouping cleared")

    @Slot(str)
    def _on_tag_color_change_requested(self, tag_name: str):
        """
        Handle tag color change from band context menu.

        Args:
            tag_name: The name of the tag to change color for.
        """
        from PySide6.QtWidgets import QColorDialog

        from src.commands.timeline_grouping_commands import UpdateTagColorCommand

        color = QColorDialog.getColor()
        if color.isValid():
            cmd = UpdateTagColorCommand(tag_name, color.name())
            self.command_requested.emit(cmd)
            logger.debug(f"Tag color changed: {tag_name} -> {color.name()}")

    @Slot(str)
    def _on_remove_from_grouping_requested(self, tag_name: str):
        """
        Remove a tag from current grouping.

        Args:
            tag_name: The name of the tag to remove.
        """
        from src.commands.timeline_grouping_commands import SetTimelineGroupingCommand

        # Get current config
        current_config = self.worker.db_service.get_timeline_grouping_config()
        if current_config:
            tag_order = current_config["tag_order"]
            if tag_name in tag_order:
                tag_order.remove(tag_name)
                cmd = SetTimelineGroupingCommand(tag_order, current_config["mode"])
                self.command_requested.emit(cmd)
                self.timeline.set_grouping_config(tag_order, current_config["mode"])
                logger.info(f"Removed '{tag_name}' from grouping")

    def remove_relation(self, rel_id):
        """
        Removes a relation by its ID.

        Args:
            rel_id (str): The ID of the relation to remove.
        """
        cmd = RemoveRelationCommand(rel_id)
        self.command_requested.emit(cmd)

    def update_relation(self, rel_id, target_id, rel_type):
        """
        Updates an existing relation.

        Args:
            rel_id (str): The ID of the relation to update.
            target_id (str): The new target entity ID.
            rel_type (str): The new relation type.
        """
        cmd = UpdateRelationCommand(rel_id, target_id, rel_type)
        self.command_requested.emit(cmd)

    def navigate_to_entity(self, target: str):
        """
        Navigates to the entity or event with the given name or ID.

        Handles both ID-based links (UUIDs) and legacy name-based links.
        Uses cached entities and events for quick lookup.

        Args:
            target (str): Entity/event name or UUID.
        """
        logger.info(f"Navigating to target: {target}")

        # Check if target is a valid UUID format
        import re

        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        is_uuid = uuid_pattern.match(target) is not None

        if is_uuid:
            # ID-based navigation - direct lookup
            entity = next((e for e in self._cached_entities if e.id == target), None)
            if entity:
                if not self.check_unsaved_changes(self.entity_editor):
                    return
                self.load_entity_details(entity.id)
                return

            event = next((e for e in self._cached_events if e.id == target), None)
            if event:
                if not self.check_unsaved_changes(self.event_editor):
                    return
                self.load_event_details(event.id)
                return

            # ID not found - broken link
            QMessageBox.warning(
                self,
                "Broken Link",
                f"The linked item (ID: {target[:8]}...) no longer exists.",
            )
        else:
            # Name-based navigation (legacy) - case-insensitive match
            entity = next(
                (e for e in self._cached_entities if e.name.lower() == target.lower()),
                None,
            )

            if entity:
                if not self.check_unsaved_changes(self.entity_editor):
                    return
                self.load_entity_details(entity.id)
                return

            # Also check events for name-based links
            event = next(
                (e for e in self._cached_events if e.name.lower() == target.lower()),
                None,
            )

            if event:
                if not self.check_unsaved_changes(self.event_editor):
                    return
                self.load_event_details(event.id)
                return

            # Name not found - Prompt for Creation
            self._prompt_create_missing_target(target)

    def _prompt_create_missing_target(self, target_name: str):
        """
        Prompts the user to create a missing entity or event from a broken link.

        Args:
            target_name (str): The name of the missing item.
        """
        msg = QMessageBox(self)
        msg.setWindowTitle("Target Not Found")
        msg.setText(f"Item '{target_name}' does not exist.")
        msg.setInformativeText("Would you like to create it?")

        btn_entity = msg.addButton("Create Entity", QMessageBox.AcceptRole)
        btn_event = msg.addButton("Create Event", QMessageBox.AcceptRole)
        msg.addButton(QMessageBox.Cancel)

        msg.exec()

        clicked = msg.clickedButton()

        if clicked == btn_entity:
            # Create Entity
            if not self.check_unsaved_changes(self.entity_editor):
                return

            # Use target name as default
            cmd = CreateEntityCommand({"name": target_name, "type": "Concept"})
            self.command_requested.emit(cmd)
            # We rely on on_command_finished to handle selection/loading
            # But we need to ensure the new item is selected.
            # CreateEntityCommand result handling in on_command_finished
            # sets _pending_select_id, which should handle it.

        elif clicked == btn_event:
            # Create Event
            if not self.check_unsaved_changes(self.event_editor):
                return

            cmd = CreateEventCommand({"name": target_name, "lore_date": 0.0})
            self.command_requested.emit(cmd)

    def load_longform_sequence(self, doc_id: str = longform_builder.DOC_ID_DEFAULT):
        """Requests loading of the longform document sequence."""
        QMetaObject.invokeMethod(
            self.worker,
            "load_longform_sequence",
            QtCore_Qt.QueuedConnection,
            Q_ARG(str, doc_id),
        )

    def promote_longform_entry(self, table: str, row_id: str, old_meta: dict):
        """
        Promotes a longform entry by reducing its depth.

        Args:
            table (str): Table name ("events" or "entities").
            row_id (str): ID of the item to promote.
            old_meta (dict): Previous longform metadata for undo.
        """
        cmd = PromoteLongformEntryCommand(table, row_id, old_meta)
        self.command_requested.emit(cmd)

    def demote_longform_entry(self, table: str, row_id: str, old_meta: dict):
        """
        Demotes a longform entry by increasing its depth.

        Args:
            table (str): Table name ("events" or "entities").
            row_id (str): ID of the item to demote.
            old_meta (dict): Previous longform metadata for undo.
        """
        cmd = DemoteLongformEntryCommand(table, row_id, old_meta)
        self.command_requested.emit(cmd)

    def move_longform_entry(
        self, table: str, row_id: str, old_meta: dict, new_meta: dict
    ):
        """
        Moves a longform entry to a new position.

        Args:
            table (str): Table name.
            row_id (str): ID.
            old_meta (dict): Old metadata.
            new_meta (dict): New metadata with position/parent/depth.
        """
        cmd = MoveLongformEntryCommand(table, row_id, old_meta, new_meta)
        self.command_requested.emit(cmd)

    def export_longform_document(self):
        """
        Exports the current longform document to Markdown.
        Opens a file dialog for the user to choose save location.
        """
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Longform Document",
            "longform_document.md",
            "Markdown Files (*.md);;All Files (*)",
        )

        if file_path:
            try:
                lines = []
                for item in self._cached_longform_sequence:
                    heading_level = item["heading_level"]
                    title = item["meta"].get("title_override") or item["name"]
                    heading = "#" * heading_level + " " + title
                    lines.append(heading)
                    lines.append("")

                    content = item.get("content", "").strip()
                    if content:
                        lines.append(content)
                        lines.append("")
                    lines.append("")

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))

                self.status_bar.showMessage(f"Exported to {file_path}", 3000)
            except Exception as e:
                logger.error(f"Failed to export longform document: {e}")
                self.status_bar.showMessage(f"Export failed: {e}", 5000)


def main():
    """
    Main entry point.
    Configures High DPI scaling, Theme, and launches MainWindow.
    """
    try:
        logger.info("Starting Application...")
        # 1. High DPI Scaling
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        app = QApplication(sys.argv)

        # 2. Apply Theme
        tm = ThemeManager()
        try:
            qss_path = get_resource_path(os.path.join("src", "resources", "main.qss"))
            with open(qss_path, "r") as f:
                qss_template = f.read()
                tm.apply_theme(app, qss_template)
        except FileNotFoundError:
            logger.warning("main.qss not found, skipping styling.")

        window = MainWindow()
        window.show()

        logger.info("Entering Event Loop...")
        sys.exit(app.exec())
    except Exception:
        logger.exception("CRITICAL: Unhandled exception in main application loop")
        sys.exit(1)


if __name__ == "__main__":
    main()
