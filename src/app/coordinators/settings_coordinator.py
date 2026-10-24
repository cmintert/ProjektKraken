"""Draft, conflict and acknowledgement orchestration for the Settings Center."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QMessageBox, QWidget

from src.commands.settings_commands import ApplyWorldSettingsCommand
from src.core.ai_generation import AIGenerationPreferences
from src.core.calendar import CalendarConfig
from src.core.command import CommandResult
from src.core.settings_registry import BY_ID, SETTINGS, SettingsDraft
from src.gui.widgets.settings_center import SettingsCenter
from src.services.lmstudio_config import normalize_lmstudio_base_url
from src.services.local_settings import LocalSettingsAdapter


class SettingsCoordinator(QObject):
    """Own configuration state independently of view lifetime and selection."""

    snapshot_requested = Signal(dict)
    preferences_changed = Signal(dict)
    world_changed = Signal(dict)
    operation_requested = Signal(str)
    connection_requested = Signal(dict)
    world_form_created = Signal(object)
    icon_picker_created = Signal(object)
    index_rebuilt = Signal(dict)
    world_availability_changed = Signal(bool, str)

    def __init__(
        self,
        context: Callable[[], dict[str, Any]],
        execute: Callable[[Any], None],
        parent: QWidget,
        local: LocalSettingsAdapter | None = None,
    ) -> None:
        """Initialize detached settings state and explicit dependencies."""
        super().__init__(parent)
        self._parent_widget = parent
        self._snapshot_worker: QObject | None = None
        self._probe_worker: Any = None
        self.credential_warnings: list[str] = []
        self.rebuild_request: dict[str, Any] | None = None
        self._context = context
        self._execute = execute
        self.local = local or LocalSettingsAdapter()
        self.seed = self.local.legacy_seed()
        self._legacy_ai = self.local.legacy_ai_preferences()
        self.draft = SettingsDraft()
        self.draft.replace(self.local.snapshot())
        self.view: SettingsCenter | None = None
        self.world_values: dict[str, Any] = {}
        self.world_data: dict[str, Any] = {}
        self._token = ""
        self._database = ""
        self._pending: tuple[str, dict[str, Any], bool] | None = None
        self._reset_workspace = False
        self._after_apply: Callable[[], None] | None = None
        self._apply_errors: list[str] = []
        self._poll = QTimer(self)
        self._poll.setInterval(400)
        self._poll.timeout.connect(self._sync)
        self._poll.start()

    def open_settings(
        self, setting_id: str | None = None, scope: str | None = None
    ) -> None:
        """Raise one modeless window and optionally reveal a particular setting."""
        if self.view is None:
            self.view = SettingsCenter(self._parent_widget)
            self.view.apply_requested.connect(self.apply)
            self.view.cancel_requested.connect(self.cancel)
            self.view.close_requested.connect(self.request_close)
            self.view.reset_requested.connect(self.reset)
            self.view.operation_requested.connect(self.operation_requested.emit)
            self.view.connection_requested.connect(self.connection_requested.emit)
            self.view.graph_form_created.connect(self._attach_graph_form)
            self._install_world_forms()
            self.view.render_values(self.draft.values)
            self.operation_requested.emit("index-status")
        context = self._context()
        self.view.world_name = context.get("name", "No world loaded")
        self.view.scope.setItemText(1, f"This World — {self.view.world_name}")
        self.view.navigate(setting_id, scope)
        self.view.show()
        self.view.raise_()
        self.view.activateWindow()
        self.refresh_world()
        if self.credential_warnings:
            self.view.message.setText("\n".join(self.credential_warnings))

    def refresh_world(self) -> None:
        """Request only snapshots for the active database and request generation."""
        context = self._context()
        database = context.get("database", "")
        if not database:
            self._set_world_enabled(False, "No world is loaded.")
            return
        if database != self._database:
            self._database = database
            self._token = str(uuid.uuid4())
        seed = (
            self.seed if context.get("created_at", 0) < self.seed["captured_at"] else {}
        )
        self.snapshot_requested.emit(
            {
                "database": database,
                "token": self._token,
                "seed": seed,
                "ai_seed": self._legacy_ai if seed else {},
            }
        )
        if not self.world_data:
            self._set_world_enabled(False, "Loading this world's settings…")

    def on_snapshot(self, payload: dict[str, Any]) -> None:
        """Ignore stale responses and merge current values without destroying drafts."""
        if (
            payload.get("token") != self._token
            or payload.get("database") != self._database
        ):
            return
        if payload.get("error"):
            self.world_data["writable"] = False
            self._set_world_enabled(False, payload["error"])
            return
        previous = self.world_values
        self.world_data = deepcopy(payload)
        values = payload["values"]
        # Absent AI preferences are seeded through the existing AI lifecycle.
        values["world.ai"] = (
            values.get("world.ai") or AIGenerationPreferences().to_dict()
        )
        self.world_values = deepcopy(values)
        self._capture()
        self.draft.merge(values)
        if values != previous:
            self.world_changed.emit(deepcopy(values))
        self._install_world_forms()
        if values != previous:
            self._render_clean_world(values)
        self._set_world_enabled(
            bool(payload["writable"]),
            "This world is read-only." if not payload["writable"] else "",
        )

    def _install_world_forms(self) -> None:
        view = self.view
        if view is None or not self.world_data or view.world_forms_ready:
            return
        context = self._context()
        self.world_data["assets_dir"] = context.get("assets_dir")
        view.world_name = context.get("name", "World")
        view.scope.setItemText(1, f"This World — {view.world_name}")
        view.build_world_pages(self.world_data)
        self._attach_graph_form(view.lexicon)
        self._render_clean_world(self.draft.values)
        view.render_values(self.draft.values)

    def _render_clean_world(self, values: dict[str, Any]) -> None:
        view = self.view
        if view is None or not view.world_forms_ready:
            return
        dirty = self.draft.changes()
        if "world.ai" not in dirty and not view.ai._template_editor_dirty:
            from src.services.task_template_catalog import TaskTemplateCatalog

            preferences = AIGenerationPreferences.from_dict(values["world.ai"])
            view.ai.set_world_preferences(preferences.to_dict())
            templates = TaskTemplateCatalog().merge(preferences.custom_task_templates)
            if templates != view.ai._task_templates:
                view.ai.set_task_templates(templates)
        clean = {key: value for key, value in values.items() if key not in dirty}
        view.render_values(clean)
        view.render_complex(clean)

    def _attach_graph_form(self, form: Any) -> None:
        form.icon_picker_created.connect(self.icon_picker_created.emit)
        self.world_form_created.emit(form)

    def _set_world_enabled(self, enabled: bool, message: str) -> None:
        self.world_availability_changed.emit(enabled, message)
        if self.view is not None:
            for (scope, _), page in self.view.pages.items():
                if scope == "world":
                    page.setEnabled(enabled)
                    page.setToolTip(message)
            if message:
                self.view.message.setText(message)

    def _capture(self) -> None:
        if self.view is None:
            return
        try:
            self.draft.values.update(self.view.collect())
        except (ValueError, TypeError, AttributeError):
            # Invalid intermediate calendar input stays in the form until validation.
            return

    def _sync(self) -> None:
        view = self.view
        if view is None or not view.isVisible():
            return
        self._capture()
        self.draft.merge(self.local.snapshot(include_secrets=False))
        view.render_values(self.draft.values)
        pending = self.draft.changes()
        view.render_states(set(pending) | set(view.invalid_fields), self.draft.baseline)
        nondefault = sum(
            self.draft.baseline.get(d.id) != d.default
            for d in SETTINGS
            if d.id in self.draft.baseline and d.resettable
        )
        view.status.setText(
            f"{len(pending)} pending changes · {nondefault} saved non-default settings"
            + (
                f" · {len(self.draft.conflicts)} conflicts require review"
                if self.draft.conflicts
                else ""
            )
        )
        view.apply_button.setEnabled(
            bool(pending or self._reset_workspace) and self._pending is None
        )
        view.ok_button.setEnabled(self._pending is None)

    def set_contextual(self, key: str, value: Any) -> None:
        """Apply an explicit contextual control through the canonical backend."""
        self._capture()
        if BY_ID[key].scope == "world":
            if not self.world_data.get("writable") or self._pending is not None:
                return
            command = ApplyWorldSettingsCommand(
                {key: value}, {key: self.world_values.get(key)}, self._database
            )
            self._execute(command)
        else:
            saved, errors = self.local.save({key: value})
            if saved:
                self.draft.merge(saved)
                self.preferences_changed.emit(saved)
            if errors and self.view:
                self.view.message.setText("\n".join(errors))

    def has_pending_changes(self) -> bool:
        """Include drafts before the periodic UI synchronization runs."""
        self._capture()
        return bool(
            self._pending
            or self.draft.changes()
            or self._reset_workspace
            or (
                self.view
                and (self.view.invalid_fields or self.view.ai._template_editor_dirty)
            )
        )

    def _resolve_conflicts(self) -> None:
        assert self.view is not None
        keys = list(self.draft.conflicts)
        for key in keys:
            dialog = QMessageBox(self.view)
            dialog.setWindowTitle("Setting changed elsewhere")
            dialog.setText(f"{BY_ID[key].label} changed while you were editing.")
            current = dialog.addButton(
                "Use current value", QMessageBox.ButtonRole.AcceptRole
            )
            dialog.addButton("Keep my edit", QMessageBox.ButtonRole.ActionRole)
            dialog.exec()
            self.draft.resolve(key, dialog.clickedButton() != current)
        resolved = {key: self.draft.values[key] for key in keys}
        self.view.render_values(resolved)
        self.view.render_complex(resolved)

    def _validate(self, changes: dict[str, Any]) -> None:
        for key, value in changes.items():
            BY_ID[key].validate(value)
        if self.view is not None:
            self.view.collect()
            if self.view.invalid_fields:
                raise ValueError(next(iter(self.view.invalid_fields.values())))
        if "ai_lmstudio_base_url" in changes:
            normalize_lmstudio_base_url(str(changes["ai_lmstudio_base_url"]))
        if "world.calendar" in changes:
            errors = CalendarConfig.from_dict(changes["world.calendar"]).validate()
            if errors:
                raise ValueError("Calendar: " + "; ".join(errors))
        if self.view is not None and self.view.ai._template_editor_dirty:
            self.view.ai._on_save_template()
            if self.view.ai._template_editor_dirty:
                raise ValueError("Complete or discard the current task template draft.")
            self._capture()

    def apply(self, close_after: bool = False, *, world_only: bool = False) -> None:
        """Validate the complete draft before any backend write."""
        if self._pending is not None or self.view is None:
            return
        self._capture()
        self.draft.merge(self.local.snapshot())
        self._resolve_conflicts()
        changes = self.draft.changes()
        if world_only:
            changes = {
                key: value
                for key, value in changes.items()
                if BY_ID[key].scope == "world"
            }
        try:
            self._validate(changes)
        except ValueError as exc:
            self.view.message.setText(str(exc))
            self.view.navigate(
                "world.calendar" if "Calendar" in str(exc) else "world.ai"
            )
            return
        changes = self.draft.changes()
        if world_only:
            changes = {
                key: value
                for key, value in changes.items()
                if BY_ID[key].scope == "world"
            }
        world = {
            key: value for key, value in changes.items() if BY_ID[key].scope == "world"
        }
        if world and not self.world_data.get("writable"):
            self.view.message.setText("World settings are not available for editing.")
            return
        local = {
            key: value for key, value in changes.items() if BY_ID[key].scope == "kraken"
        }
        saved, errors = self.local.save(local)
        self._apply_errors = errors
        if errors:
            self._after_apply = None
        self.draft.acknowledge(saved)
        if saved:
            self.preferences_changed.emit(saved)
        if self._reset_workspace and not world_only:
            self.local.request_workspace_reset()
            self._reset_workspace = False
        self.view.message.setText(
            "\n".join(errors) if errors else "Local settings saved."
        )
        if world:
            command = ApplyWorldSettingsCommand(
                world, {key: self.draft.baseline[key] for key in world}, self._database
            )
            self._pending = (
                command.command_id,
                deepcopy(world),
                close_after and not errors,
            )
            self.view.stack.setEnabled(False)
            self.view.cancel_button.setEnabled(False)
            self._execute(command)
        elif not errors:
            self._finish_apply(close_after)

    def on_command_finished(self, result: CommandResult) -> None:
        """Only acknowledge the command matching the pending settings request."""
        if self._pending and result.data.get("command_id") == self._pending[0]:
            _, values, close_after = self._pending
            self._pending = None
            if self.view:
                self.view.stack.setEnabled(True)
                self.view.cancel_button.setEnabled(True)
            if result.success:
                self.draft.acknowledge(values)
                self._finish_apply(close_after)
            elif self.view:
                self._after_apply = None
                self.view.message.setText(
                    "\n".join([*self._apply_errors, result.message])
                )
        if result.command_name.endswith(
            (
                "ApplyWorldSettingsCommand",
                "CalendarConfigCommand",
                "TimelineGroupingCommand",
                "UpdateTagColorCommand",
                "SetActiveCalendarCommand",
            )
        ) or (self.view is not None and self.view.isVisible()):
            self.refresh_world()

    def _finish_apply(self, close_after: bool) -> None:
        if self.view:
            self.view.message.setText(
                (
                    "\n".join(self._apply_errors)
                    if self._apply_errors
                    else "Settings applied."
                )
                + (
                    " Existing indexed content requires an explicit rebuild."
                    if self.world_data.get("index_requires_rebuild")
                    else ""
                )
            )
            if close_after:
                self.view.hide()
        if self._after_apply is not None:
            callback, self._after_apply = self._after_apply, None
            callback()

    def cancel(self) -> None:
        """Discard only unacknowledged settings edits, preserving authoring state."""
        if self._pending is not None:
            return
        self.draft.replace(self.draft.baseline)
        self._reset_workspace = False
        if self.view:
            self.view.hide()
            self.view.deleteLater()
            self.view = None

    def request_close(self) -> None:
        """Protect pending edits on window-manager close."""
        self.request_transition(self.cancel)

    def request_transition(self, continuation: Callable[[], None]) -> None:
        """Guard world selection/closing without blocking an asynchronous Apply."""
        self._request_transition(continuation, world_only=False)

    def request_world_transition(self, continuation: Callable[[], None]) -> None:
        """Protect world edits while retaining independent Kraken drafts."""
        self._request_transition(continuation, world_only=True)

    def _request_transition(
        self, continuation: Callable[[], None], *, world_only: bool
    ) -> None:
        self._capture()
        if self._pending is not None:
            return
        changes = self.draft.changes()
        pending = (
            any(BY_ID[key].scope == "world" for key in changes)
            if world_only
            else bool(changes)
        )
        pending = pending or bool(
            self.view
            and (self.view.invalid_fields or self.view.ai._template_editor_dirty)
        )
        if not pending and (world_only or not self._reset_workspace):
            continuation()
            return
        dialog = QMessageBox(self.view)
        dialog.setWindowTitle("Pending settings changes")
        dialog.setText("Apply your settings changes before continuing?")
        apply = dialog.addButton("Apply", QMessageBox.ButtonRole.AcceptRole)
        discard = dialog.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        dialog.addButton("Keep editing", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() == apply:
            self._after_apply = continuation
            self.apply(world_only=world_only)
        elif dialog.clickedButton() == discard:
            if world_only:
                for key in list(self.draft.values):
                    if BY_ID[key].scope == "world":
                        self.draft.values[key] = deepcopy(self.draft.baseline[key])
                        self.draft.conflicts.pop(key, None)
                if self.view:
                    self.view.ai._template_editor_dirty = False
                    self._render_clean_world(self.world_values)
            else:
                self.cancel()
            continuation()

    def reset(self, target: str) -> None:
        """Stage only registry-approved defaults and an explicit workspace reset."""
        if self.view is None:
            return
        self._capture()
        scope, category, key = self.view.selected_target()
        if target == "workspace":
            reply = QMessageBox.question(
                self.view,
                "Reset workspace state?",
                "This resets transient layout and view state on Apply. Restart Kraken "
                "after applying. Saved layouts, presets and worlds are preserved.",
            )
            self._reset_workspace = reply == QMessageBox.StandardButton.Yes
            return
        defaults = self.local.snapshot()
        for definition in SETTINGS:
            selected = target == "kraken" and definition.scope == "kraken"
            selected |= target == "setting" and definition.id == key
            selected |= target == "page" and (
                definition.scope,
                definition.category,
            ) == (scope, category)
            if selected and definition.resettable:
                value = definition.default
                if value is None and definition.scope == "kraken":
                    from src.core.summary_data import DEFAULT_SUMMARY_PROMPT

                    value = DEFAULT_SUMMARY_PROMPT
                defaults[definition.id] = deepcopy(value)
        self.draft.values.update(
            {
                k: v
                for k, v in defaults.items()
                if BY_ID[k].resettable
                and (
                    target == "kraken"
                    or k == key
                    or (BY_ID[k].scope, BY_ID[k].category) == (scope, category)
                )
            }
        )
        self.view.render_values(self.draft.values)
        self.view.render_complex(self.draft.values)
