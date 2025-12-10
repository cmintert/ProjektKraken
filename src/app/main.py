"""
Main Application Entry Point.
Responsible for initializing the MainWindow, Workers, and UI components.
"""

import sys

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QStatusBar,
    QMessageBox,
)
from PySide6.QtCore import Qt, QSettings, QThread, Slot, Signal, QTimer, QMetaObject, Qt as QtCore_Qt, Q_ARG

from src.core.logging_config import setup_logging, get_logger
from src.core.theme_manager import ThemeManager
from src.services.worker import DatabaseWorker
from src.commands.base_command import CommandResult

# UI Components
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.unified_list import UnifiedListWidget
from src.gui.widgets.timeline import TimelineWidget

# Commands
from src.commands.event_commands import (
    CreateEventCommand,
    DeleteEventCommand,
    UpdateEventCommand,
)
from src.commands.entity_commands import (
    CreateEntityCommand,
    DeleteEntityCommand,
    UpdateEntityCommand,
)
from src.commands.relation_commands import (
    AddRelationCommand,
    RemoveRelationCommand,
    UpdateRelationCommand,
)
from src.commands.wiki_commands import ProcessWikiLinksCommand

# Refactor Imports
from src.app.constants import (
    WINDOW_TITLE, DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT,
    WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP, STATUS_DB_INIT_FAIL, STATUS_ERROR_PREFIX
)
from src.app.ui_manager import UIManager

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

        # 1. Init Services (Worker Thread)
        self.init_worker()

        # 2. Init Widgets
        self.unified_list = UnifiedListWidget()
        self.event_editor = EventEditorWidget()
        self.entity_editor = EntityEditorWidget()
        self.timeline = TimelineWidget()

        # Data Cache for Unified List
        self._cached_events = []
        self._cached_entities = []

        # 3. Setup UI Layout via UIManager
        self.ui_manager = UIManager(self)
        self.ui_manager.setup_docks({
            'unified_list': self.unified_list,
            'event_editor': self.event_editor,
            'entity_editor': self.entity_editor,
            'timeline': self.timeline
        })

        # 4. Connect Signals
        self._connect_signals()

        # Central Widget
        self.setCentralWidget(QWidget())
        self.centralWidget().hide()

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # View Menu
        self.ui_manager.create_view_menu(self.menuBar())

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
        return self.ui_manager.docks.get('list')

    @property
    def editor_dock(self):
        return self.ui_manager.docks.get('event')

    @property
    def entity_editor_dock(self):
        return self.ui_manager.docks.get('entity')

    @property
    def timeline_dock(self):
        return self.ui_manager.docks.get('timeline')

    def _connect_signals(self):
        """Connects all UI signals to their respective slots."""
        # Unified List
        self.unified_list.refresh_requested.connect(self.load_data)
        self.unified_list.create_event_requested.connect(self.create_event)
        self.unified_list.create_entity_requested.connect(self.create_entity)
        self.unified_list.delete_requested.connect(self._on_item_delete_requested)
        self.unified_list.item_selected.connect(self._on_item_selected)

        # Editors
        for editor in [self.event_editor, self.entity_editor]:
            editor.save_requested.connect(self.update_item)  # Generalized update
            editor.add_relation_requested.connect(self.add_relation)
            editor.remove_relation_requested.connect(self.remove_relation)
            editor.update_relation_requested.connect(self.update_relation)
        
        # Specific connections if needed (generalized above, but keeping specific if logic differs)
        self.event_editor.save_requested.disconnect(self.update_item)
        self.entity_editor.save_requested.disconnect(self.update_item)
        
        self.event_editor.save_requested.connect(self.update_event)
        self.entity_editor.save_requested.connect(self.update_entity)

        self.event_editor.link_clicked.connect(self.navigate_to_entity)
        self.entity_editor.link_clicked.connect(self.navigate_to_entity)

        # Timeline
        self.timeline.event_selected.connect(self.load_event_details)

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
        """Placeholder for generalized update, currently unused as we split update_event/entity."""
        pass

    def load_data(self):
        """Refreshes both events and entities."""
        self.load_events()
        self.load_entities()

    @Slot(str, str)
    def _on_item_selected(self, item_type: str, item_id: str):
        """Handles selection from unified list."""
        if item_type == "event":
            self.ui_manager.docks['event'].raise_()
            self.load_event_details(item_id)
        elif item_type == "entity":
            self.ui_manager.docks['entity'].raise_()
            self.load_entity_details(item_id)

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
        self.worker = DatabaseWorker("world.kraken")
        self.worker.moveToThread(self.worker_thread)

        # Connect Worker Signals
        self.worker.initialized.connect(self.on_db_initialized)
        self.worker.events_loaded.connect(self.on_events_loaded)
        self.worker.entities_loaded.connect(self.on_entities_loaded)
        self.worker.event_details_loaded.connect(self.on_event_details_loaded)
        self.worker.entity_details_loaded.connect(self.on_entity_details_loaded)
        self.worker.command_finished.connect(self.on_command_finished)
        self.worker.operation_started.connect(self.update_status_message)
        self.worker.operation_finished.connect(self.clear_status_message)
        self.worker.error_occurred.connect(self.show_error_message)

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
            self.load_data()
        else:
            self.status_bar.showMessage(STATUS_DB_INIT_FAIL)

    @Slot(list)
    def on_events_loaded(self, events):
        """
        Updates the UI with the loaded events.
        """
        self._cached_events = events
        self.unified_list.set_data(self._cached_events, self._cached_entities)
        self.timeline.set_events(events)
        self.status_bar.showMessage(f"Loaded {len(events)} events.")

    @Slot(list)
    def on_entities_loaded(self, entities):
        """
        Updates the UI with loaded entities.
        """
        self._cached_entities = entities
        self.unified_list.set_data(self._cached_events, self._cached_entities)
        self.status_bar.showMessage(f"Loaded {len(entities)} entities.")

    @Slot(object, list, list)
    def on_event_details_loaded(self, event, relations, incoming):
        """
        Populates the Event Editor with detailed event data.

        Args:
            event (Event): The event object.
            relations (list): Outgoing relations.
            incoming (list): Incoming relations.
        """
        self.ui_manager.docks['event'].raise_()
        self.event_editor.load_event(event, relations, incoming)
        self.timeline.focus_event(event.id)

    @Slot(object, list, list)
    def on_entity_details_loaded(self, entity, relations, incoming):
        """
        Populates the Entity Editor with detailed entity data.

        Args:
            entity (Entity): The entity object.
            relations (list): Outgoing relations.
            incoming (list): Incoming relations.
        """
        self.ui_manager.docks['entity'].raise_()
        self.entity_editor.load_entity(entity, relations, incoming)

    @Slot(object)
    def on_command_finished(self, result):
        """
        Handles completion of async commands, triggering necessary UI refreshes.

        Args:
            result (CommandResult): The result of the executed command.
        """
        if not isinstance(result, CommandResult):
            # Fallback or error
            return

        command_name = result.command_name
        success = result.success
        message = result.message

        # Determine what to reload based on command
        if not success:
            if message:
                QMessageBox.warning(self, "Command Failed", message)
            return

        if "Event" in command_name:
            self.load_events()
            # If we just updated/created, maybe refresh details if active?
            # For now, simplistic reload is fine
        if "Entity" in command_name:
            self.load_entities()
        if "Relation" in command_name:
            # Reload both to be safe, or check active editor
            # Accessing private props is a bit smelly, but acceptable for now
            if self.event_editor._current_event_id:
                self.load_event_details(self.event_editor._current_event_id)
            if self.entity_editor._current_entity_id:
                self.load_entity_details(self.entity_editor._current_entity_id)

    def closeEvent(self, event):
        """
        Handles application close event.
        Saves window geometry/state and strictly cleans up worker thread.
        """
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

    def delete_event(self, event_id):
        cmd = DeleteEventCommand(event_id)
        self.command_requested.emit(cmd)

    def update_event(self, event_data: dict):
        event_id = event_data.get("id")
        if not event_id:
            logger.error("Attempted to update event without ID.")
            return

        cmd = UpdateEventCommand(event_id, event_data)
        self.command_requested.emit(cmd)

        if "description" in event_data:
            wiki_cmd = ProcessWikiLinksCommand(event_id, event_data["description"])
            self.command_requested.emit(wiki_cmd)

    def create_entity(self):
        cmd = CreateEntityCommand()
        self.command_requested.emit(cmd)

    def create_event(self):
        cmd = CreateEventCommand()
        self.command_requested.emit(cmd)

    def delete_entity(self, entity_id):
        cmd = DeleteEntityCommand(entity_id)
        self.command_requested.emit(cmd)

    def update_entity(self, entity_data: dict):
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
        cmd = AddRelationCommand(
            source_id, target_id, rel_type, bidirectional=bidirectional
        )
        self.command_requested.emit(cmd)

    def remove_relation(self, rel_id):
        cmd = RemoveRelationCommand(rel_id)
        self.command_requested.emit(cmd)

    def update_relation(self, rel_id, target_id, rel_type):
        cmd = UpdateRelationCommand(rel_id, target_id, rel_type)
        self.command_requested.emit(cmd)

    def navigate_to_entity(self, name: str):
        """
        Navigates to the entity with the given name.
        Uses cached entities for quick lookup.
        """
        logger.info(f"Navigating to entity: {name}")
        # Case-insensitive match
        target = next(
            (e for e in self._cached_entities if e.name.lower() == name.lower()), None
        )

        if target:
            self.load_entity_details(target.id)
        else:
            QMessageBox.information(
                self, "Link Not Found", f"Entity '{name}' not found."
            )


def main():
    """
    Main entry point.
    Configures High DPI scaling, Theme, and launches MainWindow.
    """
    logger.info("Starting Application...")
    # 1. High DPI Scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

    # 2. Apply Theme
    tm = ThemeManager()
    try:
        with open("src/resources/main.qss", "r") as f:
            qss_template = f.read()
            tm.apply_theme(app, qss_template)
    except FileNotFoundError:
        logger.warning("main.qss not found, skipping styling.")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
