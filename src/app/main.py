"""
Main Application Entry Point.
Responsible for initializing the MainWindow, Workers, and UI components.
"""

import sys

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QDockWidget,
    QWidget,
    QStatusBar,
    QTextEdit,
    QTabWidget,
)
from PySide6.QtCore import Qt, QSettings, QThread, Slot, Signal
from src.core.logging_config import setup_logging, get_logger
from src.core.theme_manager import ThemeManager
from src.core.events import Event
from src.core.entities import Entity
from src.services.worker import DatabaseWorker

# DatabaseService import removed as MainWindow uses Worker
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.unified_list import UnifiedListWidget
from src.gui.widgets.timeline import TimelineWidget
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
from src.core.events import Event
from src.core.entities import Entity

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
        - Dock Widgets & Layouts.
        - Worker Thread & Service connections.
        - UI Signals & View Menu.
        """
        super().__init__()
        self.setWindowTitle("Project Kraken - v0.2.0 (Editor Phase)")
        self.resize(1280, 720)

        # Enable advanced docking features
        self.setDockOptions(
            QMainWindow.AnimatedDocks
            | QMainWindow.AllowNestedDocks
            | QMainWindow.AllowTabbedDocks
        )
        # Set tabs to appear at the top
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)

        # 1. Init Services (Worker Thread)
        self.init_worker()

        # 2. Init Widgets
        self.unified_list = UnifiedListWidget()
        self.event_editor = EventEditorWidget()
        self.entity_editor = EntityEditorWidget()

        # Data Cache for Unified List
        self._cached_events = []
        self._cached_entities = []

        # Dockable List (Project Explorer)
        self.list_dock = QDockWidget("Project Explorer", self)
        self.list_dock.setObjectName("ProjectExplorerDock")
        self.list_dock.setWidget(self.unified_list)
        self.list_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.list_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        self.addDockWidget(Qt.LeftDockWidgetArea, self.list_dock)

        # Dockable Editor (Events)
        self.editor_dock = QDockWidget("Event Inspector", self)
        self.editor_dock.setObjectName("EventInspectorDock")
        self.editor_dock.setWidget(self.event_editor)
        self.editor_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.editor_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        self.addDockWidget(Qt.RightDockWidgetArea, self.editor_dock)

        # Dockable Editor (Entities)
        self.entity_editor_dock = QDockWidget("Entity Inspector", self)
        self.entity_editor_dock.setObjectName("EntityInspectorDock")
        self.entity_editor_dock.setWidget(self.entity_editor)
        self.entity_editor_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.entity_editor_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        self.addDockWidget(Qt.RightDockWidgetArea, self.entity_editor_dock)
        self.tabifyDockWidget(self.editor_dock, self.entity_editor_dock)

        # 3. Connect Signals
        # Unified List
        self.unified_list.refresh_requested.connect(self.load_data)
        self.unified_list.create_event_requested.connect(self.create_event)
        self.unified_list.create_entity_requested.connect(self.create_entity)
        self.unified_list.delete_requested.connect(self._on_item_delete_requested)
        self.unified_list.item_selected.connect(self._on_item_selected)

        # Editors
        self.event_editor.save_requested.connect(self.update_event)
        self.event_editor.add_relation_requested.connect(self.add_relation)
        self.event_editor.remove_relation_requested.connect(self.remove_relation)
        self.event_editor.update_relation_requested.connect(self.update_relation)

        self.entity_editor.save_requested.connect(self.update_entity)
        self.entity_editor.add_relation_requested.connect(self.add_relation)
        self.entity_editor.remove_relation_requested.connect(self.remove_relation)
        self.entity_editor.update_relation_requested.connect(self.update_relation)

        # Timeline (Dockable)
        self.timeline_dock = QDockWidget("Timeline", self)
        self.timeline_dock.setObjectName("TimelineDock")
        self.timeline = TimelineWidget()
        self.timeline_dock.setWidget(self.timeline)
        self.timeline_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.timeline_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        self.addDockWidget(Qt.BottomDockWidgetArea, self.timeline_dock)

        self.timeline.event_selected.connect(self.load_event_details)

        # Central Widget
        self.setCentralWidget(QWidget())
        self.centralWidget().hide()

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # View Menu
        self.create_view_menu()

        # 4. Initialize Database (deferred to ensure event loop is running)
        # Use QMetaObject.invokeMethod to call on worker thread
        from PySide6.QtCore import QTimer, QMetaObject, Qt as QtCore_Qt

        QTimer.singleShot(
            100,
            lambda: QMetaObject.invokeMethod(
                self.worker, "initialize_db", QtCore_Qt.QueuedConnection
            ),
        )

        # 5. Restore Window State
        settings = QSettings("Antigravity", "ProjectKraken_v0.3.1")
        geometry = settings.value("geometry")
        state = settings.value("windowState")

        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)
        else:
            # First run or reset: ensure default layout is applied
            self.reset_layout()

    def load_data(self):
        """Refreshes both events and entities."""
        self.load_events()
        self.load_entities()

    @Slot(str, str)
    def _on_item_selected(self, item_type: str, item_id: str):
        """Handles selection from unified list."""
        if item_type == "event":
            self.editor_dock.raise_()
            self.load_event_details(item_id)
        elif item_type == "entity":
            self.entity_editor_dock.raise_()
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
        self.status_bar.showMessage(f"Error: {message}", 5000)
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
            self.status_bar.showMessage("Database Initialization Failed!")

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
        self.editor_dock.raise_()
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
        self.entity_editor_dock.raise_()
        self.entity_editor.load_entity(entity, relations, incoming)

    @Slot(str, bool)
    def on_command_finished(self, command_name, success):
        """
        Handles completion of async commands, triggering necessary UI refreshes.

        Args:
            command_name (str): Name of the executed command.
            success (bool): Whether the command succeeded.
        """
        # Determine what to reload based on command
        if not success:
            return

        if "Event" in command_name:
            self.load_events()
            # If we just updated/created, maybe refresh details if active?
            # For now, simplistic reload is fine
        if "Entity" in command_name:
            self.load_entities()
        if "Relation" in command_name:
            # Reload both to be safe, or check active editor
            if self.event_editor._current_event_id:
                self.load_event_details(self.event_editor._current_event_id)
            if self.entity_editor._current_entity_id:
                self.load_entity_details(self.entity_editor._current_entity_id)

    def create_view_menu(self):
        """Creates the View menu for toggling docks."""
        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.list_dock.toggleViewAction())
        view_menu.addAction(self.editor_dock.toggleViewAction())
        view_menu.addAction(self.entity_editor_dock.toggleViewAction())
        view_menu.addAction(self.timeline_dock.toggleViewAction())

        view_menu.addSeparator()

        reset_action = view_menu.addAction("Reset Layout")
        reset_action.triggered.connect(self.reset_layout)

    def closeEvent(self, event):
        """
        Handles application close event.
        Saves window geometry/state and strictly cleans up worker thread.
        """
        # Save State
        from PySide6.QtCore import QSettings

        settings = QSettings("Antigravity", "ProjectKraken_v0.3.1")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())

        # self.db_service.close() # handled by thread cleanup ideally, or manual stop
        self.worker_thread.quit()
        self.worker_thread.wait()
        event.accept()

    def reset_layout(self):
        """Restores the default docking layout configuration."""
        # Restore default docking
        self.addDockWidget(Qt.LeftDockWidgetArea, self.list_dock)
        # self.entity_list_dock removed in Unified List update
        # self.tabifyDockWidget... removed

        self.addDockWidget(Qt.RightDockWidgetArea, self.editor_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.entity_editor_dock)
        self.tabifyDockWidget(self.editor_dock, self.entity_editor_dock)

        self.addDockWidget(Qt.BottomDockWidgetArea, self.timeline_dock)

        self.list_dock.show()
        # self.entity_list_dock.show()
        self.editor_dock.show()
        self.entity_editor_dock.show()
        self.timeline_dock.show()

    # ----------------------------------------------------------------------
    # Methods that request data from Worker
    # ----------------------------------------------------------------------

    def seed_data(self):
        # Checking if empty is hard without async check.
        # For now, let's just skip automatic seeding in this refactor or make it
        # a command. Ideally, we should have a 'CheckEmpty' command or similar.
        pass

    def load_events(self):
        """Requests loading of all events."""
        from PySide6.QtCore import QMetaObject, Qt as QtCore_Qt

        QMetaObject.invokeMethod(self.worker, "load_events", QtCore_Qt.QueuedConnection)

    def load_entities(self):
        """Requests loading of all entities."""
        from PySide6.QtCore import QMetaObject, Qt as QtCore_Qt

        QMetaObject.invokeMethod(
            self.worker, "load_entities", QtCore_Qt.QueuedConnection
        )

    def load_event_details(self, event_id: str):
        """Requests loading details for a specific event."""
        from PySide6.QtCore import QMetaObject, Qt as QtCore_Qt, Q_ARG

        QMetaObject.invokeMethod(
            self.worker,
            "load_event_details",
            QtCore_Qt.QueuedConnection,
            Q_ARG(str, event_id),
        )

    def load_entity_details(self, entity_id: str):
        """Requests loading details for a specific entity."""
        from PySide6.QtCore import QMetaObject, Qt as QtCore_Qt, Q_ARG

        QMetaObject.invokeMethod(
            self.worker,
            "load_entity_details",
            QtCore_Qt.QueuedConnection,
            Q_ARG(str, entity_id),
        )

    def delete_event(self, event_id):
        cmd = DeleteEventCommand(event_id)
        self.command_requested.emit(cmd)

    def update_event(self, event: Event):
        cmd = UpdateEventCommand(event)
        self.command_requested.emit(cmd)

    def create_entity(self):
        new_entity = Entity(name="New Entity", type="Concept")
        cmd = CreateEntityCommand(new_entity)
        self.command_requested.emit(cmd)

    def create_event(self):
        new_event = Event(name="New Event", lore_date=0.0)
        cmd = CreateEventCommand(new_event)
        self.command_requested.emit(cmd)

    def delete_entity(self, entity_id):
        cmd = DeleteEntityCommand(entity_id)
        self.command_requested.emit(cmd)

    def update_entity(self, entity: Entity):
        cmd = UpdateEntityCommand(entity)
        self.command_requested.emit(cmd)

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


def main():
    """
    Main entry point.
    Configures High DPI scaling, Theme, and launches MainWindow.
    """
    logger.info("Starting Application...")
    # 1. High DPI Scaling (Spec 2.2)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

    # 2. Apply Theme (Spec 3.2)
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
