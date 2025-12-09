import sys

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QDockWidget,
    QWidget,
    QStatusBar,
)
from PySide6.QtCore import Qt, QSettings, QThread, Slot
from src.core.logging_config import setup_logging, get_logger
from src.core.theme_manager import ThemeManager
from src.services.worker import DatabaseWorker

# DatabaseService import removed as MainWindow uses Worker
from src.gui.widgets.event_list import EventListWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.entity_list import EntityListWidget
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.timeline import TimelineWidget
from src.commands.event_commands import (
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Kraken - v0.2.0 (Editor Phase)")
        self.resize(1280, 720)

        # Enable advanced docking features
        self.setDockOptions(
            QMainWindow.AnimatedDocks
            | QMainWindow.AllowNestedDocks
            | QMainWindow.AllowTabbedDocks
        )

        # 1. Init Services (Worker Thread)
        self.init_worker()

        # 2. Init Widgets
        self.event_list = EventListWidget()
        self.event_editor = EventEditorWidget()

        self.entity_list = EntityListWidget()
        self.entity_editor = EntityEditorWidget()

        # Dockable List (Events)
        self.list_dock = QDockWidget("Events List", self)
        self.list_dock.setObjectName("EventsListDock")
        self.list_dock.setWidget(self.event_list)
        self.list_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.list_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        self.addDockWidget(Qt.LeftDockWidgetArea, self.list_dock)

        # Dockable List (Entities)
        self.entity_list_dock = QDockWidget("Entities List", self)
        self.entity_list_dock.setObjectName("EntitiesListDock")
        self.entity_list_dock.setWidget(self.entity_list)
        self.entity_list_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.entity_list_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        self.addDockWidget(Qt.LeftDockWidgetArea, self.entity_list_dock)
        self.tabifyDockWidget(
            self.list_dock, self.entity_list_dock
        )  # Tabify with events

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

        # 3. Connect Signals (Events)
        self.event_list.refresh_requested.connect(self.load_events)
        self.event_list.delete_requested.connect(self.delete_event)
        self.event_list.event_selected.connect(self.load_event_details)
        self.event_editor.save_requested.connect(self.update_event)

        # 3b. Connect Signals (Entities)
        self.entity_list.refresh_requested.connect(self.load_entities)
        self.entity_list.delete_requested.connect(self.delete_entity)
        self.entity_list.create_requested.connect(self.create_entity)
        self.entity_list.entity_selected.connect(self.load_entity_details)
        self.entity_editor.save_requested.connect(self.update_entity)

        # Entity Relations
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

        # Seed & Load is now triggered via worker signals or after init
        # in showEvent/post-init. We will trigger init_db in main() or after show.
        # Let's do it at the end of init
        self.worker.initialize_db()

        # Restore State
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

    def init_worker(self):
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

        # Connect Thread Start
        self.worker_thread.start()

    @Slot(str)
    def update_status_message(self, message: str):
        self.status_bar.showMessage(message)
        # Busy cursor
        QApplication.setOverrideCursor(Qt.WaitCursor)

    @Slot(str)
    def clear_status_message(self, message: str):
        self.status_bar.showMessage(message, 3000)
        QApplication.restoreOverrideCursor()

    @Slot(str)
    def show_error_message(self, message: str):
        self.status_bar.showMessage(f"Error: {message}", 5000)
        QApplication.restoreOverrideCursor()
        logger.error(message)

    @Slot(bool)
    def on_db_initialized(self, success):
        if success:
            self.load_events()
            self.load_entities()
        else:
            self.status_bar.showMessage("Database Initialization Failed!")

    @Slot(list)
    def on_events_loaded(self, events):
        self.event_list.set_events(events)
        self.timeline.set_events(events)

    @Slot(list)
    def on_entities_loaded(self, entities):
        self.entity_list.set_entities(entities)

    @Slot(object, list, list)
    def on_event_details_loaded(self, event, relations, incoming):
        self.editor_dock.raise_()
        self.event_editor.load_event(event, relations, incoming)
        self.timeline.focus_event(event.id)

    @Slot(object, list, list)
    def on_entity_details_loaded(self, entity, relations, incoming):
        self.entity_editor_dock.raise_()
        self.entity_editor.load_entity(entity, relations, incoming)

    @Slot(str, bool)
    def on_command_finished(self, command_name, success):
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
        menu_bar = self.menuBar()
        view_menu = menu_bar.addMenu("View")

        # Add actions to toggle docks
        view_menu.addAction(self.list_dock.toggleViewAction())
        view_menu.addAction(self.entity_list_dock.toggleViewAction())
        view_menu.addAction(self.editor_dock.toggleViewAction())
        view_menu.addAction(self.entity_editor_dock.toggleViewAction())
        view_menu.addAction(self.timeline_dock.toggleViewAction())

        view_menu.addSeparator()

        reset_action = view_menu.addAction("Reset Layout")
        reset_action.triggered.connect(self.reset_layout)

    def closeEvent(self, event):
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
        # Restore default docking
        self.addDockWidget(Qt.LeftDockWidgetArea, self.list_dock)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.entity_list_dock)
        self.tabifyDockWidget(self.list_dock, self.entity_list_dock)

        self.addDockWidget(Qt.RightDockWidgetArea, self.editor_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.entity_editor_dock)
        self.tabifyDockWidget(self.editor_dock, self.entity_editor_dock)

        self.addDockWidget(Qt.BottomDockWidgetArea, self.timeline_dock)

        self.list_dock.show()
        self.entity_list_dock.show()
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
        self.worker.load_events()

    def load_entities(self):
        self.worker.load_entities()

    def load_event_details(self, event_id: str):
        self.worker.load_event_details(event_id)

    def load_entity_details(self, entity_id: str):
        self.worker.load_entity_details(entity_id)

    def delete_event(self, event_id):
        cmd = DeleteEventCommand(event_id)
        self.worker.run_command(cmd)

    def update_event(self, event: Event):
        cmd = UpdateEventCommand(event)
        self.worker.run_command(cmd)

    def create_entity(self):
        new_entity = Entity(name="New Entity", type="Concept")
        cmd = CreateEntityCommand(new_entity)
        self.worker.run_command(cmd)

    def delete_entity(self, entity_id):
        cmd = DeleteEntityCommand(entity_id)
        self.worker.run_command(cmd)

    def update_entity(self, entity: Entity):
        cmd = UpdateEntityCommand(entity)
        self.worker.run_command(cmd)

    def add_relation(self, source_id, target_id, rel_type, bidirectional: bool = False):
        cmd = AddRelationCommand(
            source_id, target_id, rel_type, bidirectional=bidirectional
        )
        self.worker.run_command(cmd)

    def remove_relation(self, rel_id):
        cmd = RemoveRelationCommand(rel_id)
        self.worker.run_command(cmd)

    def update_relation(self, rel_id, target_id, rel_type):
        cmd = UpdateRelationCommand(rel_id, target_id, rel_type)
        self.worker.run_command(cmd)


def main():
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
