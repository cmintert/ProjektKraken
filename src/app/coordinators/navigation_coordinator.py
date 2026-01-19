import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

from PySide6.QtCore import QSettings, Slot
from PySide6.QtWidgets import QMessageBox

from src.app.constants import (
    SETTINGS_LAST_ITEM_ID_KEY,
    SETTINGS_LAST_ITEM_TYPE_KEY,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.app.coordinators.base_coordinator import BaseCoordinator
from src.commands.entity_commands import CreateEntityCommand
from src.commands.event_commands import CreateEventCommand

logger = logging.getLogger(__name__)


class NavigationCoordinator(BaseCoordinator):
    """Coordinator for Navigation and Selection state.

    Handles:
    - Global selection synchronization (Editors, List, Graph, Timeline).
    - Navigation requests (via ID or Name).
    - State persistence (restoring last selection).
    - Missing target creation workflows.
    """

    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__(main_window)

        # State
        self._last_selected_id: Optional[str] = None
        self._last_selected_type: Optional[str] = None

    @Slot(str, str)
    def set_global_selection(self, item_type: str, item_id: str) -> None:
        """Centralized method to handle global item selection.

        Synchronizes all UI components:
        - Editors
        - Unified List (Project Explorer)
        - Graph Focus
        - Timeline Selection
        - Last Selected State
        """
        # 1. Normalize type
        if item_type == "events":
            item_type = "event"
        elif item_type == "entities":
            item_type = "entity"

        # 2. Avoid redundant updates if already selected
        if item_id == self._last_selected_id and item_type == self._last_selected_type:
            return

        # 3. Check for unsaved changes before switching context
        # Determine target editor to check
        target_editor = (
            self.main_window.event_editor
            if item_type == "event"
            else self.main_window.entity_editor
        )
        if not self.main_window.check_unsaved_changes(target_editor):
            return

        # 4. Perform Selection & UI Updates
        logger.debug(f"[NavigationCoordinator] Global selection: {item_type}/{item_id}")

        self._last_selected_id = item_id
        self._last_selected_type = item_type

        # Update Settings
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        settings.setValue(SETTINGS_LAST_ITEM_ID_KEY, item_id)
        settings.setValue(SETTINGS_LAST_ITEM_TYPE_KEY, item_type)

        if item_type == "event":
            self.main_window.ui_manager.docks["event"].raise_()
            self.main_window.load_event_details(item_id)

        elif item_type == "entity":
            self.main_window.ui_manager.docks["entity"].raise_()
            self.main_window.load_entity_details(item_id)

        # 5. Sync Project Explorer (Unified List)
        # This ensures the list highlights the item even if selected via Graph/Link
        self.main_window.unified_list.select_item(item_type, item_id)

        # 6. Sync Graph (Focus Node)
        # self.main_window.graph_widget.focus_node(item_id)

    @Slot(str)
    def navigate_to_entity(self, target: str) -> None:
        """Navigates to the entity or event with the given name or ID.

        Handles both ID-based links (UUIDs) and legacy name-based links.
        Uses cached entities and events for quick lookup.
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
            if entity := next(
                (e for e in self.main_window._cached_entities if e.id == target),
                None,
            ):
                self.set_global_selection("entity", entity.id)
                return

            if event := next(
                (e for e in self.main_window._cached_events if e.id == target), None
            ):
                self.set_global_selection("event", event.id)
                return

            # ID not found - broken link
            QMessageBox.warning(
                self.main_window,
                "Broken Link",
                f"The linked item (ID: {target[:8]}...) no longer exists.",
            )
        else:
            # Name-based navigation (legacy) - case-insensitive match
            if entity := next(
                (
                    e
                    for e in self.main_window._cached_entities
                    if e.name.lower() == target.lower()
                ),
                None,
            ):
                self.set_global_selection("entity", entity.id)
                return

            # Also check events for name-based links
            if event := next(
                (
                    e
                    for e in self.main_window._cached_events
                    if e.name.lower() == target.lower()
                ),
                None,
            ):
                self.set_global_selection("event", event.id)
                return

            # Name not found - Prompt for Creation
            self._prompt_create_missing_target(target)

    @property
    def selected_id(self) -> Optional[str]:
        """Returns the currently selected item ID."""
        return self._last_selected_id

    @selected_id.setter
    def selected_id(self, value: Optional[str]) -> None:
        """Sets the selected item ID."""
        self._last_selected_id = value

    @property
    def selected_type(self) -> Optional[str]:
        """Returns the currently selected item type."""
        return self._last_selected_type

    @selected_type.setter
    def selected_type(self, value: Optional[str]) -> None:
        """Sets the selected item type."""
        self._last_selected_type = value

    @Slot(str, str)
    def on_item_selected(self, item_type: str, item_id: str) -> None:
        """Handles selection from unified list or longform editor."""
        self.set_global_selection(item_type, item_id)

    def restore_last_selection(self) -> None:
        """Restores the last selected item from settings."""
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        last_id = settings.value(SETTINGS_LAST_ITEM_ID_KEY)
        last_type = settings.value(SETTINGS_LAST_ITEM_TYPE_KEY)

        if last_id and last_type:
            logger.debug(f"Restoring last selection: {last_type}/{last_id}")
            self.set_global_selection(last_type, last_id)

    def _prompt_create_missing_target(self, target_name: str) -> None:
        """Prompts the user to create a missing entity or event from a broken link."""
        msg = QMessageBox(self.main_window)
        msg.setWindowTitle("Target Not Found")
        msg.setText(f"Item '{target_name}' does not exist.")
        msg.setInformativeText("Would you like to create it?")

        btn_entity = msg.addButton("Create Entity", QMessageBox.ButtonRole.AcceptRole)
        btn_event = msg.addButton("Create Event", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton(QMessageBox.StandardButton.Cancel)

        msg.exec()

        clicked = msg.clickedButton()

        if clicked == btn_entity:
            # Create Entity
            if not self.main_window.check_unsaved_changes(
                self.main_window.entity_editor
            ):
                return

            # Use target name as default
            cmd = CreateEntityCommand({"name": target_name, "type": "Concept"})
            self.main_window.command_requested.emit(cmd)

        elif clicked == btn_event:
            # Create Event
            if not self.main_window.check_unsaved_changes(
                self.main_window.event_editor
            ):
                return

            cmd = CreateEventCommand({"name": target_name, "lore_date": 0.0})
            self.main_window.command_requested.emit(cmd)
