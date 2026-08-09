"""Session-scoped context tags for interactive item creation."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Literal

from PySide6.QtCore import QSettings, Signal, Slot
from PySide6.QtWidgets import QDialog, QMessageBox

from src.app.constants import (
    SETTINGS_CONTEXT_TAGS_PREFIX,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.app.coordinators.base_coordinator import BaseCoordinator
from src.commands.base_command import BaseCommand, CommandResult
from src.commands.composite_command import CompositeCommand
from src.commands.entity_commands import CreateEntityCommand, UpdateEntityCommand
from src.commands.event_commands import CreateEventCommand, UpdateEventCommand

if TYPE_CHECKING:
    from src.app.main_window import MainWindow
    from src.core.entities import Entity
    from src.core.events import Event

logger = logging.getLogger(__name__)

ItemType = Literal["entity", "event"]


@dataclass
class ContextTagApplication:
    """Recoverable record of tags injected into one created item."""

    item_type: ItemType
    item_id: str
    command_id: str
    added_tags: list[str]
    created_at: float
    status: str = "present"

    @classmethod
    def from_dict(cls, data: object) -> ContextTagApplication | None:
        """Validate and restore a persisted application record."""
        if not isinstance(data, dict):
            return None
        item_type = data.get("item_type")
        item_id = data.get("item_id")
        command_id = data.get("command_id")
        added_tags = data.get("added_tags")
        if (
            item_type not in {"entity", "event"}
            or not isinstance(item_id, str)
            or not item_id
            or not isinstance(command_id, str)
            or not isinstance(added_tags, list)
        ):
            return None
        clean_tags = [tag for tag in added_tags if isinstance(tag, str) and tag]
        if not clean_tags:
            return None
        return cls(
            item_type=item_type,
            item_id=item_id,
            command_id=command_id,
            added_tags=clean_tags,
            created_at=float(data.get("created_at", 0.0)),
            status=str(data.get("status", "present")),
        )


class ContextTagCoordinator(BaseCoordinator):
    """Own active context-tag state, creation decoration, and recovery."""

    state_changed = Signal(dict)
    command_requested = Signal(object)
    navigation_requested = Signal(str, str)

    def __init__(
        self,
        main_window: MainWindow,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__(main_window)
        self._settings = settings or QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        world = getattr(main_window, "current_world", None)
        world_id = str(getattr(world, "id", "default") or "default")
        self._settings_prefix = SETTINGS_CONTEXT_TAGS_PREFIX.format(world_id=world_id)
        self._remembered_tags: list[str] = []
        self._active = False
        self._pending: dict[str, ContextTagApplication] = {}
        self._applications: dict[str, ContextTagApplication] = {}
        self._available_tags: list[str] = []
        self._items: dict[tuple[ItemType, str], Entity | Event] = {}
        self._load_settings()

    @property
    def remembered_tags(self) -> list[str]:
        """Return an isolated copy of the remembered set."""
        return list(self._remembered_tags)

    @property
    def is_active(self) -> bool:
        """Return whether new interactive items receive context tags."""
        return self._active

    def set_available_tags(self, tags: list[str]) -> None:
        """Update autocomplete values used by the editor dialog."""
        self._available_tags = list(dict.fromkeys(tags))

    def save_tags(self, tags: list[str], *, activate: bool | None = None) -> None:
        """Remember a normalized set and optionally change activation."""
        clean = list(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))
        self._remembered_tags = clean
        if activate is not None:
            self._active = bool(activate and clean)
        elif not clean:
            self._active = False
        self._persist()
        self._emit_state()

    @Slot()
    def enable(self) -> None:
        """Enable the remembered set when it is non-empty."""
        self._active = bool(self._remembered_tags)
        self._emit_state()

    @Slot()
    def disable(self) -> None:
        """Stop applying tags without changing content or remembered tags."""
        self._active = False
        self._emit_state()

    def create_entity_command(self, data: dict[str, Any]) -> CreateEntityCommand:
        """Build and track a context-aware interactive entity creation."""
        decorated, added_tags = self._decorate_data(data)
        command = CreateEntityCommand(decorated)
        if added_tags:
            self._track_pending(
                "entity", command._entity.id, command, added_tags  # noqa: SLF001
            )
        return command

    def create_event_command(self, data: dict[str, Any]) -> CreateEventCommand:
        """Build and track a context-aware interactive event creation."""
        decorated, added_tags = self._decorate_data(data)
        command = CreateEventCommand(decorated)
        if added_tags:
            self._track_pending("event", command.event.id, command, added_tags)
        return command

    def _decorate_data(self, data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        decorated = dict(data)
        attributes = dict(decorated.get("attributes") or {})
        existing = list(attributes.get("_tags") or [])
        added = [
            tag
            for tag in self._remembered_tags
            if self._active and tag not in existing
        ]
        if added:
            attributes["_tags"] = [*existing, *added]
            decorated["attributes"] = attributes
        return decorated, added

    def _track_pending(
        self,
        item_type: ItemType,
        item_id: str,
        command: BaseCommand,
        added_tags: list[str],
    ) -> None:
        self._pending[command.command_id] = ContextTagApplication(
            item_type=item_type,
            item_id=item_id,
            command_id=command.command_id,
            added_tags=list(added_tags),
            created_at=time.time(),
            status="pending",
        )

    @Slot(object)
    def on_command_finished(self, result: CommandResult) -> None:
        """Promote only successful context-tagged create commands."""
        command_id = str(result.data.get("command_id", ""))
        pending = self._pending.pop(command_id, None)
        if pending is not None:
            if result.success:
                pending.status = "present"
                self._applications[pending.command_id] = pending
                self._persist()
            self._emit_state()
            return

        application = self._applications.get(command_id)
        if application is not None and result.success:
            if result.command_name.startswith("Undo_Create"):
                application.status = "unavailable"
            elif result.command_name.startswith("Redo_Create"):
                application.status = "present"
            self._persist()
            self._emit_state()

    def reconcile(self, events: list[Event], entities: list[Entity]) -> None:
        """Reconcile recovery records with the latest immutable UI snapshots."""
        self._items = {
            **{("event", item.id): item for item in events},
            **{("entity", item.id): item for item in entities},
        }
        changed = False
        for application in self._applications.values():
            item = self._items.get((application.item_type, application.item_id))
            if item is None:
                status = "unavailable"
            elif any(tag in item.tags for tag in application.added_tags):
                status = "present"
            else:
                status = "resolved"
            if application.status != status:
                application.status = status
                changed = True
        if changed:
            self._persist()
        self._emit_state()

    def review_records(self) -> list[dict[str, object]]:
        """Return current affected records for the review dialog."""
        records: list[dict[str, object]] = []
        for application in self._applications.values():
            item = self._items.get((application.item_type, application.item_id))
            if item is None:
                continue
            remaining = [tag for tag in application.added_tags if tag in item.tags]
            if not remaining:
                continue
            records.append(
                {
                    "item_type": application.item_type,
                    "item_id": application.item_id,
                    "name": item.name,
                    "tags": remaining,
                    "created_at": application.created_at,
                }
            )
        return sorted(
            records,
            key=lambda record: (
                float(value)
                if isinstance((value := record["created_at"]), (int, float, str))
                else 0.0
            ),
        )

    def build_cleanup_command(
        self, selected: list[tuple[str, str]]
    ) -> CompositeCommand | None:
        """Build one atomic command removing context-added tags from selections."""
        selected_keys = {(item_type, item_id) for item_type, item_id in selected}
        commands: list[BaseCommand] = []
        for application in self._applications.values():
            key = (application.item_type, application.item_id)
            if key not in selected_keys:
                continue
            item = self._items.get(key)
            if item is None:
                continue
            new_tags = [tag for tag in item.tags if tag not in application.added_tags]
            if new_tags == item.tags:
                continue
            attributes = dict(item.attributes)
            attributes["_tags"] = new_tags
            if application.item_type == "entity":
                commands.append(UpdateEntityCommand(item.id, {"attributes": attributes}))
            else:
                commands.append(UpdateEventCommand(item.id, {"attributes": attributes}))
        if not commands:
            return None
        return CompositeCommand(commands, "Remove Context Tags")

    def has_dirty_selection(self, selected: list[tuple[str, str]]) -> bool:
        """Return whether cleanup would overlap an unsaved open inspector."""
        selected_keys = set(selected)
        event_editor = self.main_window.event_editor
        entity_editor = self.main_window.entity_editor
        return bool(
            (
                ("event", event_editor._current_event_id) in selected_keys
                and event_editor.has_unsaved_changes()
            )
            or (
                ("entity", entity_editor._current_entity_id) in selected_keys
                and entity_editor.has_unsaved_changes()
            )
        )

    def request_cleanup(self, selected: list[tuple[str, str]]) -> bool:
        """Validate and submit explicit cleanup without touching autosave."""
        if self.has_dirty_selection(selected):
            QMessageBox.information(
                self.main_window,
                "Unsaved changes",
                "Save or discard changes in the selected open inspector before "
                "removing context tags.",
            )
            return False
        command = self.build_cleanup_command(selected)
        if command is None:
            return False
        self.command_requested.emit(command)
        return True

    @Slot()
    def show_editor(self) -> None:
        """Open the tag-set editor and apply its explicit action."""
        from src.gui.dialogs.context_tag_dialogs import ContextTagEditorDialog

        dialog = ContextTagEditorDialog(
            self._remembered_tags,
            self._available_tags,
            active=self._active,
            parent=self.main_window,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.save_tags(dialog.tags(), activate=dialog.action == "apply")

    @Slot()
    def show_review(self) -> None:
        """Open recovery review and route its selected action."""
        from src.gui.dialogs.context_tag_dialogs import ContextTagReviewDialog

        records = self.review_records()
        if not records:
            if not self._applications:
                QMessageBox.information(
                    self.main_window,
                    "Review Context Tags",
                    "No context-tag recovery history is available.",
                )
                return
            response = QMessageBox.question(
                self.main_window,
                "Clear Review History",
                "No existing records currently contain recoverable context tags. "
                "Clear the local review history? World content will not be changed.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if response == QMessageBox.StandardButton.Yes:
                self.clear_review_history()
            return
        dialog = ContextTagReviewDialog(records, self.main_window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.action == "cleanup":
            self.request_cleanup(dialog.selected_keys())
        elif dialog.action == "navigate" and dialog.navigation_target is not None:
            item_type, item_id = dialog.navigation_target
            self.main_window.navigation_coordinator.set_global_selection(
                item_type, item_id
            )
        elif dialog.action == "clear":
            response = QMessageBox.question(
                self.main_window,
                "Clear Review History",
                "Forget the local recovery list? World content will not be changed.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if response == QMessageBox.StandardButton.Yes:
                self.clear_review_history()

    @Slot()
    def clear_review_history(self) -> None:
        """Forget recovery metadata without changing world content."""
        self._applications.clear()
        self._persist()
        self._emit_state()

    def snapshot(self) -> dict[str, object]:
        """Return serializable state for all context-tag UI consumers."""
        return {
            "tags": list(self._remembered_tags),
            "active": self._active,
            "affected_count": len(self.review_records()),
            "history_count": len(self._applications),
        }

    def _emit_state(self) -> None:
        self.state_changed.emit(self.snapshot())

    def _load_settings(self) -> None:
        raw_tags = self._settings.value(f"{self._settings_prefix}/last_tags", "[]")
        raw_ledger = self._settings.value(
            f"{self._settings_prefix}/recovery_ledger", "[]"
        )
        try:
            tags = json.loads(str(raw_tags))
            if isinstance(tags, list):
                self._remembered_tags = list(
                    dict.fromkeys(tag for tag in tags if isinstance(tag, str) and tag)
                )
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.warning("Ignoring malformed remembered context tags")
        try:
            ledger = json.loads(str(raw_ledger))
            if isinstance(ledger, list):
                for raw_entry in ledger:
                    entry = ContextTagApplication.from_dict(raw_entry)
                    if entry is not None:
                        self._applications[entry.command_id] = entry
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.warning("Ignoring malformed context-tag recovery ledger")

    def _persist(self) -> None:
        self._settings.setValue(
            f"{self._settings_prefix}/last_tags",
            json.dumps(self._remembered_tags),
        )
        self._settings.setValue(
            f"{self._settings_prefix}/recovery_ledger",
            json.dumps([asdict(entry) for entry in self._applications.values()]),
        )
