"""Embedded configuration forms reusing Kraken's established rich editors.

These forms never call the legacy dialogs' persistence methods. They render
detached values and expose draft values to the Settings Center.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any, cast

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QLabel,
    QLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.ai_generation import AIGenerationPreferences, TaskTemplate
from src.core.calendar import CalendarConfig
from src.gui.dialogs.ai_settings_dialog import AISettingsDialog
from src.gui.dialogs.backup_settings_dialog import BackupSettingsDialog
from src.gui.dialogs.calendar_config_dialog import CalendarConfigDialog
from src.gui.dialogs.grouping_config_dialog import GroupingConfigDialog, TagListItem
from src.gui.dialogs.lexicon_editor_dialog import LexiconEditorDialog
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.standard_buttons import StandardButton
from src.services.task_template_catalog import TaskTemplateCatalog

# Attribute bindings preserve the existing provider controls and their semantics.
AI_BINDINGS = {
    "ai_auto_index_on_save": "chk_auto_index",
    "ai_embedding_provider": "provider_combo",
    "ai_lmstudio_base_url": "lm_gen_url_input",
    "ai_lmstudio_model": "lm_model_input",
    "ai_lmstudio_timeout": "lm_timeout_input",
    "ai_st_model": "st_model_input",
    "ai_gen_lmstudio_enabled": "lm_gen_enabled",
    "ai_gen_lmstudio_use_chat_api": "lm_gen_use_chat_api",
    "ai_gen_lmstudio_model": "lm_gen_model_input",
    "ai_gen_openai_enabled": "openai_gen_enabled",
    "ai_gen_openai_model": "openai_model_input",
    "ai_gen_google_enabled": "google_gen_enabled",
    "ai_gen_google_project_id": "google_project_input",
    "ai_gen_google_location": "google_location_input",
    "ai_gen_google_model": "google_model_input",
    "ai_gen_google_credentials_path": "google_creds_input",
    "ai_gen_anthropic_enabled": "anthropic_gen_enabled",
    "ai_gen_anthropic_model": "anthropic_model_input",
    "ai_gen_summary_prompt": "summary_prompt_edit",
    "ai_gen_summary_max_tokens": "summary_max_tokens_input",
    "ai_gen_summary_temperature": "summary_temperature_input",
    "secret.lmstudio": "lm_api_key_input",
    "secret.openai": "openai_api_key_input",
    "secret.anthropic": "anthropic_api_key_input",
}
BACKUP_BINDINGS = {
    "backup_enabled": "chk_enabled",
    "backup_auto_save_interval": "spin_interval",
    "backup_auto_save_retention": "spin_auto_retention",
    "backup_daily_retention": "spin_daily_retention",
    "backup_weekly_retention": "spin_weekly_retention",
    "backup_manual_retention": "spin_manual_retention",
    "backup_verify_after": "chk_verify",
    "backup_vacuum_before": "chk_vacuum",
    "backup_custom_dir": "edit_custom_dir",
    "backup_external_path": "edit_external_path",
}


def layout_of(widget: QWidget) -> QLayout:
    """Return a constructed form's layout, failing on a composition error."""
    layout = widget.layout()
    if layout is None:
        raise ValueError("A settings form requires a layout")
    return layout


def form_layout(widget: QWidget) -> QVBoxLayout:
    """Give embedded forms the shared spacing and theme style."""
    layout = QVBoxLayout(widget)
    StyleHelper.apply_standard_list_spacing(layout)
    return layout


def enclosing_group(widget: QWidget) -> QGroupBox:
    """Locate a reusable section without depending on its translated caption."""
    parent = widget.parentWidget()
    while parent is not None and not isinstance(parent, QGroupBox):
        parent = parent.parentWidget()
    if parent is None:
        raise ValueError("Expected a configuration group")
    return parent


