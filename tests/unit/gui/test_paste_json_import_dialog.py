"""Unit tests for PasteJsonImportDialog."""

from src.gui.dialogs.paste_json_import_dialog import PasteJsonImportDialog


def test_dialog_import_button_disabled_until_text(qtbot):
    """Import button should require non-empty editor content."""
    dialog = PasteJsonImportDialog()
    qtbot.addWidget(dialog)

    ok_button = dialog.buttons.button(dialog.buttons.StandardButton.Ok)
    assert ok_button is not None
    assert ok_button.isEnabled() is False

    dialog.json_edit.setPlainText("{\"entities\": []}")
    assert ok_button.isEnabled() is True


def test_get_json_text_returns_editor_content(qtbot):
    """Dialog should return exact editor text for coordinator parsing."""
    dialog = PasteJsonImportDialog()
    qtbot.addWidget(dialog)

    payload = "{\n  \"entities\": []\n}"
    dialog.json_edit.setPlainText(payload)

    assert dialog.get_json_text() == payload


def test_json_editor_uses_themed_style(qtbot):
    """JSON editor should use theme-aware input styling."""
    dialog = PasteJsonImportDialog()
    qtbot.addWidget(dialog)

    assert dialog.json_edit.styleSheet()
