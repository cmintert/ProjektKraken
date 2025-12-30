from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QSettings

from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.gui.widgets.llm_generation_widget import LLMGenerationWidget


@pytest.fixture
def clean_settings():
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.clear()
    yield
    settings.clear()


@pytest.fixture
def widget(qtbot, clean_settings):
    widget = LLMGenerationWidget()
    qtbot.addWidget(widget)
    # widget.show()  # Ensure widget is shown for visibility tests
    return widget


def test_initial_state(widget):
    """Test initial state of the widget."""
    assert widget.generate_btn.isEnabled()
    assert not widget.cancel_btn.isEnabled()
    assert not widget.custom_prompt_edit.isHidden()
    assert widget.rag_cb.isChecked() is True  # RAG defaults to True


@patch("src.gui.widgets.llm_generation_widget.create_provider")
def test_generation_flow_custom_prompt(mock_create_provider, widget, qtbot):
    """Test generation with a custom prompt."""
    # Setup mock provider
    mock_provider = MagicMock()
    mock_provider = MagicMock()
    mock_provider.health_check.return_value = {"status": "healthy"}
    mock_provider.metadata.return_value = {"supports_streaming": True}

    # Mock stream_generate as async generator
    async def mock_stream():
        yield {"delta": "Generated text"}

    mock_provider.stream_generate.return_value = mock_stream()
    mock_create_provider.return_value = mock_provider

    # Configure widget
    widget.custom_prompt_edit.setPlainText("Custom prompt")
    widget.rag_cb.setChecked(False)  # Disable RAG to avoid db lookup

    # Mock context
    with patch.object(widget, "_get_generation_context") as mock_ctx:
        mock_ctx.return_value = {"name": "Test", "type": "Item"}

        # Trigger generation
        with qtbot.waitSignal(widget.text_generated, timeout=5000):
            widget.generate_btn.click()

    # Verify provider was called
    # After generation completes:
    # Cancel button should be disabled
    assert not widget.cancel_btn.isEnabled()
    # Generate button should be re-enabled
    assert widget.generate_btn.isEnabled()


def test_empty_custom_prompt_error(widget):
    """Test error when custom prompt is enabled but empty."""
    # Mock context retrieval to pass the first check
    with patch.object(widget, "_get_generation_context") as mock_ctx:
        mock_ctx.return_value = {"name": "Test"}

        widget.custom_prompt_edit.setPlainText("")

        widget.generate_btn.click()

        assert "empty" in widget.status_label.text().lower()


@patch("src.services.llm_provider.get_provider_settings_from_qsettings")
def test_settings_usage(mock_get_settings, widget):
    """Verify widget attempts to load settings correctly."""
    # This tests the _get_provider_id logic implicitly if we had more providers
    # For now just verify it defaults correctly
    assert widget._get_provider_id() == "lmstudio"