class _EmbeddedInput:
    """Embedded forms leave acceptance and dismissal to their containing Center."""

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Prevent legacy QDialog defaults from accepting or hiding a form."""
        QWidget.keyPressEvent(cast(QWidget, self), event)


class AISettingsForm(_EmbeddedInput, AISettingsDialog):
    """Reuse provider/template editors without constructing a settings dialog."""

    connection_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize detached settings state and explicit dependencies."""
        QDialog.__init__(self, parent, Qt.WindowType.Widget)
        self.setWindowFlags(Qt.WindowType.Widget)
        self._initializing = True
        self._discovery_worker = None
        self._task_templates: tuple[TaskTemplate, ...] = ()
        self._editing_template_id = None
        self._template_editor_dirty = False
        self._restoring_template_selection = False
        self._task_template_catalog = TaskTemplateCatalog()
        self._world_preferences = AIGenerationPreferences()
        self.save_status_label = QLabel()
        self._status_hide_timer = QTimer(self)
        self.providers = self._create_generative_ai_page()
        for key, attribute in AI_BINDINGS.items():
            if key.startswith("ai_gen_") and key.endswith("_enabled"):
                getattr(self, attribute).setText("Enable provider on this computer")
        for button in self.providers.findChildren(QPushButton):
            if button.text() == "Clear All AI Settings":
                button.hide()
        self.knowledge = self._create_knowledge_base_page()
        self.creative = self._create_prompts_page()
        self.templates = self._create_templates_page()
        # Move portable parameters out of the machine/provider section.
        layout_of(self.creative).addWidget(enclosing_group(self.max_tokens_input))
        # Summary generation is currently machine-local; do not silently rescope it.
        for control in (self.summary_prompt_edit, self.summary_max_tokens_input):
            layout_of(self.providers).addWidget(enclosing_group(control))
        enclosing_group(self.excluded_attrs_input).hide()
        self.btn_save_template.setText("Update template draft")
        self._initializing = False
        self.hide()

    def save_settings(self) -> None:
        """Field changes are drafts; persistence is owned by the coordinator."""

    def _on_clear_generation_settings(self) -> None:
        """Keep reset behavior in the Center's explicit reset controls."""
        self.save_status_label.setText("Use Reset page in the Settings Center.")

    def _test_connection(self, provider_id: str, mode: str) -> None:
        """Request a provider probe without reading or writing settings."""
        self.connection_requested.emit(
            {
                "provider": provider_id,
                "mode": mode,
                "url": self.lm_gen_url_input.text(),
                "key": self.lm_api_key_input.text(),
                "timeout": self.lm_timeout_input.value(),
            }
        )

    def set_world_preferences(self, data: dict[str, Any]) -> None:
        """Render portable values without populating any persistent cache."""
        self._original_world_preferences = dict(data)
        self._world_preferences = AIGenerationPreferences.from_dict(data)
        p = self._world_preferences
        if self.system_prompt_edit.toPlainText() != p.persona:
            self.system_prompt_edit.setPlainText(p.persona)
        self.max_tokens_input.setRange(
            min(self.max_tokens_input.minimum(), p.max_tokens),
            max(self.max_tokens_input.maximum(), p.max_tokens),
        )
        self.max_tokens_input.setValue(p.max_tokens)
        self.temperature_input.setValue(p.temperature_percent)
        self.filter_reasoning_cb.setChecked(p.filter_reasoning)
        self.enable_audit_log.setChecked(p.audit_enabled)

    def draft_preferences(self) -> dict[str, Any]:
        """Return a detached world value, retaining advanced existing options."""
        result = dict(getattr(self, "_original_world_preferences", {}))
        result.update(
            replace(
                self._world_preferences,
                persona=self.system_prompt_edit.toPlainText(),
                max_tokens=self.max_tokens_input.value(),
                temperature_percent=self.temperature_input.value(),
                filter_reasoning=self.filter_reasoning_cb.isChecked(),
                audit_enabled=self.enable_audit_log.isChecked(),
                custom_task_templates=self.get_custom_task_templates(),
            ).to_dict()
        )
        return result


class BackupSettingsForm(_EmbeddedInput, BackupSettingsDialog):
    """Backup controls without save buttons or QSettings access."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize detached settings state and explicit dependencies."""
        QDialog.__init__(self, parent, Qt.WindowType.Widget)
        self.setWindowFlags(Qt.WindowType.Widget)
        layout = form_layout(self)
        self._create_general_section(layout)
        self._create_retention_section(layout)
        self._create_location_section(layout)
        self.edit_custom_dir.textChanged.connect(self._update_path_label)


class CalendarSettingsForm(_EmbeddedInput, CalendarConfigDialog):
    """Lossless calendar editor with validation owned by the Apply boundary."""

    def __init__(
        self, data: dict[str, Any] | None, parent: QWidget | None = None
    ) -> None:
        """Initialize detached settings state and explicit dependencies."""
        QDialog.__init__(self, parent, Qt.WindowType.Widget)
        self.setWindowFlags(Qt.WindowType.Widget)
        self._config = (
            CalendarConfig.from_dict(data) if data else CalendarConfig.create_default()
        )
        self._empty_initial: dict[str, Any] | None = None
        self._validation_errors = []
        self._setup_ui()
        self.button_box.hide()
        self.set_snapshot(data)

    def set_snapshot(self, data: dict[str, Any] | None) -> None:
        """Render the one-based leap month while retaining original metadata."""
        self._empty_initial = None
        self._config = (
            CalendarConfig.from_dict(data) if data else CalendarConfig.create_default()
        )
        self._load_config()
        for row, rule in enumerate(self._config.leap_year_rules):
            item = self.leap_table.item(row, 3)
            if item is not None:
                item.setText(str(rule.month_index + 1))
        if data is None:
            self._empty_initial = self.draft_config()

    def draft_config(self) -> dict[str, Any] | None:
        """Read the complete calendar, including leap and advanced values."""
        for row in range(self.leap_table.rowCount()):
            for column in range(self.leap_table.columnCount()):
                item = self.leap_table.item(row, column)
                if item is None:
                    raise ValueError("Calendar: complete the leap rule.")
                try:
                    value = int(item.text())
                except ValueError as exc:
                    raise ValueError(
                        "Calendar: leap rules require whole numbers."
                    ) from exc
                if column == 0 and value <= 0:
                    raise ValueError("Calendar: leap interval must be positive.")
        config = self._build_config_from_ui()
        config.modified_at = self._config.modified_at
        config.is_active = self._config.is_active
        result = config.to_dict()
        return None if result == self._empty_initial else result


