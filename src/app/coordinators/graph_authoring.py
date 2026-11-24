"""Route graph gestures through ordinary commands and world-owned snapshots."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

import shiboken6
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QDialog, QMessageBox

from src.app.coordinators.graph_pair_reader import GraphPairReader
from src.commands.batch_metadata_command import BatchMetadataCommand
from src.commands.graph_connection_command import GraphConnectionCommand
from src.commands.relation_commands import AddRelationCommand, UpdateRelationCommand
from src.core.batch_metadata import MetadataOperation, Target
from src.core.entities import Entity
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext
from src.gui.dialogs.entity_creation_dialog import EntityCreationDialog
from src.gui.dialogs.graph_connection_dialog import GraphConnectionDialog
from src.gui.dialogs.lifecycle_event_dialog import LifecycleEventDialog
from src.gui.dialogs.relation_dialog import RelationEditDialog
from src.gui.widgets.wiki_link_authoring import EntryLinkPicker
from src.services.authored_relation_service import AuthoredRelationService

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from src.app.command_coordinator import CommandCoordinator
    from src.app.coordinators.authoring_scope_coordinator import (
        AuthoringScopeCoordinator,
    )
    from src.app.coordinators.context_tag_coordinator import ContextTagCoordinator
    from src.app.coordinators.data_coordinator import DataCoordinator
    from src.app.coordinators.navigation_coordinator import NavigationCoordinator
    from src.commands.base_command import BaseCommand
    from src.core.calendar import CalendarConverter
    from src.core.command import CommandResult
    from src.gui.widgets.graph_view.graph_widget import GraphWidget
    from src.services.worker import DatabaseWorker


EntryKind = Literal["entity", "event"]
Context = tuple[str, int, int]


@dataclass(frozen=True)
class GraphEntry:
    """Identity and display data from the canonical GUI-side cache."""

    kind: EntryKind
    item: Entity | Event


@dataclass
class GraphDraft:
    """An unfinished gesture bound to its originating scope and world."""

    world: str
    scope_revision: int
    source: str
    position: dict[str, float] | None
    target: str = ""
    creation_kind: EntryKind | None = None
    creation_data: dict | None = None
    fixed_start: float | None = None


@dataclass(frozen=True)
class GraphSubmission:
    """Record the graph context without consulting live draft fields on reply."""

    command_id: str
    context: Context
    source: str
    target: str
    created: str | None
    position: dict[str, float] | None


@dataclass(frozen=True)
class SavedGraphConnection:
    """A committed graph result ready for the next matching snapshot."""

    submission: GraphSubmission
    relation_ids: frozenset[str]
    outside: str | None = None


class GraphAuthoring(QObject):
    """Own draft and feedback lifecycle while leaving graph reads to DataCoordinator."""

    pair_requested = Signal(dict)

    def __init__(
        self,
        view: GraphWidget,
        data: DataCoordinator,
        scope: AuthoringScopeCoordinator,
        tags: ContextTagCoordinator,
        commands: CommandCoordinator,
        navigation: NavigationCoordinator,
        worker: DatabaseWorker,
        world_id: Callable[[], str],
        playhead: Callable[[], float],
        calendar: Callable[[], CalendarConverter | None],
        membership_draft_warning: Callable[[list[Target]], str],
    ) -> None:
        """Connect queued reads and world-validated command acknowledgements."""
        super().__init__(view)
        self._view = view
        self._data = data
        self._scope = scope
        self._tags = tags
        self._commands = commands
        self._navigation = navigation
        self._world_id = world_id
        self._playhead = playhead
        self._calendar = calendar
        self._membership_draft_warning = membership_draft_warning
        self._draft: GraphDraft | None = None
        self._dialog: GraphConnectionDialog | None = None
        self._auxiliary: QWidget | None = None
        self._pending: GraphSubmission | None = None
        self._awaiting_snapshot: SavedGraphConnection | None = None
        self._feedback: SavedGraphConnection | None = None
        self._pair_requests: dict[str, dict] = {}
        self._interaction_revision = 0
        self._refreshing_after_failure = False

        thread = worker.thread()
        self._reader = GraphPairReader(worker)
        self._reader.moveToThread(thread)
        thread.finished.connect(self._reader.deleteLater)
        self.pair_requested.connect(
            self._reader.load, Qt.ConnectionType.QueuedConnection
        )
        self._reader.ready.connect(self._on_pair, Qt.ConnectionType.QueuedConnection)
        commands.graph_command_finished.connect(self._on_result)
        view.connection_requested.connect(self.begin)
        view.interaction_changed.connect(self._invalidate_feedback)
        view.snapshot_presented.connect(self._present_committed)
        view.feedback.inspect_requested.connect(self.inspect_saved)
        view.feedback.timing_requested.connect(self.inspect_timing)
        view.feedback.membership_requested.connect(self.add_to_tag_scope)
        scope.changed.connect(self._cancel_scope_draft)
        navigation.navigation_result.connect(self._on_navigation)
        worker.history_loaded.connect(
            tags.restore_graph_recovery, Qt.ConnectionType.QueuedConnection
        )

    def _context(self) -> Context:
        return self._world_id(), self._scope.revision, self._interaction_revision

    def _entries(self) -> dict[str, GraphEntry]:
        return {
            **{
                item.id: GraphEntry("entity", item)
                for item in self._data.cached_entities
            },
            **{item.id: GraphEntry("event", item) for item in self._data.cached_events},
        }

    def _invalidate_feedback(self) -> None:
        self._interaction_revision += 1
        self._feedback = None
        self._awaiting_snapshot = None
        self._pair_requests.pop("inspect", None)

    def _on_navigation(self, _kind: str, _identity: str, status: str) -> None:
        if status == "selected":
            self._view.authoring_context_changed()

    def _cancel_scope_draft(self, _scope: object) -> None:
        self._pair_requests.clear()
        self._refreshing_after_failure = False
        if self._auxiliary is not None and shiboken6.isValid(self._auxiliary):
            self._auxiliary.close()
        self._auxiliary = None
        if self._dialog is not None and shiboken6.isValid(self._dialog):
            self._dialog.reject()

    def _draft_current(self, draft: GraphDraft) -> bool:
        return (
            draft is self._draft
            and draft.world == self._world_id()
            and draft.scope_revision == self._scope.revision
        )

    @Slot(dict)
    def begin(self, gesture: dict) -> None:
        """Start a drag or the equivalent focusable Connect action."""
        if self._pending is not None:
            return
        if self._dialog is not None:
            self._dialog.raise_()
            self._dialog.activateWindow()
            return
        entries = self._entries()
        source = gesture.get("source")
        target = gesture.get("target")
        if not source:
            self._pick(
                self._view,
                {
                    key: entries[key]
                    for key in self._view.visible_node_ids
                    if key in entries
                },
                lambda selected: self.begin({"source": selected}),
            )
            return
        if source not in entries or source not in self._view.visible_node_ids:
            return
        if target and (target == source or target not in entries):
            return
        position = self._position(
            gesture.get("position")
        ) or self._view.new_node_position(source)
        draft = GraphDraft(self._world_id(), self._scope.revision, source, position)
        self._draft = draft
        dialog = GraphConnectionDialog(
            entries[source].item.name, self._view.relation_types(), self._view
        )
        self._dialog = dialog
        dialog.target_requested.connect(self._choose_target)
        dialog.save_requested.connect(self._save)
        dialog.edit_requested.connect(self._edit_existing)
        dialog.retry_pair_requested.connect(self._retry_draft_pair)
        dialog.start_at_playhead.toggled.connect(self._capture_start)
        dialog.finished.connect(self._close_draft)
        if target:
            self._connect_existing(draft, target)
        dialog.show()

    @staticmethod
    def _position(raw: object) -> dict[str, float] | None:
        if isinstance(raw, dict):
            x, y = raw.get("x"), raw.get("y")
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                if isfinite(x) and isfinite(y):
                    return {"x": float(x), "y": float(y)}
        return None

    def _close_draft(self, _outcome: int) -> None:
        self._pair_requests.pop("draft", None)
        self._draft = None
        self._dialog = None
        self._refreshing_after_failure = False

    def _pick(
        self,
        parent: QWidget,
        entries: dict[str, GraphEntry],
        chosen: Callable[[str], None],
    ) -> None:
        world, scope_revision, _ = self._context()
        items = []
        for identity, entry in entries.items():
            label = entry.item.name
            if not self._scope.scope.matches(entry.item.tags):
                label = f"{label} (outside scope)"
            items.append((identity, label, entry.kind))
        picker = EntryLinkPicker(
            parent, sorted(items, key=lambda row: row[1].casefold()), ""
        )
        picker.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._auxiliary = picker
        picker.chosen.connect(
            lambda identity: chosen(identity)
            if self._context()[:2] == (world, scope_revision)
            else None
        )
        anchor = (
            self._view.connect_button
            if parent is self._view
            else parent.focusWidget() or parent
        )
        picker.move(anchor.mapToGlobal(anchor.rect().bottomLeft()))
        picker.show()
        picker.search.setFocus()

    def _choose_target(self, action: str) -> None:
        draft, dialog = self._draft, self._dialog
        if draft is None or dialog is None or not self._draft_current(draft):
            return
        if action == "existing":
            entries = self._entries()
            entries.pop(draft.source, None)
            self._pick(
                dialog,
                entries,
                lambda identity: self._connect_existing(draft, identity),
            )
            return
        if action == "entity":
            form = EntityCreationDialog(dialog, self._data.cached_entity_types)
            self._auxiliary = form
            accepted = form.exec() == QDialog.DialogCode.Accepted
            values = (
                {"name": form.name(), "type": form.entity_type()} if accepted else {}
            )
            self._finish_target_form(draft, form, "entity", values, accepted)
        elif action == "event":
            event = LifecycleEventDialog("", self._calendar(), dialog)
            event.setWindowTitle("Create Event")
            event.restore_input({"name": "", "lore_date": self._playhead()})
            self._auxiliary = event
            accepted = event.exec() == QDialog.DialogCode.Accepted
            values = event.event_data if accepted else {}
            self._finish_target_form(draft, event, "event", values, accepted)

    def _finish_target_form(
        self,
        draft: GraphDraft,
        form: QDialog,
        kind: EntryKind,
        values: dict,
        accepted: bool,
    ) -> None:
        if shiboken6.isValid(form):
            form.deleteLater()
        self._auxiliary = None
        if accepted and self._draft_current(draft) and self._dialog is not None:
            values = {**values, "id": str(uuid4())}
            draft.target = values["id"]
            draft.creation_kind, draft.creation_data = kind, values
            self._dialog.set_target(values["name"])
            self._dialog.type_field.setFocus()

    def _connect_existing(self, draft: GraphDraft, identity: str) -> None:
        if not self._draft_current(draft) or self._dialog is None:
            return
        entry = self._entries().get(identity)
        if entry is not None and identity != draft.source:
            draft.target = identity
            title = entry.item.name
            if not self._scope.scope.matches(entry.item.tags):
                title += " (outside scope)"
            self._dialog.set_target(title, awaiting_relations=True)
            self._request_pair(draft.source, identity, "draft")

    def _retry_draft_pair(self) -> None:
        draft, dialog = self._draft, self._dialog
        if draft is None or dialog is None or not self._draft_current(draft):
            return
        dialog.pair_loading()
        self._request_pair(draft.source, draft.target, "draft")

    def _request_pair(self, source: str, target: str, purpose: str) -> None:
        request = {
            "id": str(uuid4()),
            "world": self._world_id(),
            "scope": self._scope.revision,
            "source": source,
            "target": target,
            "playhead": self._playhead(),
            "purpose": purpose,
        }
        self._pair_requests[purpose] = request
        self.pair_requested.emit(request)

    @Slot(dict)
    def _on_pair(self, reply: dict) -> None:
        request = reply["request"]
        purpose = request["purpose"]
        if (
            request != self._pair_requests.get(purpose)
            or request["world"] != self._world_id()
            or request["scope"] != self._scope.revision
        ):
            return
        self._pair_requests.pop(purpose)
        if purpose == "inspect":
            self._present_timing(reply)
            return
        draft, dialog = self._draft, self._dialog
        if (
            draft is None
            or dialog is None
            or not self._draft_current(draft)
            or (draft.source, draft.target) != (request["source"], request["target"])
        ):
            return
        if "error" in reply:
            dialog.pair_failed(reply["error"])
            return
        entries = self._entries()
        rows = [(self._relation_label(row, entries), row) for row in reply["rows"]]
        dialog.pair_ready(rows)

    @staticmethod
    def _relation_label(row: dict, entries: dict[str, GraphEntry]) -> str:
        source, target = entries.get(row["source_id"]), entries.get(row["target_id"])
        kind = row["rel_type"]
        if AuthoredRelationService.is_system_managed_type(kind):
            kind += " (read-only)"
        return (
            f"{source.item.name if source else row['source_id']} → "
            f"{target.item.name if target else row['target_id']} · {kind}"
        )

    def _capture_start(self, checked: bool) -> None:
        if self._draft is None or self._dialog is None:
            return
        self._draft.fixed_start = self._playhead() if checked else None
        converter = self._calendar()
        if checked:
            date = self._draft.fixed_start
            assert date is not None
            caption = converter.format_datetime(date) if converter else f"Day {date:g}"
            self._dialog.start_at_playhead.setText(f"Start at Playhead ({caption})")
        else:
            self._dialog.start_at_playhead.setText("Start at Playhead")

    def _save(self, kind: str, direction: str, _use_playhead: bool) -> None:
        draft = self._draft
        if draft is None or not self._draft_current(draft) or self._pending:
            return
        creation = None
        added: list[str] = []
        if draft.creation_kind is not None and draft.creation_data is not None:
            creation, added = self._tags.graph_creation(
                draft.creation_kind, draft.creation_data
            )
        source, target = draft.source, draft.target
        if direction == "reverse":
            source, target = target, source
        attributes = {}
        if draft.fixed_start is not None:
            attributes = {
                "valid_from": draft.fixed_start,
                "temporal": {
                    "schema": 1,
                    "behavior": "stateful",
                    "start": {"exact": draft.fixed_start},
                    "end": {"status": "open"},
                },
            }
        relation = AddRelationCommand(
            source, target, kind, attributes, bidirectional=direction == "reciprocal"
        )
        children: list[BaseCommand] = (
            [creation, relation] if creation is not None else [relation]
        )
        command = GraphConnectionCommand(children, "Create Graph Connection")
        if added:
            command.recovery = {
                "command_id": command.command_id,
                "added_tags": added,
                "item_type": draft.creation_kind,
                "item_id": draft.target,
                "created_at": command.timestamp,
            }
        self._submit(command, draft)

    def _edit_existing(self, row: dict) -> None:
        draft, dialog = self._draft, self._dialog
        if draft is None or dialog is None or not self._draft_current(draft):
            return
        entries = self._entries()
        source = entries.get(row["source_id"])
        target = entries.get(row["target_id"])
        if source is None or target is None:
            return
        source_event = source.item if isinstance(source.item, Event) else None
        calendar = self._calendar()
        form = RelationEditDialog(
            parent=dialog,
            source_name=source.item.name,
            source_event_id=source_event.id if source_event else None,
            source_event_date=source_event.lore_date if source_event else None,
            source_event_name=source_event.name if source_event else None,
            target_id=target.item.id,
            target_kind=target.kind,
            rel_type=row["rel_type"],
            attributes=row.get("attributes"),
            known_types=self._view.relation_types(),
            suggestion_items=[(target.item.id, target.item.name, target.kind)],
            calendar_converter=calendar,
            playhead_time=self._playhead(),
            temporal_context=TemporalResolutionContext.build(
                self._data.cached_events, calendar
            ),
        )
        form.bi_check.hide()
        form.target_edit.setReadOnly(True)
        self._auxiliary = form
        accepted = form.exec() == QDialog.DialogCode.Accepted
        target_id, kind, _, attributes = (
            form.get_data() if accepted else ("", "", False, {})
        )
        if shiboken6.isValid(form):
            form.deleteLater()
        self._auxiliary = None
        if accepted and target_id and self._draft_current(draft):
            relation = UpdateRelationCommand(
                row["id"], target_id, kind, attributes, expected=row
            )
            self._submit(
                GraphConnectionCommand([relation], "Edit Graph Connection"), draft
            )

    def _submit(self, command: GraphConnectionCommand, draft: GraphDraft) -> None:
        if self._dialog is None or self._commands.mutations_suspended:
            return
        self._pending = GraphSubmission(
            command.command_id,
            self._context(),
            draft.source,
            draft.target,
            draft.target if draft.creation_kind else None,
            draft.position,
        )
        self._dialog.set_pending(True, "Saving relationship…")
        self._commands.execute_command(command)

    @Slot(object)
    def _on_result(self, result: CommandResult) -> None:
        pending = self._pending
        matches = pending is not None and pending.command_id == result.data.get(
            "command_id"
        )
        if matches:
            self._pending = None
        if result.success:
            self._tags.apply_graph_recovery(result.data.get("graph_context_tags"))
            self._data.apply_graph_command(result)
        if not matches or pending is None:
            return
        current = pending.context == self._context() and self._view.isVisible()
        if not result.success:
            if pending.context[:2] == self._context()[:2]:
                self._report_failure(result)
            return
        if self._dialog is not None:
            self._dialog.accept()
        if current:
            raw = result.data.get("graph_relation_ids")
            ids = (
                frozenset(str(identity) for identity in raw)
                if isinstance(raw, list)
                else frozenset()
            )
            self._awaiting_snapshot = SavedGraphConnection(pending, ids)
            if pending.created and pending.position:
                self._view.seed_node(pending.created, pending.position)

    def _report_failure(self, result: CommandResult) -> None:
        if self._dialog is None:
            return
        if result.data.get("graph_error") == "rejected" or "cancelled" in result.data:
            self._dialog.set_pending(False, result.message)
        else:
            self._refreshing_after_failure = True
            self._dialog.set_pending(
                True,
                "The save could not be confirmed. Refreshing the graph before retry.",
            )
            self._data.load_data()
            self._data.load_graph_data()

    def _present_committed(self) -> None:
        if self._refreshing_after_failure and self._dialog is not None:
            self._refreshing_after_failure = False
            self._dialog.set_pending(
                False, "Graph refreshed. Review the draft before retrying."
            )
        saved = self._awaiting_snapshot
        if saved is None:
            return
        self._awaiting_snapshot = None
        if saved.submission.context != self._context():
            return
        entries = self._entries()
        outside = next(
            (
                identity
                for identity in (saved.submission.target, saved.submission.source)
                if identity in entries
                and not self._scope.scope.matches(entries[identity].item.tags)
            ),
            None,
        )
        self._feedback = SavedGraphConnection(
            saved.submission, saved.relation_ids, outside
        )
        if outside:
            self._view.feedback.present(
                f"Saved. {entries[outside].item.name} is outside the current scope.",
                inspect=True,
                timing=True,
                membership=bool(self._membership_tags(entries[outside])),
            )
            return
        reasons, excluded = self._view.show_saved_relations(saved.relation_ids)
        caption = "Relationship saved."
        if reasons:
            caption += (
                " Temporarily shown despite filters for " + ", ".join(reasons) + "."
            )
        if excluded:
            caption += " Current timing hides at least one saved relationship."
        self._view.feedback.present(caption, timing=bool(excluded))

    def _membership_tags(self, entry: GraphEntry) -> list[str]:
        tags = self._scope.scope.creation_tags
        if not set(tags).issubset(self._data.cached_tags):
            return []
        return [tag for tag in tags if tag not in entry.item.tags]

    def inspect_saved(self) -> None:
        """Open the outside endpoint through guarded inspector navigation."""
        saved = self._feedback
        if saved is None:
            return
        if saved.outside and (entry := self._entries().get(saved.outside)) is not None:
            self._navigation.set_global_selection(entry.kind, saved.outside)

    def inspect_timing(self) -> None:
        """Inspect the canonical timing of the saved relationship."""
        saved = self._feedback
        if saved is not None:
            self._request_pair(
                saved.submission.source, saved.submission.target, "inspect"
            )

    def _present_timing(self, result: dict) -> None:
        saved = self._feedback
        if saved is None or saved.submission.context != self._context():
            return
        entries = self._entries()
        rows = [
            row for row in result.get("rows", []) if row["id"] in saved.relation_ids
        ]
        caption = "\n\n".join(
            f"{self._relation_label(row, entries)}\n{row.get('timing_summary', 'Timing unavailable.')}"
            for row in rows
        )
        QMessageBox.information(
            self._view,
            "Saved Relationship Timing",
            caption or result.get("error", "The relationship is no longer available."),
        )

    def add_to_tag_scope(self) -> None:
        """Preview and apply a separate undoable membership edit."""
        saved = self._feedback
        if saved is None or saved.outside is None:
            return
        entry = self._entries().get(saved.outside)
        if entry is None or not (tags := self._membership_tags(entry)):
            return
        targets: list[Target] = [(entry.kind, entry.item.id)]
        if self._membership_blocked(targets):
            return
        response = QMessageBox.question(
            self._view,
            "Add to Tag Scope",
            f"Add the following tags to {entry.item.name}?\n\n" + "\n".join(tags),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if response != QMessageBox.StandardButton.Yes or self._feedback is not saved:
            return
        if self._membership_blocked(targets):
            return
        operation = MetadataOperation("add_tags", tags=tags)
        before, after, overwritten = operation.patch(entry.item.attributes)
        row = {
            "kind": entry.kind,
            "id": entry.item.id,
            "before": before,
            "after": after,
            "overwritten": overwritten,
        }
        command = BatchMetadataCommand(targets, operation.to_dict(), [row])
        self._commands.execute_command(command)
        self._view.authoring_context_changed()

    def _membership_blocked(self, targets: list[Target]) -> bool:
        if warning := self._membership_draft_warning(targets):
            self._view.feedback.present(
                warning, inspect=True, timing=True, membership=True
            )
            return True
        return False
