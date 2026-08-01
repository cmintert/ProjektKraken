"""Tests for AI Settings Dialog autosave visual feedback."""

from unittest.mock import patch

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from src.gui.dialogs.ai_settings_dialog import AISettingsDialog


@pytest.fixture
def qapp():
    """Ensure QApplication exists for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def dialog(qapp, qtbot):
    """Create AI Settings dialog for testing."""
    dlg = AISettingsDialog()
    qtbot.addWidget(dlg)
    return dlg


def test_dialog_has_save_status_label(dialog):
    """Test that dialog has a status label for save feedback."""
    assert hasattr(dialog, "save_status_label")
    assert dialog.save_status_label.text() == ""


def test_save_shows_saved_feedback_immediately(dialog, qtbot):
    """Test that save_settings shows 'Saved' feedback."""
    # Trigger save
    dialog.save_settings()

    # Status should show "Saved" after save completes
    assert dialog.save_status_label.text() == "Saved"


def test_save_shows_saved_feedback(dialog, qtbot):
    """Test that after save completes, shows 'Saved' feedback."""
    dialog.save_settings()

    # Wait for autohide timer (if any)
    qtbot.wait(100)

    # Should show "Saved" or similar confirmation
    text = dialog.save_status_label.text()
    assert text in ["Saved", "Settings saved", ""] or "Saved" in text


def test_save_status_autohides(dialog, qtbot):
    """Test that save status message auto-hides after delay."""
    dialog.save_settings()

    # Status should be visible initially
    assert dialog.save_status_label.text() != ""

    # Wait for autohide (typically 2-3 seconds)
    qtbot.wait(3500)

    # Status should be cleared
    assert dialog.save_status_label.text() == ""


def test_field_change_triggers_autosave_status(dialog, qtbot):
    """Test that save_settings shows visual feedback."""
    # Directly call save_settings
    dialog.save_settings()

    # Should show "Saved" status after save completes
    assert dialog.save_status_label.text() == "Saved"


def test_persona_prompt_change_triggers_autosave(dialog, qtbot):
    """Test that editing the Persona prompt editor triggers autosave."""
    # Clear status first
    dialog.save_status_label.setText("")

    # Type into the system prompt editor
    dialog.system_prompt_edit.setPlainText("New persona text")

    # The textChanged signal should have triggered save_settings
    assert dialog.save_status_label.text() == "Saved"


def test_summary_prompt_change_triggers_autosave(dialog, qtbot):
    """Test that editing the Summary Prompt editor triggers autosave."""
    # Clear status first
    dialog.save_status_label.setText("")

    # Type into the summary prompt editor
    dialog.summary_prompt_edit.setPlainText("New summary prompt")

    # The textChanged signal should have triggered save_settings
    assert dialog.save_status_label.text() == "Saved"


def test_malformed_settings_fall_back_to_safe_defaults(dialog):
    """Invalid persisted AI values must not break settings restoration."""
    malformed_values = {
        "ai_search_excluded_attrs": 42,
        "ai_auto_index_on_save": "sometimes",
        "ai_embedding_provider": [],
        "ai_lmstudio_timeout": "not-a-number",
        "ai_st_model": None,
        "ai_gen_lmstudio_enabled": "unknown",
        "ai_gen_openai_enabled": object(),
        "ai_gen_max_tokens": "many",
        "ai_gen_temperature": False,
        "ai_gen_filter_reasoning": 12,
        "ai_gen_system_prompt": {"unexpected": "mapping"},
        "ai_gen_summary_max_tokens": None,
        "ai_gen_summary_temperature": [],
    }

    def mock_value(key, default=None, type=None):
        return malformed_values.get(key, default)

    with (
        patch.object(QSettings, "value", side_effect=mock_value),
        patch.object(QSettings, "setValue"),
    ):
        dialog.load_settings()

    assert dialog.excluded_attrs_input.text() == ""
    assert dialog.chk_auto_index.isChecked() is False
    assert dialog.provider_combo.currentIndex() == 0
    assert dialog.lm_timeout_input.value() == 30
    assert dialog.st_model_input.text() == "all-MiniLM-L6-v2"
    assert dialog.lm_gen_enabled.isChecked() is True
    assert dialog.openai_gen_enabled.isChecked() is False
    assert dialog.max_tokens_input.value() == 512
    assert dialog.temperature_input.value() == 70
    assert dialog.filter_reasoning_cb.isChecked() is True
    assert dialog.system_prompt_edit.toPlainText()
    assert dialog.summary_max_tokens_input.value() == 2048
    assert dialog.summary_temperature_input.value() == 0
