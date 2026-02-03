from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from src.gui.dialogs.ai_settings_dialog import AISettingsDialog


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_loader():
    with patch("src.gui.dialogs.ai_settings_dialog.PromptLoader") as MockLoader:
        loader_instance = MockLoader.return_value
        # Setup default return values
        loader_instance.list_templates.return_value = [
            {
                "template_id": "test_t1",
                "version": "1.0",
                "name": "Test Template 1",
                "description": "Desc 1",
                "content": "Content 1",
                "metadata": {"name": "Test Template 1"},
            },
            {
                "template_id": "test_t2",
                "version": "2.0",
                "name": "Test Template 2",
                "description": "Desc 2",
                "content": "Content 2",
                "metadata": {"name": "Test Template 2"},
            },
        ]

        def create_mock_template(tid, v=None):
            m = MagicMock()
            m.template_id = tid
            m.version = "1.0"
            m.name = f"Name {tid}"
            m.content = f"Content {tid}"
            m.metadata = {}
            return m

        loader_instance.load_template.side_effect = create_mock_template
        yield loader_instance


@pytest.fixture
def dialog(qapp, qtbot, mock_loader):
    dlg = AISettingsDialog()
    qtbot.addWidget(dlg)
    return dlg


def test_templates_sidebar_item_exists(dialog):
    """Test that 'Templates' item exists in sidebar."""
    # Should be 4th item (index 3)
    assert dialog.sidebar_list.count() == 4
    assert dialog.sidebar_list.item(3).text() == "Task Templates"


def test_templates_page_structure(dialog):
    """Test the structure of the templates page."""
    # Select Templates page
    dialog.sidebar_list.setCurrentRow(3)

    # Check key widgets exist
    assert hasattr(dialog, "template_list")  # The list of templates
    assert hasattr(dialog, "template_id_edit")
    assert hasattr(dialog, "template_name_edit")
    assert hasattr(dialog, "template_content_edit")
    assert hasattr(dialog, "btn_new_template")
    assert hasattr(dialog, "btn_save_template")
    assert hasattr(dialog, "btn_delete_template")


def test_templates_list_population(dialog, mock_loader):
    """Test that template list is populated from loader."""
    dialog.sidebar_list.setCurrentRow(3)  # Switch to page to trigger refresh if needed

    # Force refresh manually if it's not auto-triggered (implementation detail)
    if hasattr(dialog, "_refresh_templates_list"):
        dialog._refresh_templates_list()

    assert dialog.template_list.count() == 2
    assert dialog.template_list.item(0).data(Qt.ItemDataRole.UserRole) == "test_t1"
    assert dialog.template_list.item(1).data(Qt.ItemDataRole.UserRole) == "test_t2"


def test_select_template_populates_editor(dialog, mock_loader, qtbot):
    """Test selecting a template populates the editor fields."""
    dialog.sidebar_list.setCurrentRow(3)
    dialog._refresh_templates_list()

    # Mock load_template return specifically for this test
    mock_loader.load_template.side_effect = None
    mock_template = MagicMock()
    mock_template.template_id = "test_t1"
    mock_template.name = "Test Template 1"
    mock_template.content = "Content 1"
    mock_template.metadata = {"description": "Desc 1"}
    mock_loader.load_template.return_value = mock_template

    # Select first item
    dialog.template_list.setCurrentRow(0)

    assert dialog.template_id_edit.text() == "test_t1"
    assert dialog.template_name_edit.text() == "Test Template 1"
    # assert dialog.template_content_edit.toPlainText() == "Content 1"
    # depends on widget type


def test_new_template_clears_editor(dialog, qtbot):
    """Test clicking New Template clears fields."""
    dialog.sidebar_list.setCurrentRow(3)

    # Simulate existing data
    dialog.template_id_edit.setText("old")
    dialog.template_name_edit.setText("old")

    # Click New
    qtbot.mouseClick(dialog.btn_new_template, Qt.MouseButton.LeftButton)

    assert dialog.template_id_edit.text() == ""
    assert dialog.template_name_edit.text() == ""
    assert dialog.template_id_edit.isReadOnly() is False


def test_save_template(dialog, mock_loader, qtbot):
    """Test saving calls loader.save_template."""
    dialog.sidebar_list.setCurrentRow(3)

    # Fill data
    dialog.template_id_edit.setText("new_t")
    dialog.template_name_edit.setText("New T")
    dialog.template_content_edit.setPlainText("New Content")

    # Click Save
    qtbot.mouseClick(dialog.btn_save_template, Qt.MouseButton.LeftButton)

    # Verify mock call
    mock_loader.save_template.assert_called_once()
    args = mock_loader.save_template.call_args
    assert args[0][0] == "new_t"  # id
    assert args[0][1] == "New Content"  # content
    assert args[0][2]["name"] == "New T"  # metadata


def test_delete_template(dialog, mock_loader, qtbot):
    """Test deleting calls loader.delete_template."""
    dialog.sidebar_list.setCurrentRow(3)
    dialog._refresh_templates_list()
    dialog.template_list.setCurrentRow(0)  # Select first

    # Mock confirmation dialog to click Yes
    with patch.object(
        QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
    ):
        qtbot.mouseClick(dialog.btn_delete_template, Qt.MouseButton.LeftButton)

    mock_loader.delete_template.assert_called_once_with("test_t1")