class GroupingSettingsForm(_EmbeddedInput, GroupingConfigDialog):
    """Stage grouping and shared tag colours without submitting commands."""

    def __init__(
        self,
        tags: list[dict[str, Any]],
        config: dict[str, Any] | None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize detached settings state and explicit dependencies."""
        QDialog.__init__(self, parent, Qt.WindowType.Widget)
        self.setWindowFlags(Qt.WindowType.Widget)
        self.tags_data = tags
        self.current_config = config or {}
        self.tag_items = {}
        self.colors = {tag["name"]: tag["color"] for tag in tags}
        self._setup_ui()
        self.button_box.hide()
        self._load_tags()
        self._load_current_config()

    def _on_tag_color_changed(self, tag_name: str, color: str) -> None:
        """Keep colour edits inside the current draft."""
        self.colors[tag_name] = color

    def draft_config(self) -> dict[str, Any] | None:
        """Return the selected order and the established grouping mode."""
        tags = []
        for index in range(self.list_widget.count()):
            widget = self.list_widget.itemWidget(self.list_widget.item(index))
            if isinstance(widget, TagListItem) and widget.is_checked():
                tags.append(widget.tag_name)
        return (
            {
                "tag_order": tags,
                "mode": "FIRST_MATCH"
                if self.radio_first_match.isChecked()
                else "DUPLICATE",
            }
            if tags
            else None
        )


class LexiconSettingsForm(_EmbeddedInput, LexiconEditorDialog):
    """Embed the established graph style editor; previews stay in the form."""

    def __init__(self, data: dict[str, Any], parent: QWidget | None = None) -> None:
        """Initialize detached settings state and explicit dependencies."""
        QDialog.__init__(self, parent, Qt.WindowType.Widget)
        self.setWindowFlags(Qt.WindowType.Widget)
        self._entity_types = data.get("entity_types", [])
        self._relation_types = data.get("relation_types", [])
        self._config = data.get("values", {}).get("world.lexicon") or {
            "nodes": {},
            "edges": {},
        }
        self._assets_dir = data.get("assets_dir")
        self._node_rows = {}
        self._edge_rows = {}
        self._setup_ui()
        info_item = layout_of(self).itemAt(0)
        assert info_item is not None
        info = info_item.widget()
        if isinstance(info, QLabel):
            info.setText(
                "Configure visual styles for each type. "
                "Choose Apply in Settings Center to update the graph."
            )
        for name, row in self._node_rows.items():
            for key in ("color", "border_color"):
                row[key].setAccessibleName(
                    f"{key.replace('_', ' ').title()} for {name}"
                )
            self._replace_icon_actions(name, row)
        for name, row in self._edge_rows.items():
            row["color"].setAccessibleName(f"Relation colour for {name}")
            row["dashes"].setText("Dashed")
        # The original button box is a compatibility detail, never a second save route.
        from src.gui.widgets.responsive_dialog_buttons import ResponsiveDialogButtonBox

        for box in self.findChildren(ResponsiveDialogButtonBox):
            box.hide()

    def _replace_icon_actions(self, name: str, row: dict[str, Any]) -> None:
        """Reuse shared content-sized buttons in the existing graph style grid."""
        for key, text in (("icon_btn", "Choose icon…"), ("clear_btn", "Clear icon")):
            old = row[key]
            parent = old.parentWidget()
            button = StandardButton(text, parent)
            button.setAutoDefault(False)
            declare_inspection(button, old.property("krakenHelpBinding"))
            layout_of(parent).replaceWidget(old, button)
            row[key] = button
            old.hide()
            old.deleteLater()
        row["icon_btn"].clicked.connect(
            lambda _checked=False: self._select_icon(
                name, row["icon_btn"], row["shape"]
            )
        )
        row["clear_btn"].setEnabled(bool(row["icon_id"]))
        row["clear_btn"].clicked.connect(lambda _checked=False: self._clear_icon(name))

    def get_lexicon_config(self) -> dict[str, Any]:
        """Retain styles for currently unused types and unknown style metadata."""
        edited = super().get_lexicon_config()
        result = deepcopy(self._config)
        for section, styles in edited.items():
            destination = result.setdefault(section, {})
            for name, style in styles.items():
                merged = dict(destination.get(name, {}))
                if section == "nodes":
                    merged.pop("icon_id", None)
                merged.update(style)
                destination[name] = merged
        return result

    def _clear_icon(self, type_name: str) -> None:
        """Keep the shared picker wording after the existing clear operation."""
        super()._clear_icon(type_name)
        if type_name in self._node_rows:
            self._node_rows[type_name]["icon_btn"].setText("Choose icon…")
