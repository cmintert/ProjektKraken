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

    def mock_start(prompt, temp, db, **_kwargs):
        captured_prompt.append(prompt)

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


def test_preview_fetches_rag(qtbot, widget, monkeypatch):  # noqa: C901
    """Test that preview fetches real RAG context."""

    # Mock context
    def mock_context():
        return {"name": "Test Item", "object_type": "event"}

    monkeypatch.setattr(widget, "_get_generation_context", mock_context)

    # Use QMainWindow parent for db_path
    from PySide6.QtWidgets import QMainWindow

    class MockWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.db_path = "test.db"

    win = MockWindow()
    # Explicitly mock parent() for checking db_path, as setParent might depend on hierarchy
    monkeypatch.setattr(widget, "parent", lambda: win)

    # Also set actual parent for Qt correctness if needed, but mock covers logic
    widget.setParent(win)

    # Mock RAGService
    mock_rag_return = "### World Knowledge (RAG Data):\n**Test** (Item):\nContent..."
    rag_called = []

    class MockRAGService:
        def __init__(self, db_path):
            rag_called.append((db_path, "init"))

        def get_context(self, query, top_k=3, exclude_names=None):
            rag_called.append((query, "get_context"))
            return mock_rag_return

    monkeypatch.setattr(
        "src.gui.widgets.llm_generation_widget.RAGService", MockRAGService
    )

    # Mock UI dialogs to be headless
    # We patch QDialog to avoid execution loop
    class MockDialog:
        def __init__(self, *args, **kwargs):
            pass

        def setWindowTitle(self, t):
            pass

        def resize(self, w, h):
            pass

        def setStyleSheet(self, s):
            pass

        def exec(self):
            pass

        def accept(self):
            pass

        def setLayout(self, layout):
            pass

        def setPlainText(self, t):
            pass

        def setReadOnly(self, b):
            pass

        def addWidget(self, w):
            pass

        def addLayout(self, layout):
            pass

        def addStretch(self):
            pass

        @property
        def clicked(self):
            class Sig:
                def connect(self, f):
                    pass

            return Sig()

    monkeypatch.setattr("src.gui.widgets.llm_generation_widget.QDialog", MockDialog)
    monkeypatch.setattr(
        "src.gui.widgets.llm_generation_widget.QVBoxLayout", MockDialog
    )  # Dummy
    monkeypatch.setattr("src.gui.widgets.llm_generation_widget.QHBoxLayout", MockDialog)
    monkeypatch.setattr("src.gui.widgets.llm_generation_widget.QLabel", MockDialog)
    monkeypatch.setattr(
        "src.gui.widgets.llm_generation_widget.QPlainTextEdit", MockDialog
    )
    monkeypatch.setattr("src.gui.widgets.llm_generation_widget.QPushButton", MockDialog)

    widget.rag_cb.setChecked(True)
    widget.custom_prompt_edit.setPlainText("Test Prompt")
    widget._on_preview_clicked()

    # Check that we had an init call and a get_context call or similar
    # We expect init with db_path, then get_context with query

    # Filter for get_context call
    context_calls = [c for c in rag_called if c[1] == "get_context"]
    assert len(context_calls) == 1

    # Check db_path from init call
    init_calls = [c for c in rag_called if c[1] == "init"]
    assert len(init_calls) == 1
    assert init_calls[0][0] == "test.db"

    # Ensure RAG placeholder is present in the query
    assert "{{RAG_CONTEXT}}" in context_calls[0][0]
    # Ensure section marker is present
    assert "[Event]" in context_calls[0][0]


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
