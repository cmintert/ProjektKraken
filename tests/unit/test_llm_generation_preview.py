from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QPlainTextEdit

from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.gui.widgets.llm_generation_widget import GenerationWorker, LLMGenerationWidget
from src.services.prompt_builder import PromptBuilder, build_retrieval_query


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
    _assert_preview_rag_success(mock_rag_cls, widget, world_context_enabled=False)


@patch("src.gui.widgets.llm_generation_widget.RAGService")
def test_preview_rag_with_world_context(mock_rag_cls, widget):
    _assert_preview_rag_success(mock_rag_cls, widget, world_context_enabled=True)


def _assert_preview_rag_success(mock_rag_cls, widget, world_context_enabled):
    # 1. Setup RAG Mock
    mock_service = MagicMock()
    mock_rag_cls.return_value = mock_service
    mock_service.get_context.return_value = "Verified RAG Context"

    # 2. Setup Widget State
    widget.rag_cb.setChecked(True)
    widget.rag_limit_input.setText("2")
    widget.world_context_cb.setChecked(world_context_enabled)
    widget._get_generation_context = MagicMock(
        return_value={
            "name": "Northwatch",
            "type": "Character",
            "object_type": "entity",
            "object_id": "northwatch-id",
            "existing_description": "Unrelated manuscript prose. " * 40,
        }
    )

    # Mock window traversal for db_path
    mock_window = MagicMock()
    mock_window.db_path = "dummy.db"
    widget.window = MagicMock(return_value=mock_window)

    widget.custom_prompt_edit.setPlainText(
        "Find past conflicts with {name} {{RAG_CONTEXT}}"
    )

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
        patch.object(
            widget,
            "_preview_authoring_context",
            return_value="[Authoritative Context]\nKnown fact",
        ),
    ):
        widget._on_preview_clicked()

        mock_warning.assert_not_called()
        mock_rag_cls.assert_called_with("dummy.db")
        mock_service.get_context.assert_called_once()
        call_args = mock_service.get_context.call_args
        assert call_args.args[0] == (
            "Find past conflicts with Northwatch\nSubject: entity Northwatch"
        )
        assert call_args.kwargs == {
            "top_k": 2,
            "exclude_object": ("entity", "northwatch-id"),
        }

        display_text = captured["display_text"]
        assert "Verified RAG Context" in display_text
        assert "{{RAG_CONTEXT}}" not in display_text
        assert ("[Authoritative Context]" in display_text) == world_context_enabled


@patch("src.gui.widgets.llm_generation_widget.RAGService")
@pytest.mark.parametrize("rag_enabled,rag_limit", [(False, "2"), (True, "0")])
def test_preview_skips_retrieval_when_disabled_or_zero(
    mock_rag_cls, widget, rag_enabled, rag_limit
):
    widget.rag_cb.setChecked(rag_enabled)
    widget.rag_limit_input.setText(rag_limit)
    widget.custom_prompt_edit.setPlainText("Find conflicts")
    widget._get_generation_context = MagicMock(
        return_value={"name": "Northwatch", "object_type": "entity"}
    )
    widget._resolve_db_path = MagicMock(return_value="dummy.db")

    with patch("src.gui.widgets.llm_generation_widget.QDialog.exec", return_value=0):
        widget._on_preview_clicked()

    mock_rag_cls.assert_not_called()


@patch("src.gui.widgets.llm_generation_widget.RAGService")
def test_preview_and_generation_use_identical_retrieval_arguments(mock_rag_cls, widget):
    context = {
        "name": "Northwatch",
        "object_id": "northwatch-id",
        "object_type": "entity",
        "existing_description": "Unrelated manuscript prose. " * 40,
    }
    widget._get_generation_context = MagicMock(return_value=context)
    widget._resolve_db_path = MagicMock(return_value="dummy.db")
    widget.rag_cb.setChecked(True)
    widget.rag_limit_input.setText("2")
    widget.custom_prompt_edit.setPlainText("Find past conflicts with {name}")
    mock_rag_cls.return_value.get_context.return_value = "Relevant conflict"

    with patch("src.gui.widgets.llm_generation_widget.QDialog.exec", return_value=0):
        widget._on_preview_clicked()
    preview_call = mock_rag_cls.return_value.get_context.call_args

    builder = PromptBuilder()
    task = builder.substitute_variables(
        widget.custom_prompt_edit.toPlainText(), context
    )
    prompt = builder.construct_prompt(
        builder.build_context_string(context), task, include_rag_placeholder=True
    )
    widget._current_provider = MagicMock()
    with patch.object(GenerationWorker, "start"):
        widget._start_generation(
            prompt,
            0.7,
            "dummy.db",
            object_id=context["object_id"],
            object_type=context["object_type"],
            retrieval_query=build_retrieval_query(task, context),
        )
    worker = widget._worker
    assert worker is not None
    worker._apply_rag_to_prompt()

    assert preview_call == mock_rag_cls.return_value.get_context.call_args
    assert worker.prompt["user"].count("Relevant conflict") == 1
