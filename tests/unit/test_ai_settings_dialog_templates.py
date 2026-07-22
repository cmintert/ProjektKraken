"""Task-template management tests for AI Settings."""

from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from src.core.ai_generation import TaskIntent, TaskTemplate, TaskTemplateSource
from src.gui.dialogs.ai_settings_dialog import AISettingsDialog


@pytest.fixture
def built_in() -> TaskTemplate:
    return TaskTemplate(
        template_id="create_builtin",
        name="Create — Built In",
        description="Bundled task",
        intent=TaskIntent.CREATE,
        content="Write {name}",
        source=TaskTemplateSource.BUILT_IN,
    )


@pytest.fixture
def world_template() -> TaskTemplate:
    return TaskTemplate(
        template_id="29ee028a-e40e-441f-bd9d-e170c55bf998",
        name="World Revision",
        description="Custom world task",
        intent=TaskIntent.UPDATE,
        content="Revise {description}",
        source=TaskTemplateSource.WORLD,
    )


@pytest.fixture
def dialog(qtbot, built_in, world_template):
    instance = AISettingsDialog()
    qtbot.addWidget(instance)
    instance.set_task_templates((built_in, world_template))
    return instance


def _select(dialog: AISettingsDialog, template_id: str) -> None:
    for index in range(dialog.template_list.count()):
        item = dialog.template_list.item(index)
        if item.data(Qt.ItemDataRole.UserRole) == template_id:
            dialog.template_list.setCurrentItem(item)
            return
    raise AssertionError(f"Template not found: {template_id}")


def test_templates_page_structure(dialog):
    """The page exposes useful metadata without user-facing IDs."""
    dialog.sidebar_list.setCurrentRow(3)

    assert dialog.template_list.count() == 2
    assert hasattr(dialog, "template_name_edit")
    assert hasattr(dialog, "template_description_edit")
    assert hasattr(dialog, "template_intent_combo")
    assert hasattr(dialog, "btn_duplicate_template")
    assert not hasattr(dialog, "template_id_edit")


def test_built_in_is_locked_and_can_be_duplicated(dialog, built_in, qtbot):
    """Bundled tasks cannot be edited or deleted, only copied to the world."""
    _select(dialog, built_in.template_id)

    assert dialog.template_content_edit.isReadOnly()
    assert not dialog.btn_save_template.isEnabled()
    assert not dialog.btn_delete_template.isEnabled()
    assert dialog.btn_duplicate_template.isEnabled()

    with qtbot.waitSignal(dialog.task_templates_changed) as blocker:
        dialog.btn_duplicate_template.click()

    custom = blocker.args[0]
    assert len(custom) == 2
    assert custom[-1].source == TaskTemplateSource.WORLD
    assert custom[-1].name == "Copy of Create — Built In"


def test_new_template_saves_uuid_and_supported_variables(dialog, qtbot):
    """A new task is created in place and emitted as a world snapshot."""
    dialog.btn_new_template.click()
    dialog.template_name_edit.setText("Continuity Pass")
    dialog.template_description_edit.setText("Align supplied facts")
    dialog.template_intent_combo.setCurrentIndex(
        dialog.template_intent_combo.findData(TaskIntent.UPDATE.value)
    )
    dialog.template_content_edit.setPlainText("Revise {name}: {description}")

    with qtbot.waitSignal(dialog.task_templates_changed) as blocker:
        dialog.btn_save_template.click()

    custom = blocker.args[0]
    assert len(custom) == 2
    assert custom[-1].name == "Continuity Pass"
    assert custom[-1].template_id


def test_unsupported_variable_is_rejected(dialog):
    """The editor reports variables that generation cannot substitute."""
    dialog.btn_new_template.click()
    dialog.template_name_edit.setText("Broken")
    dialog.template_content_edit.setPlainText("Use {relations}")

    dialog.btn_save_template.click()

    assert "Unsupported template variables" in dialog.save_status_label.text()


def test_world_template_updates_in_place(dialog, world_template, qtbot):
    """Saving an existing world task retains its stable ID."""
    _select(dialog, world_template.template_id)
    dialog.template_content_edit.setPlainText("Improve {description}")

    with qtbot.waitSignal(dialog.task_templates_changed) as blocker:
        dialog.btn_save_template.click()

    updated = next(
        item for item in blocker.args[0] if item.template_id == world_template.template_id
    )
    assert updated.content == "Improve {description}"


def test_world_template_can_be_deleted(dialog, world_template, qtbot):
    """Deleting removes only the selected world-owned task."""
    _select(dialog, world_template.template_id)
    with patch.object(
        QMessageBox,
        "question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        with qtbot.waitSignal(dialog.task_templates_changed) as blocker:
            dialog.btn_delete_template.click()

    assert blocker.args[0] == ()


def test_dirty_editor_blocks_selection_change(dialog, built_in, world_template):
    """A declined discard confirmation restores the previous selection."""
    _select(dialog, world_template.template_id)
    dialog.template_content_edit.setPlainText("Unsaved edit")

    with patch.object(
        QMessageBox,
        "question",
        return_value=QMessageBox.StandardButton.No,
    ):
        _select(dialog, built_in.template_id)

    assert dialog._editing_template_id == world_template.template_id
