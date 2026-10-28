"""One modeless configuration surface; persistence lives in its coordinator."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.settings_registry import BY_ID, SETTINGS
from src.core.theme_manager import ThemeManager
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.responsive_form import scrollable_form_page
from src.gui.widgets.settings_forms import (
    AI_BINDINGS,
    BACKUP_BINDINGS,
    AISettingsForm,
    BackupSettingsForm,
    CalendarSettingsForm,
    GroupingSettingsForm,
    LexiconSettingsForm,
    layout_of,
)
from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton
from src.gui.widgets.wrapping_buttons import WrappingPushButton
from src.gui.widgets.wrapping_choices import WrappingCheckBox as QCheckBox

_NARROW_SETTINGS_WIDTH = 800


def read_control(control: Any) -> Any:
    """Read a standard control's user value."""
    if isinstance(control, QCheckBox):
        return control.isChecked()
    if isinstance(control, QComboBox):
        return (
            control.currentData()
            if control.currentData() is not None
            else control.currentText()
        )
    if hasattr(control, "toPlainText"):
        return control.toPlainText()
    if hasattr(control, "value"):
        return control.value()
    return control.text()


def write_control(control: Any, value: Any) -> None:
    """Hydrate controls without invoking consumer mutation signals."""
    blocked = control.blockSignals(True)
    try:
        if isinstance(control, QCheckBox):
            control.setChecked(bool(value))
        elif isinstance(control, QComboBox):
            index = control.findData(value)
            if index < 0:
                index = control.findText(str(value))
            if index >= 0:
                control.setCurrentIndex(index)
            elif control.isEditable():
                control.setCurrentText(str(value))
        elif hasattr(control, "setPlainText"):
            control.setPlainText(str(value or ""))
        elif hasattr(control, "setValue"):
            control.setValue(value)
        else:
            control.setText(str(value or ""))
    finally:
        control.blockSignals(blocked)


