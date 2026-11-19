from unittest.mock import Mock

import pytest

# LLMGenerationWidget imported inside fixture to ensure clean state
from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY


@pytest.fixture
def widget(qtbot):
    # Ensure no settings leak
    from src.gui.widgets.llm_generation_widget import LLMGenerationWidget

    w = LLMGenerationWidget()
    qtbot.addWidget(w)
    return w


def test_preview_dialog_builds_prompt(qtbot, widget, monkeypatch):
    """Test that preview logic builds prompt correctly with placeholder."""

    # Mock context
    def mock_context():
        return {
            "name": "Test Item",
            "type": "Test Type",
            "existing_description": "Desc",
        }

    monkeypatch.setattr(widget, "_get_generation_context", mock_context)

    # Enable RAG
    widget.rag_cb.setChecked(True)
    widget.custom_prompt_edit.setPlainText("Test Prompt")
    pass


def test_custom_prompt_structure(qtbot, widget, monkeypatch):
    """Test custom prompt construction."""

    # Mock context
    def mock_context():
        return {"name": "Test Item", "object_type": "entity"}

    monkeypatch.setattr(widget, "_get_generation_context", mock_context)

    widget.rag_cb.setChecked(True)
    widget.custom_prompt_edit.setPlainText("My custom instruction")

    captured_prompt = []
    captured_kwargs = []

    def mock_start(prompt, temp, db, **kwargs):
        captured_prompt.append(prompt)
        captured_kwargs.append(kwargs)

    monkeypatch.setattr(widget, "_start_generation", mock_start)
    monkeypatch.setattr(widget, "_get_provider_id", lambda: "lmstudio")

    # Mock create_provider
    class MockProvider:
        def health_check(self):
            return {"status": "healthy"}

    monkeypatch.setattr(
        "src.gui.widgets.llm_generation_widget.create_provider",
        lambda pid: MockProvider(),
    )

    widget._on_generate_clicked()

    assert len(captured_prompt) == 1
    prompt = captured_prompt[0]

    # Prompt can be dict (chat) or string (legacy)
    if isinstance(prompt, dict):
        # Flatten values to search
        prompt_text = str(prompt)
    else:
        prompt_text = prompt

    assert "My custom instruction" in prompt_text
    # New compact section markers
    assert "[Entity]" in prompt_text
    # RAG context is a placeholder at this stage (before worker)
    assert "{{RAG_CONTEXT}}" in prompt_text
    assert "[Task]" in prompt_text
    assert captured_kwargs[0]["retrieval_query"] == (
        "My custom instruction\nSubject: entity Test Item"
    )


def test_preview_fetches_rag(qtbot, widget, monkeypatch):
    """An Event preview displays context retrieved for its task and subject."""
    from PySide6.QtWidgets import QDialog

    context = {"name": "Test Item", "object_type": "event", "object_id": "event-id"}
    monkeypatch.setattr(widget, "_get_generation_context", lambda: context)
    monkeypatch.setattr(widget, "_resolve_db_path", lambda: "test.db")
    rag = Mock()
    rag.return_value.get_context.return_value = "Retrieved lore for the preview"
    rag.return_value.source_references = ()
    monkeypatch.setattr("src.services.generation_worker.RAGService", rag)

    widget.world_context_cb.setChecked(False)
    widget.spatial_cb.setChecked(False)
    widget.undated_cb.setChecked(True)
    widget.rag_cb.setChecked(True)
    widget.rag_limit_input.setText("2")
    widget.custom_prompt_edit.setPlainText("Test Prompt")

    def capture_preview(dialog):
        qtbot.waitUntil(lambda: widget._prepared_request is not None)
        assert "Retrieved lore for the preview" in dialog.text.toPlainText()
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", capture_preview)
    widget._on_preview_clicked()

    rag.assert_called_once_with("test.db")
    rag.return_value.get_context.assert_called_once_with(
        "Test Prompt\nSubject: event Test Item",
        top_k=2,
        exclude_object=("event", "event-id"),
    )


def test_default_system_prompt_fallback(qtbot, widget, monkeypatch):
    """Test that default system prompt is used when settings are empty."""
    # Ensure empty settings
    from PySide6.QtCore import QSettings

    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.remove("ai_gen_system_prompt")
    settings.remove("ai_gen_system_prompt_template_id")

    # It should strictly look at settings, so if missing, it falls back to default.
    result = widget._get_system_prompt()
    assert (
        "world-builder" in result.lower()
        or "fantasy" in result.lower()
        or "assistant" in result.lower()
    )


# test_template_loading_fallback_on_error is removed because
# the widget no longer attempts to load system prompts from templates.
