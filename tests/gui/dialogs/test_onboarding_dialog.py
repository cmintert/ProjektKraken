import pytest
from PySide6.QtWidgets import QApplication

from src.core.theme_manager import ThemeManager
from src.gui.widgets.map_widget import OnboardingDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_onboarding_dialog_init(qapp, qtbot):
    """Test that OnboardingDialog initializes correctly with themes."""
    # Ensure theme manager is initialized
    ThemeManager()

    dialog = OnboardingDialog()
    qtbot.addWidget(dialog)

    # Check title
    assert dialog.windowTitle() == "✨ Keyframe Created!"

    # Check if style sheet is applied (not empty)
    assert dialog.styleSheet() != ""

    # Check if buttons are present
    assert hasattr(dialog, "btn_got_it")
    assert hasattr(dialog, "btn_tutorial")

    # Check button text
    assert dialog.btn_got_it.text() == "Got it!"
    assert dialog.btn_tutorial.text() == "Show Tutorial Video"