class SettingsCenter(QDialog):
    """Render drafts and emit intent, without accessing preference stores."""

    apply_requested = Signal(bool)
    cancel_requested = Signal()
    close_requested = Signal()
    reset_requested = Signal(str)
    operation_requested = Signal(str)
    connection_requested = Signal(dict)
    graph_form_created = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize detached settings state and explicit dependencies."""
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Settings Center")
        self.resize(960, 680)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.controls: dict[str, Any] = {}
        self.readers: dict[str, Callable[[], Any]] = {}
        self.pages: dict[tuple[str, str], QWidget] = {}
        self.world_name = "No world loaded"
        self.world_forms_ready = False
        self.invalid_fields: dict[str, str] = {}
        self._build_shell()
        self._build_local_pages()
        self._refresh_navigation()
        ThemeManager().theme_changed.connect(self._apply_theme)
        self._apply_theme()

    def _build_shell(self) -> None:
        layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(layout)
        self.search = declare_inspection(
            QLineEdit(),
            "settings.center.search|settings.center|help-inspect-settings-center-search",
        )
        self.search.setPlaceholderText("Search all settings…")
        self.search.setAccessibleName("Search all settings")
        layout.addWidget(self.search)
        self.scope = declare_inspection(
            QComboBox(),
            "settings.center.scope|settings.center|help-inspect-settings-center-scope",
        )
        self.scope.addItem("Kraken", "kraken")
        self.scope.addItem("This World — No world loaded", "world")
        layout.addWidget(self.scope)
        self.scope_caption = QLabel()
        self.scope_caption.setWordWrap(True)
        layout.addWidget(self.scope_caption)
        body = QHBoxLayout()
        self.content_layout = body
        self.navigation = declare_inspection(
            QListWidget(),
            "settings.center.navigation|settings.center|help-inspect-settings-center-navigation",
        )
        self.navigation.setMaximumWidth(290)
        self.navigation.setWordWrap(True)
        self.navigation.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.stack = QStackedWidget()
        self.empty_page = QLabel(
            "World settings will appear when a world is available."
        )
        self.empty_page.setWordWrap(True)
        self.stack.addWidget(self.empty_page)
        body.addWidget(self.navigation, 1)
        body.addWidget(self.stack, 3)
        layout.addLayout(body, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        from src.gui.widgets.action_flow_layout import ActionFlowLayout

        actions = ActionFlowLayout()
        self.reset_setting = StandardButton("Reset selected setting")
        self.reset_page = StandardButton("Reset page")
        self.apply_button = PrimaryButton("Apply")
        self.ok_button = StandardButton("OK")
        self.cancel_button = StandardButton("Cancel")
        for button in (
            self.reset_setting,
            self.reset_page,
            self.apply_button,
            self.ok_button,
            self.cancel_button,
        ):
            actions.addWidget(button)
            button.setAutoDefault(False)
        layout.addLayout(actions)
        self.reset_setting.clicked.connect(lambda: self.reset_requested.emit("setting"))
        self.reset_page.clicked.connect(lambda: self.reset_requested.emit("page"))
        self.apply_button.clicked.connect(lambda: self.apply_requested.emit(False))
        self.ok_button.clicked.connect(lambda: self.apply_requested.emit(True))
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.search.textChanged.connect(self._refresh_navigation)
        self.scope.currentIndexChanged.connect(self._refresh_navigation)
        self.navigation.currentItemChanged.connect(self._select_item)
        declare_inspection(
            self.apply_button,
            "settings.center.apply|settings.center|help-inspect-settings-center-apply",
        )
        declare_inspection(
            self.ok_button,
            "settings.center.ok|settings.center|help-inspect-settings-center-ok",
        )
        declare_inspection(
            self.cancel_button,
            "settings.center.cancel|settings.center|help-inspect-settings-center-cancel",
        )

    def add_page(self, scope: str, category: str, page: QWidget) -> None:
        """Install an actual configuration form, not a dialog launcher."""
        key = (scope, category)
        previous = self.pages.get(key)
        if previous is not None:
            self.stack.removeWidget(previous)
            previous.deleteLater()
        wrapper = scrollable_form_page(page)
        self.pages[key] = wrapper
        self.stack.addWidget(wrapper)
        page.show()

    def _simple_page(self, scope: str, category: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        StyleHelper.apply_standard_list_spacing(layout)
        self.add_page(scope, category, page)
        return page

    def _field(self, page: QWidget, key: str, choices: list[str] | None = None) -> None:
        definition = BY_ID[key]
        control: Any
        if choices is not None:
            control = declare_inspection(
                QComboBox(),
                "settings.center.preference|settings.center|help-inspect-settings-center-preference",
            )
            for choice in choices:
                control.addItem(
                    choice.replace("_", " ").title()
                    if choice
                    else "Use Kraken default",
                    choice,
                )
        elif isinstance(definition.default, bool):
            control = declare_inspection(
                QCheckBox(definition.label),
                "settings.center.preference|settings.center|help-inspect-settings-center-preference",
            )
        else:
            layout_of(page).addWidget(QLabel(definition.label))
            control = declare_inspection(
                QLineEdit(),
                "settings.center.preference|settings.center|help-inspect-settings-center-preference",
            )
            if definition.secret:
                control.setEchoMode(QLineEdit.EchoMode.Password)
        layout_of(page).addWidget(control)
        control.setAccessibleName(definition.label)
        self.controls[key] = control

    def _build_local_pages(self) -> None:
        appearance = self._simple_page("kraken", "Appearance")
        layout_of(appearance).addWidget(QLabel("Default theme"))
        self._field(
            appearance, "appearance.theme", ThemeManager().get_available_themes()
        )
        writing = self._simple_page("kraken", "Writing")
        for key in (
            "longform_auto_refresh",
            "SpellCheck/enabled",
            "SpellCheck/language",
            "secret.languagetool.username",
            "secret.languagetool.api_key",
        ):
            self._field(writing, key)
        timeline = self._simple_page("kraken", "Timeline")
        self._field(timeline, "timeline/snap_playhead_to_events")
        self._field(timeline, "timeline/show_dependencies")
        analysis = self._simple_page("kraken", "Analysis")
        self._field(analysis, "analysis/editorial_checks")
        self.ai = AISettingsForm(self)
        ai_page = self._simple_page("kraken", "AI")
        layout_of(ai_page).addWidget(self.ai.providers)
        layout_of(ai_page).addWidget(self.ai.knowledge)
        for key, attribute in AI_BINDINGS.items():
            self.controls[key] = getattr(self.ai, attribute)
        self.ai.provider_combo.setItemData(0, "sentence-transformers")
        self.ai.provider_combo.setItemData(1, "lmstudio")
        self.ai.connection_requested.connect(self.connection_requested.emit)
        self.ai.rebuild_index_requested.connect(self.operation_requested.emit)
        self.ai.index_status_requested.connect(
            lambda: self.operation_requested.emit("index-status")
        )
        self.backups = BackupSettingsForm(self)
        self.add_page("kraken", "Backups & storage", self.backups)
        for key, attribute in BACKUP_BINDINGS.items():
            self.controls[key] = getattr(self.backups, attribute)
        advanced = self._simple_page("kraken", "Advanced")
        reset_explanation = QLabel(
            "Resets preserve worlds, credentials, saved layouts, presets and history."
        )
        reset_explanation.setWordWrap(True)
        layout_of(advanced).addWidget(reset_explanation)
        for label, action in (
            ("Reset Kraken preferences", "kraken"),
            ("Reset workspace state…", "workspace"),
        ):
            button = WrappingPushButton(label)
            button.clicked.connect(
                lambda _checked=False, name=action: self.reset_requested.emit(name)
            )
            layout_of(advanced).addWidget(button)
        cast(QVBoxLayout, layout_of(advanced)).addStretch()

    def build_world_pages(self, snapshot: dict[str, Any]) -> None:
        """Replace world forms only for a new world/session, never on polling."""
        appearance = self._simple_page("world", "Appearance")
        layout_of(appearance).addWidget(QLabel("Theme override"))
        self._field(
            appearance, "world.theme", [""] + ThemeManager().get_available_themes()
        )
        writing = self._simple_page("world", "Writing")
        self._field(writing, "world.auto_relations")
        ai_page = self._simple_page("world", "AI")
        layout_of(ai_page).addWidget(QLabel("Index exclusions (comma-separated)"))
        excluded = declare_inspection(
            QLineEdit(),
            "settings.center.exclusions|settings.center|help-inspect-settings-center-exclusions",
        )
        self.controls["world.excluded_attributes"] = excluded
        layout_of(ai_page).addWidget(excluded)
        layout_of(ai_page).addWidget(self.ai.creative)
        layout_of(ai_page).addWidget(QLabel("World task templates — resources"))
        layout_of(ai_page).addWidget(self.ai.templates)
        self.readers["world.ai"] = self.ai.draft_preferences
        timeline = self._simple_page("world", "Timeline")
        values = snapshot["values"]
        self.calendar = CalendarSettingsForm(values.get("world.calendar"), timeline)
        self.grouping = GroupingSettingsForm(
            snapshot["tags"], values.get("world.grouping"), timeline
        )
        layout_of(timeline).addWidget(self.calendar)
        layout_of(timeline).addWidget(self.grouping)
        self.calendar.show()
        self.grouping.show()
        self.readers["world.calendar"] = self.calendar.draft_config
        self.readers["world.grouping"] = self.grouping.draft_config
        self.grouping.colors.update(values["world.tag_colors"])
        self.readers["world.tag_colors"] = lambda: dict(self.grouping.colors)
        self.lexicon = LexiconSettingsForm(snapshot, self)
        self.add_page("world", "Graph", self.lexicon)
        initial_lexicon = self.lexicon.get_lexicon_config()
        self.readers["world.lexicon"] = lambda: (
            values.get("world.lexicon")
            if self.lexicon.get_lexicon_config() == initial_lexicon
            else self.lexicon.get_lexicon_config()
        )
        self.world_forms_ready = True
        self._refresh_navigation()

    def render_values(self, values: dict[str, Any]) -> None:
        """Refresh only changed scalar controls, retaining focus and caret."""
        for key, value in values.items():
            if key in self.controls:
                control = self.controls[key]
                rendered = (
                    ", ".join(value) if key == "world.excluded_attributes" else value
                )
                if read_control(control) != rendered:
                    write_control(control, rendered)

    def render_complex(self, values: dict[str, Any]) -> None:
        """Hydrate changed complex snapshots, preserving untouched live editors."""
        if not self.world_forms_ready:
            return
        calendar = values.get("world.calendar")
        if "world.calendar" in values and self.calendar.draft_config() != calendar:
            self.calendar.set_snapshot(calendar)
        if (
            "world.grouping" in values
            and self.grouping.draft_config() != values["world.grouping"]
        ):
            self.grouping.current_config = values["world.grouping"] or {}
            for _, widget in self.grouping.tag_items.values():
                widget.set_checked(False)
            self.grouping._load_current_config()
        if "world.tag_colors" in values:
            self.grouping.colors = dict(values["world.tag_colors"])
            for name, (_, widget) in self.grouping.tag_items.items():
                if name in self.grouping.colors:
                    widget.tag_color = self.grouping.colors[name]
                    widget.color_button.set_color(widget.tag_color)
        if (
            "world.lexicon" in values
            and self.readers["world.lexicon"]() != values["world.lexicon"]
        ):
            data = {
                "values": {"world.lexicon": values["world.lexicon"]},
                "entity_types": self.lexicon._entity_types,
                "relation_types": self.lexicon._relation_types,
                "assets_dir": self.lexicon._assets_dir,
            }
            self.lexicon = LexiconSettingsForm(data, self)
            self.add_page("world", "Graph", self.lexicon)
            self.graph_form_created.emit(self.lexicon)
            initial = self.lexicon.get_lexicon_config()
            original = values["world.lexicon"]
            self.readers["world.lexicon"] = lambda: (
                original
                if self.lexicon.get_lexicon_config() == initial
                else self.lexicon.get_lexicon_config()
            )

    def collect(self) -> dict[str, Any]:
        """Return current form drafts; no effects or persistence."""
        values = {key: read_control(control) for key, control in self.controls.items()}
        if "world.excluded_attributes" in values:
            values["world.excluded_attributes"] = [
                part.strip()
                for part in values["world.excluded_attributes"].split(",")
                if part.strip()
            ]
        self.invalid_fields.clear()
        for key, reader in self.readers.items():
            try:
                values[key] = reader()
            except (ValueError, TypeError) as exc:
                self.invalid_fields[key] = str(exc)
        return values

    def render_states(self, pending: set[str], baseline: dict[str, Any]) -> None:
        """Distinguish unsaved edits from acknowledged non-default values."""
        for index in range(self.navigation.count()):
            item = self.navigation.item(index)
            scope, category, key = item.data(Qt.ItemDataRole.UserRole)
            members = (
                [BY_ID[key]]
                if key
                else [d for d in SETTINGS if (d.scope, d.category) == (scope, category)]
            )
            changed = any(d.id in pending for d in members)
            nondefault = any(
                d.resettable and d.id in baseline and baseline[d.id] != d.default
                for d in members
            )
            base = (
                f"{BY_ID[key].label} · {'This World' if scope == 'world' else 'Kraken'}"
                if key
                else category
            )
            item.setText(
                base
                + (" — Pending" if changed else " — Customized" if nondefault else "")
            )

    def navigate(self, setting_id: str | None = None, scope: str | None = None) -> None:
        """Deep-link to a setting's page and focus its control."""
        definition = BY_ID.get(setting_id or "")
        target_scope = definition.scope if definition else scope or "kraken"
        self.search.clear()
        self.scope.setCurrentIndex(1 if target_scope == "world" else 0)
        self._refresh_navigation()
        if definition:
            for index in range(self.navigation.count()):
                item = self.navigation.item(index)
                if tuple(item.data(Qt.ItemDataRole.UserRole)[:2]) == (
                    target_scope,
                    definition.category,
                ):
                    self.navigation.setCurrentItem(item)
                    break
            if setting_id in self.controls:
                self.controls[setting_id].setFocus()

    def selected_target(self) -> tuple[str, str, str]:
        """Identify reset scope/category and an optional search result."""
        item = self.navigation.currentItem()
        return (
            tuple(item.data(Qt.ItemDataRole.UserRole)) if item else ("kraken", "", "")
        )

    def _refresh_navigation(self) -> None:
        previous = self.selected_target()
        self.navigation.clear()
        query = self.search.text().strip()
        scope = self.scope.currentData()
        if query:
            entries: list[tuple[str, str, str, str]] = [
                (
                    d.scope,
                    d.category,
                    d.id,
                    f"{d.label} · {'This World' if d.scope == 'world' else 'Kraken'}",
                )
                for d in SETTINGS
                if d.matches(query) and (d.scope, d.category) in self.pages
            ]
        else:
            entries = [
                (s, category, "", category) for s, category in self.pages if s == scope
            ]
        for target_scope, category, key, label in entries:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, (target_scope, category, key))
            self.navigation.addItem(item)
            if (target_scope, category, key) == previous:
                self.navigation.setCurrentItem(item)
        if self.navigation.currentItem() is None and self.navigation.count():
            self.navigation.setCurrentRow(0)
        elif not self.navigation.count():
            self.stack.setCurrentWidget(self.empty_page)

    def _select_item(self, current: QListWidgetItem | None) -> None:
        if current is None:
            return
        scope, category, key = current.data(Qt.ItemDataRole.UserRole)
        self.stack.setCurrentWidget(self.pages[(scope, category)])
        self.scope_caption.setText(
            f"This World — {self.world_name}. These settings travel with the world."
            if scope == "world"
            else "Kraken — local preferences. Connections and credentials stay on this computer."
        )
        self.reset_setting.setEnabled(bool(key and BY_ID[key].resettable))
        if key in self.controls:
            self.controls[key].setFocus()

    def _apply_theme(self, _theme: dict[str, Any] | None = None) -> None:
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Let the coordinator protect drafts before closing."""
        event.ignore()
        self.close_requested.emit()

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802
        """Escape protects the Center draft; focused child editors keep Enter."""
        if event.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
            event.accept()
        else:
            QWidget.keyPressEvent(self, event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Stack category navigation above the form in narrow allocations."""
        super().resizeEvent(event)
        if not hasattr(self, "content_layout"):
            return
        narrow = self.width() < _NARROW_SETTINGS_WIDTH
        self.content_layout.setDirection(
            QHBoxLayout.Direction.TopToBottom
            if narrow
            else QHBoxLayout.Direction.LeftToRight
        )
        self.navigation.setMaximumWidth(16777215 if narrow else 290)
        self.navigation.setMaximumHeight(140 if narrow else 16777215)
