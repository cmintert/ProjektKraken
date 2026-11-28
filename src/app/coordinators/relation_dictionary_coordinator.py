"""Coordinate one world dictionary draft and its worker-reviewed save."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QObject, QSignalBlocker, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from src.commands.relation_dictionary_command import EditRelationDefinitionCommand
from src.commands.relation_preset_command import ImportRelationPresetCommand
from src.commands.remove_relation_definition_command import (
    RemoveRelationDefinitionCommand,
)
from src.core.command import CommandResult
from src.core.relation_dictionary import (
    CATALOG_VERSION,
    edit_document,
    kraken_defaults,
    may_define,
    remove_definition,
    wording_examples,
)
from src.core.relation_presets import candidate, read_preset, write_preset
from src.core.relation_vocabulary import ENDPOINTS, load_document
from src.gui.widgets.relation_dictionary import RelationDictionaryDialog
from src.services.relation_identifier_migration import is_custom_key
from src.services.transfer_files import staged_output

DictionaryCommand = (
    EditRelationDefinitionCommand
    | ImportRelationPresetCommand
    | RemoveRelationDefinitionCommand
)
_PRESET_FILTER = "Relation presets (*.json)"


def _preview_text(
    raw: str | None, key: str, definition: dict[str, Any], sample: dict[str, str] | None
) -> str:
    forward, reverse, guidance = wording_examples(raw, key, sample)
    state = (
        ("Enabled" if definition.get("enabled", True) else "Disabled")
        if definition
        else "No definition"
    )
    source, target = (
        {"entity": "Entity", "event": "Event"}.get(
            str(definition.get(field)), "Any kind"
        )
        for field in ENDPOINTS
    )
    symmetry = (
        "symmetric" if definition.get("symmetric") is True else "not declared symmetric"
    )
    text = (
        f"From source: {forward}\nFrom target: {reverse}\n"
        f"{state} · Prefers {source} → {target} · {symmetry}"
    )
    return f"{text}\n{guidance}" if guidance else text


def _preset_definition_text(
    key: str, definition: dict[str, Any] | None, sample: dict[str, str] | None
) -> str:
    raw = (
        json.dumps({"version": 1, "definitions": [definition]}) if definition else None
    )
    result = _preview_text(raw, key, definition or {}, sample)
    if not definition:
        return result
    for field, label in (
        ("description", "Description"),
        ("category", "Category"),
        ("forward_template", "Forward template"),
        ("reverse_template", "Reverse template"),
    ):
        result += f"\n{label}: {definition.get(field) or 'None'}"
    return result


class RelationDictionaryCoordinator(QObject):
    """Keep drafts and requests pinned to the world that opened the editor."""

    requested = Signal(dict)

    def __init__(
        self,
        context: Callable[[], dict[str, Any]],
        execute: Callable[[DictionaryCommand], bool],
        reader: QObject,
        parent: QObject,
        migrate: Callable[[dict[str, Any]], bool] = lambda _request: False,
    ) -> None:
        """Bind narrow context and command dependencies."""
        super().__init__(parent)
        self._context = context
        self._execute = execute
        self._reader = reader
        self._migrate = migrate
        self.view: RelationDictionaryDialog | None = None
        self._database = ""
        self._request = ""
        self._pending = ""
        self._raw: str | None = None
        self._writable = False
        self._definitions: dict[str, dict[str, Any]] = {}
        self._counts: dict[str, int] = {}
        self._defaults = kraken_defaults()
        self._original: str | None = None
        self._selected = ""
        self._baseline: dict[str, Any] | None = None
        self._reviewed: dict[str, Any] | None = None
        self._list_message = ""
        self._preset: list[dict[str, Any]] = []
        self._preset_snapshot: dict[str, Any] = {}
        self._exporting = False
        self._removing = False
        self._migration: dict[str, Any] = {}

    def open(self, parent: QWidget) -> None:
        """Open one editor and request current world data."""
        if self.view is not None:
            self.view.raise_()
            self.view.activateWindow()
            return
        context = self._context()
        if not context.get("database"):
            return
        self._database = context["database"]
        self._selected = ""
        self._list_message = ""
        view = self.view = RelationDictionaryDialog(context["name"], parent)
        view.selected.connect(self._select)
        view.draft_changed.connect(self._draft_changed)
        view.review_requested.connect(self._review)
        view.edit_requested.connect(self._edit)
        view.save_requested.connect(self._save)
        view.back_requested.connect(self._back)
        view.close_requested.connect(self.allow_transition)
        view.export_requested.connect(self._select_export)
        view.import_requested.connect(self._open_preset)
        view.removal_requested.connect(self._review_removal)
        view.migration_requested.connect(self._open_migration)
        view.migration_review.back.clicked.connect(self._return_to_definition)
        view.migration_review.destination.textChanged.connect(
            self._clear_migration_review
        )
        view.migration_review.review.clicked.connect(self._request_migration_review)
        view.migration_review.apply.clicked.connect(self._confirm_migration)
        view.preset_review.cancel.clicked.connect(lambda: self._load_list())
        view.preset_review.confirm.clicked.connect(self._confirm_preset)
        view.show()
        self._load_list()

    def allow_transition(self) -> bool:
        """Guard close and world changes with a discard or keep-editing decision."""
        view = self.view
        if view is None:
            return True
        if self._pending:
            view.show_message("Wait for the dictionary change to finish saving.")
            return False
        if not self._may_discard(view):
            return False
        self._request = ""
        self.view = None
        view.hide()
        view.deleteLater()
        return True

    def has_pending_changes(self) -> bool:
        """Report unsaved work to the existing application close guard."""
        return bool(
            self._pending
            or (
                self.view is not None
                and self._baseline is not None
                and self.view.definition() != self._baseline
            )
        )

    def _may_discard(self, view: RelationDictionaryDialog) -> bool:
        if self._baseline is None or view.definition() == self._baseline:
            return True
        result = QMessageBox.question(
            view,
            "Discard definition draft?",
            "Discard the changes to this relation definition?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return result == QMessageBox.StandardButton.Discard

    def _back(self) -> None:
        view = self.view
        if view is not None and not self._pending and self._may_discard(view):
            self._load_list()

    def _load_list(self, message: str = "") -> None:
        view = self.view
        if view is not None:
            self._baseline = None
            self._reviewed = None
            self._preset = []
            self._preset_snapshot = {}
            self._exporting = False
            self._removing = False
            self._migration = {}
            self._list_message = message
            view.show_entries([], False, "")
            view.show_message(message or "Loading relation definitions…")
            self._load()

    def _load(self, key: str | None = None) -> None:
        self._request = uuid4().hex
        request = {"database": self._database, "token": self._request}
        if key is not None:
            request["key"] = key
        self.requested.emit(request)

    @Slot(dict)
    def on_snapshot(self, payload: dict[str, Any]) -> None:
        """Ignore stale replies and render the latest scope or review."""
        view = self.view
        if view is None or payload["token"] != self._request:
            return
        if self._context().get("database") != self._database:
            self.allow_transition()
            return
        if error := payload.get("error"):
            view.show_message(error, error=True)
            return
        if "preset_usage" in payload:
            self._show_preset(view, payload)
            return
        if "migration_review" in payload:
            self._show_migration_review(view, payload)
            return
        if "usage" in payload:
            self._show_review(view, payload)
            return
        self._raw = payload["raw"]
        self._writable = payload["writable"]
        self._counts = payload["counts"]
        self._definitions = {entry["key"]: entry for entry in payload["definitions"]}
        self._show_list()

    def _show_list(self) -> None:
        view = self.view
        if view is None:
            return
        self._baseline = None
        self._reviewed = None
        keys = sorted(
            self._definitions.keys() | self._counts.keys(),
            key=lambda k: (k.casefold(), k),
        )
        rows = []
        for key in keys:
            if not may_define(key, existing_key=True):
                continue
            definition = self._definitions.get(key)
            count = self._counts.get(key, 0)
            if definition is None:
                caption = f"{key} · {count} uses · No definition"
            else:
                state = " · Disabled" if not definition.get("enabled", True) else ""
                caption = f"{definition['forward_label']} ({key}) · {count} uses{state}"
            rows.append(("world", key, caption))
        rows.extend(
            (
                "default",
                key,
                f"{definition['forward_label']} ({key}) · Kraken defaults v{CATALOG_VERSION}",
            )
            for key, definition in self._defaults.items()
            if key not in self._definitions
        )
        view.show_entries(
            rows, self._writable, self._selected, exportable=bool(self._definitions)
        )
        view.show_message(
            self._list_message or ("" if self._writable else "This world is read-only.")
        )

    @Slot(str, str)
    def _select(self, source: str, key: str) -> None:
        view = self.view
        if view is None:
            return
        self._request = ""
        self._removing = False
        self._migration = {}
        self._selected = key
        self._original = key if source == "world" else None
        entry = (
            self._defaults.get(key)
            if source == "default"
            else self._definitions.get(key)
        )
        with QSignalBlocker(view):
            view.show_definition(entry or {"key": key}, bool(key), self._writable)
            view.set_definition_actions(
                removable=self._writable and source == "world" and entry is not None,
                migratable=self._writable and source == "world" and is_custom_key(key),
            )
        self._baseline = view.definition()
        self._draft_changed()

    @Slot()
    def _draft_changed(self) -> None:
        view = self.view
        if view is None:
            return
        self._request = ""
        self._reviewed = None
        view.save.setEnabled(False)
        definition = view.definition()
        key = definition["key"]
        current = self._definitions.get(key)
        try:
            updated = edit_document(self._raw, definition, self._original)
        except ValueError as exc:
            view.review.setEnabled(False)
            view.preview.setText(
                "Current wording\n" + _preview_text(self._raw, key, current, None)
                if current is not None
                else ""
            )
            if self._writable and (definition != self._baseline or current is not None):
                view.show_message(str(exc), error=True)
            else:
                view.show_message("" if self._writable else "This world is read-only.")
            return
        view.review.setEnabled(
            self._writable and (current is None or definition != self._baseline)
        )
        view.show_message("" if self._writable else "This world is read-only.")
        view.preview.setText(_preview_text(updated, key, definition, None))

    def _edit(self) -> None:
        if self.view is not None and not self._pending:
            self._removing = False
            self.view.save.setText("Save definition")
            self.view.return_to_edit()
            self._draft_changed()

    def _review_removal(self) -> None:
        view = self.view
        key = self._original
        if (
            view is not None
            and key is not None
            and key in self._definitions
            and self._may_discard(view)
        ):
            self._select("world", key)
            self._removing = True
            self._reviewed = None
            view.save.setEnabled(False)
            view.show_message("Checking current relation usage…")
            self._load(key)

    def _review(self) -> None:
        view = self.view
        if view is not None and view.review.isEnabled():
            self._removing = False
            self._reviewed = None
            view.save.setEnabled(False)
            view.show_message("Checking current relation usage…")
            self._load(view.definition()["key"])

    def _show_review(
        self, view: RelationDictionaryDialog, payload: dict[str, Any]
    ) -> None:
        if payload["raw"] != self._raw or not payload["writable"]:
            view.show_message(
                "The dictionary or its availability changed. Go back to reload it.",
                error=True,
            )
            return
        if self._removing and self._original is not None:
            self._show_removal_review(view, payload, self._original)
            return
        definition = view.definition()
        key = definition["key"]
        updated = edit_document(self._raw, definition, self._original)
        evidence = payload["usage"]
        sample = evidence["sample"]
        before = _preview_text(self._raw, key, self._definitions.get(key, {}), sample)
        after = _preview_text(updated, key, definition, sample)
        sample_note = (
            "Example from a saved connection" if sample else "Illustrative endpoints"
        )
        self._reviewed = evidence
        view.show_message()
        view.save.setText("Save definition")
        view.save.setEnabled(True)
        count = evidence["count"]
        noun = "connection" if count == 1 else "connections"
        view.show_review(
            f"{key} · {count} stored {noun} · {sample_note}\n\n"
            f"Before\n{before}\n\nAfter\n{after}"
        )

    def _show_removal_review(
        self, view: RelationDictionaryDialog, payload: dict[str, Any], key: str
    ) -> None:
        evidence = payload["usage"]
        updated = remove_definition(self._raw, key)
        before = _preview_text(
            self._raw, key, self._definitions[key], evidence["sample"]
        )
        after = _preview_text(updated, key, {}, evidence["sample"])
        self._reviewed = evidence
        view.show_message()
        view.save.setText("Remove definition")
        view.save.setEnabled(True)
        view.show_review(
            f"{key}\nStored connections: {evidence['count']}\n\n"
            f"Current\n{before}\n\nAfter removal\n{after}\n\n"
            "The existing connections keep their saved key. Undo restores this definition."
        )

    def _return_to_definition(self) -> None:
        if self._original is not None and not self._pending:
            self._select("world", self._original)

    def _open_migration(self) -> None:
        view = self.view
        if view is None or self._original is None or not self._may_discard(view):
            return
        self._select("world", self._original)
        view.pages.setCurrentWidget(view.migration_review)
        view.migration_review.reset(self._original)
        self._clear_migration_review()

    def _clear_migration_review(self) -> None:
        if self.view is not None and not self._pending:
            self._migration = {}
            self._request = ""
            self.view.migration_review.show_preview("")
            self.view.show_message()

    def _request_migration_review(self) -> None:
        if self.view is None or self._original is None:
            return
        self._request = uuid4().hex
        self.view.show_message("Checking migration impact…")
        self.requested.emit(
            {
                "database": self._database,
                "token": self._request,
                "migration": [
                    self._original,
                    self.view.migration_review.destination.text(),
                ],
            }
        )

    def _show_migration_review(
        self, view: RelationDictionaryDialog, payload: dict[str, Any]
    ) -> None:
        if not payload["writable"]:
            view.show_message("This world is read-only.", error=True)
            return
        self._migration = payload
        old, new = payload["migration"]
        review = payload["migration_review"]
        definition = (
            "Move the saved definition."
            if review["definition"]
            else "Connections use fallback wording."
        )
        style = (
            "Move the saved GraphView style."
            if review["graph_style"]
            else "GraphView uses its default style."
        )
        history = review["history"]
        view.show_message()
        view.migration_review.show_preview(
            f"{old} → {new}\nStored connections: {review['count']}\n\n"
            f"{definition}\n{style}\nGraphView and World Context refresh after migration.\n\n"
            f"Start fresh Undo and Redo stacks ({len(history['undo'])} undo, "
            f"{len(history['redo'])} redo entries in the saved history).\n"
            "Kraken will verify a backup before changing the key. To reverse the migration, "
            "restore that backup. Restoring also rolls back later edits."
        )
        view.migration_review.apply.setFocus()

    def _confirm_migration(self) -> None:
        view = self.view
        if view is None or not self._migration or self._pending:
            return
        self._pending = self._migration["token"]
        view.migration_review.setEnabled(False)
        view.show_message("Creating and verifying the migration checkpoint…")
        if not self._migrate(self._migration):
            self.on_migration_finished(
                {
                    "token": self._pending,
                    "error": "Wait for pending commands to finish, then review again.",
                }
            )

    @Slot(dict)
    def on_migration_finished(self, result: dict[str, Any]) -> None:
        """Publish the checkpoint location only after a committed migration."""
        view = self.view
        if view is None or not self._pending or self._pending != result["token"]:
            return
        self._pending = ""
        view.migration_review.setEnabled(True)
        if error := result.get("error"):
            self._clear_migration_review()
            view.show_message(error, error=True)
        else:
            self._selected = result["new"]
            self._load_list(
                f"Migrated {result['old']} → {result['new']}. Checkpoint: {result['checkpoint']}"
            )

    def _save(self) -> None:
        view = self.view
        if view is None or self._reviewed is None or self._pending:
            return
        command: DictionaryCommand
        if self._removing and self._original is not None and self._raw is not None:
            command = RemoveRelationDefinitionCommand(
                self._database, self._raw, self._original, self._reviewed
            )
        else:
            command = EditRelationDefinitionCommand(
                self._database,
                self._raw,
                view.definition(),
                self._original,
                self._reviewed,
            )
        self._pending = command.command_id
        view.edit.setEnabled(False)
        view.save.setEnabled(False)
        view.show_message("Saving relation definition…")
        if not self._execute(command):
            self.on_command_finished(
                CommandResult(
                    False,
                    "The world is unavailable for editing.",
                    data={"command_id": command.command_id},
                )
            )

    def _select_export(self) -> None:
        view = self.view
        if view is None:
            return
        self._exporting = True
        rows = {
            key: (
                "export",
                f"{key}\n\n{_preset_definition_text(key, definition, None)}",
            )
            for key, definition in self._definitions.items()
        }
        view.pages.setCurrentWidget(view.preset_review)
        view.preset_review.show_rows(rows, exporting=True)
        view.show_message()

    def _open_preset(self) -> None:
        view = self.view
        if view is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            view, "Open relation preset", "", _PRESET_FILTER
        )
        if not path or view is not self.view:
            return
        try:
            self._preset = read_preset(Path(path).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            view.show_message(str(exc), error=True)
            return
        self._request_preset()

    def _request_preset(self, feedback: str = "") -> None:
        view = self.view
        if view is None:
            return
        self._request = uuid4().hex
        self._preset_snapshot = {}
        view.pages.setCurrentWidget(view.preset_review)
        view.preset_review.show_rows({}, exporting=False)
        view.show_message(
            feedback or "Checking destination usage…", error=bool(feedback)
        )
        self.requested.emit(
            {
                "database": self._database,
                "token": self._request,
                "preset_keys": [entry["key"] for entry in self._preset],
            }
        )

    def _show_preset(
        self, view: RelationDictionaryDialog, payload: dict[str, Any]
    ) -> None:
        if not payload["writable"]:
            view.show_message("This world is read-only.", error=True)
            return
        self._preset_snapshot = payload
        existing = {
            entry["key"]: entry
            for entry in load_document(payload["raw"])["definitions"]
        }
        rows = {}
        for incoming in self._preset:
            key = incoming["key"]
            evidence = payload["preset_usage"][key]
            current = existing.get(key)
            status, proposed = candidate(key, current, incoming, evidence["count"])
            sample = evidence["sample"]
            before = _preset_definition_text(key, current, sample)
            after = (
                _preset_definition_text(key, proposed, sample)
                if proposed is not None
                else "This key is protected or requires an exact existing key in this world."
            )
            rows[key] = (
                status,
                f"{key}\nStored connections: {evidence['count']}\n\n"
                f"Current\n{before}\n\nPreset\n{after}",
            )
        view.preset_review.show_rows(rows, exporting=False)
        if not view.message.property("dictionary_error"):
            view.show_message()

    def _confirm_preset(self) -> None:
        view = self.view
        if view is None or self._pending or not view.preset_review.confirm.isEnabled():
            return
        choices = view.preset_review.choices
        if self._exporting:
            self._write_preset(view, choices)
        elif self._preset_snapshot:
            self._import_preset(view, choices)

    def _write_preset(
        self, view: RelationDictionaryDialog, choices: dict[str, str]
    ) -> None:
        try:
            contents = write_preset(
                [
                    self._definitions[key]
                    for key, choice in choices.items()
                    if choice == "export"
                ]
            )
            path, _ = QFileDialog.getSaveFileName(
                view, "Save relation preset", "relation-preset.json", _PRESET_FILTER
            )
            if not path or view is not self.view:
                return
            destination = Path(path)
            if destination.suffix.casefold() != ".json":
                raise ValueError("Use a .json filename for the relation preset.")
            with staged_output(destination) as output:
                output.write_text(contents, encoding="utf-8")
        except (OSError, ValueError) as exc:
            view.show_message(str(exc), error=True)
            return
        self._load_list("Relation preset exported.")

    def _import_preset(
        self, view: RelationDictionaryDialog, choices: dict[str, str]
    ) -> None:
        command = ImportRelationPresetCommand(
            self._database,
            self._preset_snapshot["raw"],
            self._preset,
            choices,
            self._preset_snapshot["preset_usage"],
        )
        self._pending = command.command_id
        view.preset_review.setEnabled(False)
        view.show_message("Importing relation definitions…")
        if not self._execute(command):
            self.on_command_finished(
                CommandResult(
                    False,
                    "The destination world is unavailable for editing.",
                    data={"command_id": command.command_id},
                )
            )

    @Slot(object)
    def on_command_finished(self, result: CommandResult) -> None:
        """Acknowledge only the editor's outstanding save."""
        view = self.view
        if (
            view is None
            or not self._pending
            or result.data.get("command_id") != self._pending
        ):
            return
        self._pending = ""
        if self._preset:
            view.preset_review.setEnabled(True)
            if result.success:
                self._load_list(result.message)
            else:
                self._request_preset(result.message)
            return
        self._reviewed = None
        view.edit.setEnabled(True)
        if result.success:
            self._selected = view.definition()["key"]
            self._load_list(result.message)
        else:
            self._removing = False
            view.save.setText("Save definition")
            view.return_to_edit()
            view.show_message(result.message, error=True)
