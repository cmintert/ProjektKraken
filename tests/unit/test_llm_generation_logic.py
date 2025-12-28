import pytest

from src.gui.widgets.llm_generation_widget import LLMGenerationWidget


@pytest.fixture
def widget(qtbot):
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

    # We can't easily test the dialog popping up without blocking, but we can verify
    # the logic by inspecting what _build_prompt returns, which preview uses.
    prompt = widget._build_prompt(mock_context(), use_rag=True)

    assert "{{RAG_CONTEXT}}" in prompt
    assert "### Item Context" in prompt
    assert "Test Item" in prompt


def test_custom_prompt_structure(qtbot, widget, monkeypatch):
    """Test custom prompt construction."""

    # Mock context
    def mock_context():
        return {"name": "Test Item"}

    monkeypatch.setattr(widget, "_get_generation_context", mock_context)

    widget.rag_cb.setChecked(True)
    widget.use_custom_prompt_cb.setChecked(True)
    widget.custom_prompt_edit.setPlainText("My custom instruction")

    # We need to access the logic inside _on_preview_clicked or _on_generate_clicked.
    # Since we duplicated logic in _on_preview_clicked, let's verify _on_generate_clicked logic
    # by mocking _start_generation to capture the prompt.

    captured_prompt = []

    def mock_start(prompt, temp, db):
        captured_prompt.append(prompt)

    monkeypatch.setattr(widget, "_start_generation", mock_start)
    monkeypatch.setattr(widget, "_get_provider_id", lambda: "lmstudio")

    # Mock create_provider to avoid actual init
    class MockProvider:
        def health_check(self):
            return {"status": "healthy"}

    monkeypatch.setattr(
        "src.services.llm_provider.create_provider", lambda pid: MockProvider()
    )

    widget._on_generate_clicked()

    assert len(captured_prompt) == 1
    prompt = captured_prompt[0]

    assert "My custom instruction" in prompt
    assert "{{RAG_CONTEXT}}" in prompt
    assert "You are an expert fantasy world-builder" in prompt  # System persona check


def test_preview_fetches_rag(qtbot, widget, monkeypatch):
    """Test that preview fetches real RAG context."""

    # Mock context
    def mock_context():
        return {"name": "Test Item"}

    monkeypatch.setattr(widget, "_get_generation_context", mock_context)

    # Mock window db_path
    class MockWindow:
        db_path = "test.db"

    monkeypatch.setattr(widget, "window", lambda: MockWindow())

    # Mock perform_rag_search
    mock_rag_return = "### World Knowledge (RAG Data):\n**Test** (Item):\nContent..."
    rag_called = []

    def mock_search(prompt, db_path):
        rag_called.append((prompt, db_path))
        return mock_rag_return

    monkeypatch.setattr(
        "src.gui.widgets.llm_generation_widget.perform_rag_search", mock_search
    )

    # Mock QDialog to avoid blocking
    class MockDialog:
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

    monkeypatch.setattr("PySide6.QtWidgets.QDialog", MockDialog)
    # Mock QVBoxLayout/QLabel/etc if strictly needed.
    # Current code passes `self` or `dlg` as parent.
    # With mocked QDialog, children instantiations might fail if C++ binding checks types.
    # But usually PySide6 mocks allow this if not strictly typed in C++.
    monkeypatch.setattr("PySide6.QtWidgets.QDialog.exec", lambda self: None)

    widget.rag_cb.setChecked(True)
    widget._on_preview_clicked()

    assert len(rag_called) == 1
    assert rag_called[0][1] == "test.db"
    # Prompt passed to search should be the template before replacement
    assert "{{RAG_CONTEXT}}" in rag_called[0][0]
