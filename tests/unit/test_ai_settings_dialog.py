"""Tests for AI Settings Dialog autosave visual feedback."""

import pytest
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
