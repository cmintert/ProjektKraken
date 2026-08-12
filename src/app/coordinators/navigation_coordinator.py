"""Coordinate selection and navigation between world objects."""

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

from PySide6.QtCore import QSettings, Slot
from PySide6.QtWidgets import QMessageBox

from src.app.constants import (
    NAVIGATION_SELECTION_DELAY_MS,
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
        """Initialize navigation state for the main window."""
        super().__init__(main_window)

        # State
        self._last_selected_id: Optional[str] = None
        self._last_selected_type: Optional[str] = None

        # Delayed Selection State
        self._pending_selection: Optional[tuple[str, str]] = None
        from PySide6.QtCore import QTimer

        self._selection_timer = QTimer()
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(NAVIGATION_SELECTION_DELAY_MS)
        self._selection_timer.timeout.connect(self._perform_delayed_selection)

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
            self.main_window.data_coordinator.load_event_details(item_id)
            # Sync Timeline (Focus and Select)
            self.main_window.timeline.focus_event(item_id)

        elif item_type == "entity":
            self.main_window.ui_manager.docks["entity"].raise_()
            self.main_window.data_coordinator.load_entity_details(item_id)

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

        # Strip "id:" prefix if present
        if target.lower().startswith("id:"):
            target = target[3:]

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
                (
                    e
                    for e in self.main_window.data_coordinator.cached_entities
                    if e.id == target
                ),
                None,
            ):
                self.set_global_selection("entity", entity.id)
                return

            if event := next(
                (
                    e
                    for e in self.main_window.data_coordinator.cached_events
                    if e.id == target
                ),
                None,
            ):
                self.set_global_selection("event", event.id)
                return

            # ID not found - broken link
            QMessageBox.warning(
                self.main_window,
                "Broken Link",
                f"The linked item (ID: {target[:8]}...) no longer exists.\n\n"
                "This link may have been broken because:\n"
                "• The item was deleted\n"
                "• The link was created in a different world/database\n"
                "• Data corruption occurred\n\n"
                "To fix:\n"
                "1. Remove or update the broken link\n"
                "2. Search for the item by name in the Unified List\n"
                "3. Create a new link to the correct item",
            )
        else:
            # Name-based navigation (legacy) - case-insensitive match
            if entity := next(
                (
                    e
                    for e in self.main_window.data_coordinator.cached_entities
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
                    for e in self.main_window.data_coordinator.cached_events
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
        # Start delayed selection to allow drag operations to cancel it
        self._pending_selection = (item_type, item_id)
        self._selection_timer.start()

    @Slot()
    def on_drag_started(self) -> None:
        """Handles drag start event to cancel pending selection."""
        # Stop timer to prevent new selection from taking effect
        if self._selection_timer.isActive():
            self._selection_timer.stop()
            self._pending_selection = None
            logger.debug(
                "[NavigationCoordinator] Selection cancelled due to drag start"
            )

        # Revert list selection to the currently active global selection
        # This ensures the dragged item doesn't appear selected in the UI
        selected_id = self._last_selected_id
        selected_type = self._last_selected_type
        if selected_id and selected_type:
            # We must use a slight delay or QMetaObject.invokeMethod because
            # dragging might still be processing mouse events
            from PySide6.QtCore import QTimer

            QTimer.singleShot(
                0,
                lambda: self.main_window.unified_list.select_item(
                    selected_type, selected_id
                ),
            )
        else:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(
                0, self.main_window.unified_list.list_widget.clearSelection
            )

    def _perform_delayed_selection(self) -> None:
        """Executes the pending selection."""
        if self._pending_selection:
            item_type, item_id = self._pending_selection
            self.set_global_selection(item_type, item_id)
            self._pending_selection = None

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
            app_coordinator = getattr(self.main_window, "app_coordinator", None)
            context = getattr(app_coordinator, "context_tags", None)
            entity_data: dict[str, Any] = {
                "name": target_name,
                "type": "Concept",
            }
            entity_command = (
                context.create_entity_command(entity_data)
                if context
                else CreateEntityCommand(entity_data)
            )
            self.main_window.command_requested.emit(entity_command)

        elif clicked == btn_event:
            # Create Event
            if not self.main_window.check_unsaved_changes(
                self.main_window.event_editor
            ):
                return

            app_coordinator = getattr(self.main_window, "app_coordinator", None)
            context = getattr(app_coordinator, "context_tags", None)
            event_data: dict[str, Any] = {
                "name": target_name,
                "lore_date": 0.0,
            }
            event_command = (
                context.create_event_command(event_data)
                if context
                else CreateEventCommand(event_data)
            )
            self.main_window.command_requested.emit(event_command)
