from PySide6.QtWidgets import QLabel, QPushButton

from src.app.constants import VERSION
from src.gui.dialogs.about_dialog import AboutDialog


def test_about_dialog_initialization(qapp):
    """Test that AboutDialog initializes correctly."""
    dialog = AboutDialog()

    assert dialog.windowTitle() == "About ProjektKraken"

    # Check for version label
    version_label_found = False
    for child in dialog.findChildren(QLabel):
        if f"Version {VERSION}" in child.text():
            version_label_found = True
            break

    assert version_label_found, f"Version {VERSION} not found in dialog"


def test_about_dialog_has_close_button(qapp):
    """Test that AboutDialog has a close button."""
    dialog = AboutDialog()

    # Use findChild or search for buttons
    buttons = dialog.findChildren(QPushButton)
    assert len(buttons) >= 1

    close_btn = None
    for btn in buttons:
        if btn.text() == "Close":
            close_btn = btn
            break

    assert close_btn is not None
    # assert close_btn.isVisible()  # Skip visibility check in headless environment
