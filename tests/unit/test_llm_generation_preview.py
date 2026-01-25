import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QSettings
from src.app.constants import WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP
from src.gui.widgets.llm_generation_widget import LLMGenerationWidget


@pytest.fixture
def widget(qtbot):
    """Fixture for LLMGenerationWidget."""
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.clear()
    widget = LLMGenerationWidget()
    qtbot.addWidget(widget)
    return widget


@patch("src.gui.widgets.llm_generation_widget.RAGService")
def test_preview_rag_success(mock_rag_cls, widget, qtbot):
    """Verify preview works correctly with RAGService."""
    # 1. Setup RAG Mock
    mock_service = MagicMock()
    mock_rag_cls.return_value = mock_service
    mock_service.get_context.return_value = "Verified RAG Context"

    # 2. Setup Widget State
    widget.rag_cb.setChecked(True)
    widget.rag_limit = 2

    # Mock window traversal for db_path
    mock_window = MagicMock()
    mock_window.db_path = "dummy.db"
    widget.window = MagicMock(return_value=mock_window)

    widget.custom_prompt_edit.setPlainText("User {{RAG_CONTEXT}}")

    # 3. Global Patches for Dialog interaction
    # Patch QDialog to prevent exec() blocking
    with patch("PySide6.QtWidgets.QDialog") as MockDialogCls:
        mock_dlg = MockDialogCls.return_value
        mock_dlg.exec.return_value = 0  # Return immediately

        # Patch QPlainTextEdit to capture the text set in the dialog
        with patch("PySide6.QtWidgets.QPlainTextEdit") as MockTextEditCls:
            mock_text_edit = MockTextEditCls.return_value

            # 4. Trigger Action
            widget._on_preview_clicked()

            # 5. Verify RAG interaction
            mock_rag_cls.assert_called_with("dummy.db")
            mock_service.get_context.assert_called_once()
            call_args = mock_service.get_context.call_args
            assert call_args[0][0] == "User {{RAG_CONTEXT}}"
            assert call_args[1]["top_k"] == 2

            # 6. Verify Dialog Content
            # We expect setPlainText to be called on the *newly created* QPlainTextEdit
            # which is our mock_text_edit
            mock_text_edit.setPlainText.assert_called()
            args = mock_text_edit.setPlainText.call_args[0]
            display_text = args[0]

            assert "Verified RAG Context" in display_text
            assert "{{RAG_CONTEXT}}" not in display_text
