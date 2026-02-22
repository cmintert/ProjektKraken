import logging
from typing import Any

from PySide6.QtCore import Signal, Slot

from src.app.coordinators.base_coordinator import BaseCoordinator
from src.commands.inject_commands import InjectTemplateCommand
from src.core.fast_inject import FastInjectTemplate
from src.gui.dialogs.fast_inject_dialog import FastInjectDialog

logger = logging.getLogger(__name__)


class FastInjectCoordinator(BaseCoordinator):
    """Coordinator for Fast Inject and Template Creation workflows.

    Handles:
    - Displaying the Fast Inject Dialog
    - Template selection and injection logic
    - Template creation interactions
    """

    # Signals
    command_requested = Signal(object)  # Emits BaseCommand
    # We might need signals for status updates if MainWindow needs to show them
    status_message_requested = Signal(str, int)

    def __init__(self, main_window: Any) -> None:
        super().__init__(main_window)
        self._fast_inject_manager: Any = None

    @property
    def fast_inject_manager(self) -> Any:
        """Lazy accessor for FastInjectManager.

        The manager is created on MainWindow during Phase 2
        (_init_widgets_skeleton), but this coordinator is instantiated
        in Phase 1 (_init_core_services).  Deferring access avoids an
        AttributeError at startup.
        """
        if self._fast_inject_manager is None:
            self._fast_inject_manager = self.main_window.fast_inject_manager
        return self._fast_inject_manager

    @Slot(str)
    def request_fast_inject_for_entity(self, entity_id: str) -> None:
        """Initiates the Fast Inject flow for an entity."""
        # 1. Check unsaved changes
        if not self.main_window.check_unsaved_changes(self.main_window.entity_editor):
            return

        # 2. Fetch Target
        # Accessing _cached_entities from MainWindow.
        # Note: In future, this should be via a DataService/Store.
        target_entity = next(
            (e for e in self.main_window.data_coordinator.cached_entities if e.id == entity_id), None
        )

        if not target_entity:
            self.main_window.show_error_message(
                f"Entity {entity_id} not found in cache."
            )
            return

        self._show_fast_inject_dialog(target_entity)

    @Slot(str)
    def request_fast_inject_for_event(self, event_id: str) -> None:
        """Initiates the Fast Inject flow for an event."""
        # 1. Check unsaved changes
        if not self.main_window.check_unsaved_changes(self.main_window.event_editor):
            return

        # 2. Fetch Target
        target_event = next(
            (e for e in self.main_window.data_coordinator.cached_events if e.id == event_id), None
        )

        if not target_event:
            self.main_window.show_error_message(f"Event {event_id} not found in cache.")
            return

        self._show_fast_inject_dialog(target_event)

    def _show_fast_inject_dialog(self, target: Any) -> None:
        """Shows the dialog for a generic target (Entity or Event)."""
        # Load templates
        templates = self.fast_inject_manager.load_templates()

        dlg = FastInjectDialog(
            templates,
            target_name=target.name,
            parent=self.main_window,
            manager=self.fast_inject_manager,
        )
        result = dlg.exec()

        # Handle Import
        if result == 2:
            self._handle_import_result(dlg, target)
            return

        if not result or not dlg.selected_template:
            return

        # Prepare Command
        import copy

        target_clone = copy.deepcopy(target)

        cmd = InjectTemplateCommand(
            target=target_clone,
            template=dlg.selected_template,
            manager=self.fast_inject_manager,
            overwrite=dlg.should_overwrite,
            variables=dlg.variable_values,
        )

        self.command_requested.emit(cmd)

    def _handle_import_result(self, dlg: FastInjectDialog, target: Any) -> None:
        """Handles the import result from the dialog."""
        import_paths = getattr(dlg, "_import_paths", [])
        if import_paths:
            imported_count = 0
            for path in import_paths:
                try:
                    self.fast_inject_manager.import_template(path)
                    imported_count += 1
                except Exception as e:
                    logger.error(f"Failed to import template {path}: {e}")

            if imported_count > 0:
                self.status_message_requested.emit(
                    f"Imported {imported_count} template(s). Reopening dialog...", 0
                )
                # Reopen recursively
                self._show_fast_inject_dialog(target)

    @Slot(dict)
    def request_create_template(self, data: dict) -> None:
        """Creates a new template from provided data."""
        try:
            # logic extracted from MainWindow._on_create_template_requested
            tags = data.get("selected_tags", [])
            attributes = data.get("selected_attributes", {})
            type_val = data.get("type_value")

            template = FastInjectTemplate(
                name=data["name"],
                description=data.get("description", ""),
                tags=tags,
                attributes=attributes,
                type_value=type_val,
                target_type="any",
            )

            self.fast_inject_manager.save_template(template)
            self.status_message_requested.emit(
                f"Template '{template.name}' saved.", 2000
            )

        except Exception as e:
            self.main_window.show_error_message(f"Failed to create template: {e}")
            logger.error(f"Template creation failed: {e}")
