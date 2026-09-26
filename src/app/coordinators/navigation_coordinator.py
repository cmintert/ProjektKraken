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
        self._pending_navigation: tuple[str, str, str, str, int] | None = None
        self._save_signal_connected = False

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

        if self._pending_navigation is not None:
            self._restore_selection()
            return

        if not self._guard_navigation(item_type, item_id):
            return

        logger.debug(f"[NavigationCoordinator] Global selection: {item_type}/{item_id}")

        self._last_selected_id = item_id
        self._last_selected_type = item_type

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        settings.setValue(SETTINGS_LAST_ITEM_ID_KEY, item_id)
        settings.setValue(SETTINGS_LAST_ITEM_TYPE_KEY, item_type)

        if item_type == "event":
            self.main_window.workspace.show_panel("event")
            self.main_window.data_coordinator.load_event_details(item_id)
            self.main_window.timeline.focus_event(item_id)
        elif item_type == "entity":
            self.main_window.workspace.show_panel("entity")
            self.main_window.data_coordinator.load_entity_details(item_id)

        self.main_window.unified_list.select_item(item_type, item_id)

    def _guard_navigation(self, item_type: str, item_id: str) -> bool:
        """Protect every draft that a destination selection would abandon."""
        candidates: list[tuple[str, Any]] = []
        if self._last_selected_type in {"event", "entity"}:
            source = self._editor_for(self._last_selected_type)
            candidates.append((self._last_selected_type, source))
        if item_type in {"event", "entity"}:
            target = self._editor_for(item_type)
            current_id = (
                target.current_event_id if item_type == "event"
                else target.current_entity_id
            )
            if current_id != item_id and all(target is not e for _, e in candidates):
                candidates.append((item_type, target))
        for editor_type, editor in candidates:
            if not editor.has_unsaved_changes():
                continue
            reply = QMessageBox.warning(
                self.main_window,
                "Unsaved Changes",
                f"You have unsaved changes in the {editor_type.title()} Editor.\n"
                "Do you want to save them before proceeding?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                self._restore_selection()
                return False
            if reply == QMessageBox.StandardButton.Discard:
                editor.set_dirty(False)
                if editor_type != item_type:
                    editor._on_discard()
                continue
            if reply != QMessageBox.StandardButton.Save:
                self._restore_selection()
                return False
            if not self._save_signal_connected:
                self.main_window.editor_coordinator.editor_save_finished.connect(
                    self._on_navigation_save_finished
                )
                self._save_signal_connected = True
            editor._on_save()
            revision = getattr(editor, "_pending_save_revision", None)
            current_id = (
                editor.current_event_id if editor_type == "event"
                else editor.current_entity_id
            )
            if revision is None or current_id is None:
                self._restore_selection()
                return False
            self._pending_navigation = (
                item_type, item_id, editor_type, current_id, revision
            )
            self._restore_selection()
            return False
        return True

    def _editor_for(self, item_type: str) -> Any:
        """Return the editor that owns one authoring context."""
        return (
            self.main_window.event_editor
            if item_type == "event"
            else self.main_window.entity_editor
        )

    def _restore_selection(self) -> None:
        """Undo a visual selection made before navigation was approved."""
        if self._last_selected_type and self._last_selected_id:
            self.main_window.unified_list.select_item(
                self._last_selected_type, self._last_selected_id
            )
            if self._last_selected_type == "event":
                self.main_window.timeline.focus_event(self._last_selected_id)
            else:
                self.main_window.timeline.clear_event_selection()

    @Slot(str)
    def on_timeline_event_selected(self, event_id: str) -> None:
        """Route timeline clicks through guarded global selection."""
        self.set_global_selection("event", event_id)

    @Slot(str, str, int, bool)
    def _on_navigation_save_finished(
        self, item_type: str, item_id: str, revision: int, complete: bool
    ) -> None:
        """Continue only after the exact source draft was persisted."""
        pending = self._pending_navigation
        if pending is None or pending[2:] != (item_type, item_id, revision):
            return
        self._pending_navigation = None
        if complete:
            self.set_global_selection(pending[0], pending[1])
        else:
            self._restore_selection()

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
                "lore_date": float(
                    self.main_window.timeline.get_playhead_time()
                ),
            }
            event_command = (
                context.create_event_command(event_data)
                if context
                else CreateEventCommand(event_data)
            )
            self.main_window.command_requested.emit(event_command)
