import pytest
from PySide6.QtWidgets import QApplication
from src.gui.dialogs.ai_settings_dialog import AISettingsDialog


@pytest.fixture
def qapp():
    """Ensure QApplication exists."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def dialog(qapp, qtbot):
    """Create AI Settings dialog."""
    dlg = AISettingsDialog()
    qtbot.addWidget(dlg)
    return dlg


def test_sidebar_structure(dialog):
    """Test that the dialog has the correct sidebar structure."""
    # We now have 4 items in the sidebar
    assert dialog.sidebar_list.count() == 4
    assert dialog.sidebar_list.item(0).text() == "Generative AI"
    assert dialog.sidebar_list.item(1).text() == "Knowledge Base"
    assert dialog.sidebar_list.item(2).text() == "Prompts & Persona"
    assert dialog.sidebar_list.item(3).text() == "Templates"

    # We should have 4 pages in the stack
    assert dialog.pages_stack.count() == 4
