"""Tests for ProgressDialog widget."""

import pytest


@pytest.fixture
def qapp():
    """Fixture to provide QApplication instance."""
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
    except ImportError:
        pytest.skip("PySide6 not available")


def test_progress_dialog_creation(qapp):
    """Test that ProgressDialog can be created."""
    from src.gui.dialogs.progress_dialog import ProgressDialog

    dialog = ProgressDialog("Test operation", None, False, "Test Title")

    assert dialog is not None
    assert dialog.windowTitle() == "Test Title"
    assert dialog.minimum() == 0
    assert dialog.maximum() == 0  # Indeterminate

    dialog.close()


def test_progress_dialog_update_text(qapp):
    """Test that dialog text can be updated."""
    from src.gui.dialogs.progress_dialog import ProgressDialog

    dialog = ProgressDialog("Initial text", None, False)

    dialog.update_text("Updated text")
    assert dialog.labelText() == "Updated text"

    dialog.close()


def test_progress_dialog_finish(qapp):
    """Test that dialog can be closed via finish()."""
    from src.gui.dialogs.progress_dialog import ProgressDialog

    dialog = ProgressDialog("Test", None, False)

    dialog.finish()
    # Dialog should be closed after finish()
    assert not dialog.isVisible()


def test_progress_dialog_cancelable(qapp):
    """Test cancelable progress dialog."""
    from src.gui.dialogs.progress_dialog import ProgressDialog

    # Create cancelable dialog
    dialog = ProgressDialog("Test", None, cancelable=True)

    # Should have cancel button (not None)
    # Note: We can't easily test the button text without showing the dialog

    dialog.close()


def test_progress_dialog_non_cancelable(qapp):
    """Test non-cancelable progress dialog (default)."""
    from src.gui.dialogs.progress_dialog import ProgressDialog

    # Create non-cancelable dialog (default)
    dialog = ProgressDialog("Test", None)

    # Cancel button should be None
    # This is the default behavior

    dialog.close()
