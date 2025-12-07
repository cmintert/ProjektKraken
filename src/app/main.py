import sys
import logging
from PySide6.QtWidgets import QApplication, QMainWindow, QDockWidget
from PySide6.QtCore import Qt
from src.core.logging_config import setup_logging, get_logger
from src.services.db_service import DatabaseService
from src.gui.widgets.event_list import EventListWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.commands.event_commands import (
    CreateEventCommand,
    DeleteEventCommand,
    UpdateEventCommand,
)
from src.commands.relation_commands import AddRelationCommand
from src.core.events import Event

# Initialize Logging
setup_logging(debug_mode=True)
logger = get_logger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Kraken - v0.2.0 (Editor Phase)")
        self.resize(1280, 720)

        # 1. Init Services
        # Using a file DB now for persistence across runs
        self.db_service = DatabaseService("world.kraken")
        self.db_service.connect()

        # 2. Init Widgets
        self.event_list = EventListWidget()
        self.event_editor = EventEditorWidget()

        # Dockable List
        list_dock = QDockWidget("Events List", self)
        list_dock.setWidget(self.event_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, list_dock)

        # Dockable Editor (or separate window, but dock is fine)
        editor_dock = QDockWidget("Event Inspector", self)
        editor_dock.setWidget(self.event_editor)
        self.addDockWidget(Qt.RightDockWidgetArea, editor_dock)

        # 3. Connect Signals (The Controller Logic)
        self.event_list.refresh_requested.connect(self.load_events)
        self.event_list.delete_requested.connect(self.delete_event)
        self.event_list.event_selected.connect(self.load_event_details)

        self.event_editor.save_requested.connect(self.update_event)
        self.event_editor.add_relation_requested.connect(self.add_relation)

        # Seed some data if empty
        self.seed_data()
        self.load_events()

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

    def load_events(self):
        logger.debug("Loading events from DB...")
        events = self.db_service.get_all_events()
        self.event_list.set_events(events)

    def load_event_details(self, event_id: str):
        """Fetches full event details AND relations, pushing to editor."""
        logger.debug(f"Loading details for {event_id}")
        event = self.db_service.get_event(event_id)
        if event:
            # Also fetch relations
            relations = self.db_service.get_relations(event_id)
            self.event_editor.load_event(event, relations)

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

    def add_relation(self, source_id, target_id, rel_type):
        logger.info(f"Adding relation {source_id} -> {target_id} [{rel_type}]")
        cmd = AddRelationCommand(self.db_service, source_id, target_id, rel_type)
        if cmd.execute():
            # Refresh editor details to show new relation
            self.load_event_details(source_id)

    def closeEvent(self, event):
        self.db_service.close()
        event.accept()


def main():
    logger.info("Starting Application...")
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
