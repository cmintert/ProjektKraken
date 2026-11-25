"""Coordinate one world dictionary draft and its worker-reviewed save."""

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QObject, QSignalBlocker, Signal, Slot
from PySide6.QtWidgets import QMessageBox, QWidget

from src.commands.relation_dictionary_command import EditRelationDefinitionCommand
from src.core.command import CommandResult
from src.core.relation_dictionary import (
    CATALOG_VERSION,
    edit_document,
    kraken_defaults,
    may_define,
    wording_examples,
)
from src.core.relation_vocabulary import ENDPOINTS
from src.gui.widgets.relation_dictionary import RelationDictionaryDialog


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


class RelationDictionaryCoordinator(QObject):
    """Keep drafts and requests pinned to the world that opened the editor."""

    requested = Signal(dict)

    def __init__(
        self,
        context: Callable[[], dict[str, Any]],
        execute: Callable[[EditRelationDefinitionCommand], bool],
        reader: QObject,
        parent: QObject,
    ) -> None:
        """Bind narrow context and command dependencies."""
        super().__init__(parent)
        self._context = context
        self._execute = execute
        self._reader = reader
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
        view.show()
        self._load_list()

    def allow_transition(self) -> bool:
        """Guard close and world changes with a discard or keep-editing decision."""
        view = self.view
        if view is None:
            return True
        if self._pending:
            view.show_message("Wait for the definition to finish saving.")
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
        view.show_entries(rows, self._writable, self._selected)
        view.show_message(
            self._list_message if self._writable else "This world is read-only."
        )

    @Slot(str, str)
    def _select(self, source: str, key: str) -> None:
        view = self.view
        if view is None:
            return
        self._request = ""
        self._selected = key
        self._original = key if source == "world" else None
        entry = (
            self._defaults.get(key)
            if source == "default"
            else self._definitions.get(key)
        )
        with QSignalBlocker(view):
            view.show_definition(entry or {"key": key}, bool(key), self._writable)
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
            self.view.return_to_edit()
            self._draft_changed()

    def _review(self) -> None:
        view = self.view
        if view is not None and view.review.isEnabled():
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
        view.save.setEnabled(True)
        count = evidence["count"]
        noun = "connection" if count == 1 else "connections"
        view.show_review(
            f"{key} · {count} stored {noun} · {sample_note}\n\n"
            f"Before\n{before}\n\nAfter\n{after}"
        )

    def _save(self) -> None:
        view = self.view
        if view is None or self._reviewed is None or self._pending:
            return
        command = EditRelationDefinitionCommand(
            self._database, self._raw, view.definition(), self._original, self._reviewed
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
        self._reviewed = None
        view.edit.setEnabled(True)
        if result.success:
            self._selected = view.definition()["key"]
            self._load_list(result.message)
        else:
            view.return_to_edit()
            view.show_message(result.message, error=True)
