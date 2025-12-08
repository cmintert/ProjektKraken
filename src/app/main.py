import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QDockWidget, QWidget
from PySide6.QtCore import Qt, QSettings
from src.core.logging_config import setup_logging, get_logger
from src.core.theme_manager import ThemeManager
from src.services.db_service import DatabaseService
from src.gui.widgets.event_list import EventListWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.entity_list import EntityListWidget
from src.gui.widgets.entity_editor import EntityEditorWidget
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

        # 1. Init Services
        # Using a file DB now for persistence across runs
        self.db_service = DatabaseService("world.kraken")
        self.db_service.connect()

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

        # View Menu
        self.create_view_menu()

        # Seed & Load
        self.seed_data()
        self.load_events()
        self.load_entities()

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

        self.db_service.close()
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

    def seed_data(self):
        if not self.db_service.get_all_events():
            logger.info("Seeding initial data...")
            e1 = Event(name="Big Bang", lore_date=-13800000000.0, type="cosmic")
            e2 = Event(name="Start of Campaign", lore_date=1000.0, type="session")
            e3 = Event(name="The Dragon Attacks", lore_date=1001.5, type="combat")

            cmd1 = CreateEventCommand(self.db_service, e1)
            cmd1.execute()
            cmd2 = CreateEventCommand(self.db_service, e2)
            cmd2.execute()
            self.db_service.insert_event(e3)  # Direct insert just to vary it

        if not self.db_service.get_all_entities():
            # Seed entities
            ent1 = Entity(name="Gandalf", type="Character", description="A Wizard")
            ent2 = Entity(
                name="The Shire", type="Location", description="A peaceful place"
            )

            CreateEntityCommand(self.db_service, ent1).execute()
            CreateEntityCommand(self.db_service, ent2).execute()

    def load_events(self):
        logger.debug("Loading events from DB...")
        events = self.db_service.get_all_events()
        self.event_list.set_events(events)
        self.timeline.set_events(events)

    def load_entities(self):
        logger.debug("Loading entities from DB...")
        entities = self.db_service.get_all_entities()
        self.entity_list.set_entities(entities)

    def load_event_details(self, event_id: str):
        """Fetches full event details AND relations, pushing to editor."""
        logger.debug(f"Loading details for {event_id}")

        # Raise the docks
        self.list_dock.raise_()
        self.editor_dock.raise_()

        event = self.db_service.get_event(event_id)
        if event:
            # Also fetch relations
            relations = self.db_service.get_relations(event_id)
            incoming_relations = self.db_service.get_incoming_relations(event_id)
            self.event_editor.load_event(event, relations, incoming_relations)

            # Sync Timeline Focus
            self.timeline.focus_event(event_id)

    def load_entity_details(self, entity_id: str):
        logger.debug(f"Loading entity details for {entity_id}")

        # Raise the docks
        self.entity_list_dock.raise_()
        self.entity_editor_dock.raise_()

        entity = self.db_service.get_entity(entity_id)
        if entity:
            relations = self.db_service.get_relations(entity_id)
            incoming_relations = self.db_service.get_incoming_relations(entity_id)
            self.entity_editor.load_entity(entity, relations, incoming_relations)

    def delete_event(self, event_id):
        logger.info(f"Requesting delete for {event_id}")
        cmd = DeleteEventCommand(self.db_service, event_id)
        if cmd.execute():
            self.load_events()  # Refresh lists
            # Disable editor if we deleted the active item?
            # Ideally yes, but tricky to track 'active' strictly without more state.

    def update_event(self, event: Event):
        logger.info(f"Requesting update for {event.id}")
        cmd = UpdateEventCommand(self.db_service, event)
        if cmd.execute():
            self.load_events()  # Update list (e.g. name might have changed)
            # Re-load to confirm state or just stay as is
            # self.load_event_details(event.id)

    # -----------------------------
    # Entity Actions
    # -----------------------------

    def create_entity(self):
        new_entity = Entity(name="New Entity", type="Concept")
        cmd = CreateEntityCommand(self.db_service, new_entity)
        if cmd.execute():
            self.load_entities()
            # Select and load it
            self.entity_list.set_entities(self.db_service.get_all_entities())
            # We could scroll to it, but for now just refresh

    def delete_entity(self, entity_id):
        logger.info(f"Requesting delete for entity {entity_id}")
        cmd = DeleteEntityCommand(self.db_service, entity_id)
        if cmd.execute():
            self.load_entities()
            self.entity_editor.clear()

    def update_entity(self, entity: Entity):
        logger.info(f"Requesting update for entity {entity.id}")
        cmd = UpdateEntityCommand(self.db_service, entity)
        if cmd.execute():
            self.load_entities()

    # -----------------------------
    # Relations
    # -----------------------------

    def add_relation(self, source_id, target_id, rel_type, bidirectional: bool = False):
        logger.info(
            f"Adding rel {source_id} -> {target_id} [{rel_type}] (bi={bidirectional})"
        )
        cmd = AddRelationCommand(
            self.db_service, source_id, target_id, rel_type, bidirectional=bidirectional
        )
        if cmd.execute():
            # Refresh editor details to show new relation
            # Check both, one will work
            if self.event_editor._current_event_id == source_id:
                self.load_event_details(source_id)
            if self.entity_editor._current_entity_id == source_id:
                self.load_entity_details(source_id)

    def remove_relation(self, rel_id):
        logger.info(f"Removing relation {rel_id}")
        cmd = RemoveRelationCommand(self.db_service, rel_id)
        if cmd.execute():
            # Refresh active editors
            if self.event_editor._current_event_id:
                self.load_event_details(self.event_editor._current_event_id)
            if self.entity_editor._current_entity_id:
                self.load_entity_details(self.entity_editor._current_entity_id)

    def update_relation(self, rel_id, target_id, rel_type):
        logger.info(f"Updating relation {rel_id}")
        cmd = UpdateRelationCommand(self.db_service, rel_id, target_id, rel_type)
        if cmd.execute():
            if self.event_editor._current_event_id:
                self.load_event_details(self.event_editor._current_event_id)
            if self.entity_editor._current_entity_id:
                self.load_entity_details(self.entity_editor._current_entity_id)


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
