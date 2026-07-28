from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QPlainTextEdit

from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.gui.widgets.llm_generation_widget import LLMGenerationWidget


@pytest.fixture
def widget(qtbot, tmp_path):
    """Fixture for LLMGenerationWidget."""
    original_format = QSettings.defaultFormat()
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.clear()
    widget = LLMGenerationWidget()
    qtbot.addWidget(widget)
    yield widget
    QSettings.setDefaultFormat(original_format)


@patch("src.gui.widgets.llm_generation_widget.RAGService")
def test_preview_rag_success(mock_rag_cls, widget, qtbot):
    """Verify preview works correctly with RAGService."""
    # 1. Setup RAG Mock
    mock_service = MagicMock()
    mock_rag_cls.return_value = mock_service
    mock_service.get_context.return_value = "Verified RAG Context"

    # 2. Setup Widget State
    widget.rag_cb.setChecked(True)
    widget.rag_limit_input.setText("2")
    widget._get_generation_context = MagicMock(
        return_value={
            "name": "Test Entity",
            "type": "Character",
            "object_type": "entity",
            "existing_description": "Existing description",
        }
    )

    # Mock window traversal for db_path
    mock_window = MagicMock()
    mock_window.db_path = "dummy.db"
    widget.window = MagicMock(return_value=mock_window)

    widget.custom_prompt_edit.setPlainText("User {{RAG_CONTEXT}}")

    captured = {}

    def capture_preview(dialog):
        text_edits = dialog.findChildren(QPlainTextEdit)
        assert len(text_edits) == 1
        captured["display_text"] = text_edits[0].toPlainText()
        return 0

    # Patch only exec(), retaining a real dialog and child widgets so layout
    # construction and preview rendering are still exercised.
    with (
        patch(
            "src.gui.widgets.llm_generation_widget.QDialog.exec",
            new=capture_preview,
        ),
        patch(
            "src.gui.widgets.llm_generation_widget.QMessageBox.warning"
        ) as mock_warning,
    ):
        widget._on_preview_clicked()

        mock_warning.assert_not_called()
        mock_rag_cls.assert_called_with("dummy.db")
        mock_service.get_context.assert_called_once()
        call_args = mock_service.get_context.call_args
        assert "User {{RAG_CONTEXT}}" in call_args[0][0]
        assert call_args[1]["top_k"] == 2

        display_text = captured["display_text"]
        assert "Verified RAG Context" in display_text
        assert "{{RAG_CONTEXT}}" not in display_text
