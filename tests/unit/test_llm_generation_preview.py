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
    # Setup mock
    mock_service = MagicMock()
    mock_rag_cls.return_value = mock_service
    mock_service.get_context.return_value = "Verified RAG Context"

    # Setup widget
    widget.rag_cb.setChecked(True)
    widget.rag_limit = 2

    # Mock window access
    mock_window = MagicMock()
    mock_window.db_path = "dummy.db"
    widget.window = MagicMock(return_value=mock_window)

    widget.custom_prompt_edit.setPlainText("User {{RAG_CONTEXT}}")

    # Mock Dialog to inspect the prompt passed to it
    with patch("src.gui.widgets.llm_generation_widget.QDialog") as MockDialog:
        # Mock the layout lookup
        mock_dlg_instance = MockDialog.return_value

        # We need to capture the text set on the QLabel/QTextEdit etc.
        # The widget uses QDialog which probably creates a QTextEdit or similar inside.
        # However, since we mock QDialog, the layout logic that creates QTextEdit might not run
        # if it's inside QDialog.__init__ which is mocked.
        # Actually, let's look at _on_preview_clicked in source:
        # It creates a QDialog, adds a layout, then creates a QLabel and a QTextEdit
        # *directly in the method*.

        # So mocking src.gui.widgets.llm_generation_widget.QTextEdit is correct IF it is imported.
        # But if it's imported as "from PySide6.QtWidgets import ..., QTextEdit",
        # then patching the module attribute should work.

        # Wait, if I mock 'src.gui.widgets.llm_generation_widget.QTextEdit',
        # and it says module has no attribute, it means it's NOT imported or not named that way.

        # Checking file content via next tool will confirm.
        # But to be safe, I can patch 'PySide6.QtWidgets.QTextEdit' globally or check header.

        # Let's try patching via PySide6.QtWidgets which is safer if direct import is used
        with patch("PySide6.QtWidgets.QTextEdit") as MockEdit:
            mock_edit_instance = MockEdit.return_value

            # Execute
            widget._on_preview_clicked()

            # Verify RAG Service called
            mock_rag_cls.assert_called_with("dummy.db")
            mock_service.get_context.assert_called_with("User {{RAG_CONTEXT}}", top_k=2)

            # Verify text set on the preview dialog
            # arg[0] of setPlainText
            args, _ = mock_edit_instance.setPlainText.call_args
            display_text = args[0]

            assert "Verified RAG Context" in display_text
            assert "{{RAG_CONTEXT}}" not in display_text


@patch("src.gui.widgets.llm_generation_widget.RAGService")
def test_preview_rag_empty_results(mock_rag_cls, widget, qtbot):
    """Verify preview shows feedback when RAG returns no results."""
    # Setup mock to return empty
    mock_service = MagicMock()
    mock_rag_cls.return_value = mock_service
    mock_service.get_context.return_value = ""

    # Setup widget
    widget.rag_cb.setChecked(True)
    widget.rag_limit = 2

    # Mock window access
    mock_window = MagicMock()
    mock_window.db_path = "dummy.db"
    widget.window = MagicMock(return_value=mock_window)

    widget.custom_prompt_edit.setPlainText("User {{RAG_CONTEXT}}")

    with patch("src.gui.widgets.llm_generation_widget.QDialog"):
        with patch("PySide6.QtWidgets.QTextEdit") as MockEdit:
            mock_edit_instance = MockEdit.return_value

            widget._on_preview_clicked()

            args, _ = mock_edit_instance.setPlainText.call_args
            display_text = args[0]

            assert "(No results found for query)" in display_text
            assert "--- DATA: RAG CONTEXT ---" in display_text
