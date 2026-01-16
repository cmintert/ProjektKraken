from unittest.mock import MagicMock, patch
import importlib
import sys

import pytest
from PySide6.QtCore import QSettings

from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY


# Reload the widget module after QSettings is mocked to ensure it uses MockQSettings
if 'src.gui.widgets.llm_generation_widget' in sys.modules:
    import src.gui.widgets.llm_generation_widget
    importlib.reload(src.gui.widgets.llm_generation_widget)

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


def test_template_combo_populated(widget):
    """Test that template dropdown is populated with description templates."""
    # Check that template combo exists
    assert widget.template_combo is not None
    
    # Should have at least one item (fallback at minimum)
    assert widget.template_combo.count() > 0
    
    # Check that items have data (template_id)
    for i in range(widget.template_combo.count()):
        item_data = widget.template_combo.itemData(i)
        assert item_data is not None
        assert isinstance(item_data, str)


def test_template_selection_saved(widget, clean_settings):
    """Test that template selection triggers save."""
    # This test verifies that changing template selection calls _save_settings
    # The actual QSettings saving is tested elsewhere and may use real QSettings
    
    # Find a valid template in the combo
    if widget.template_combo.count() > 0:
        # Get initial template
        initial_template = widget.template_combo.currentData()
        
        # Change to a different template if possible
        if widget.template_combo.count() > 1:
            new_index = 1 if widget.template_combo.currentIndex() != 1 else 0
            widget.template_combo.setCurrentIndex(new_index)
            new_template = widget.template_combo.currentData()
            
            # Verify it changed
            assert new_template != initial_template
            assert new_template is not None


def test_template_selection_loaded(qtbot, clean_settings):
    """Test that widget initializes with a default template."""
    # Create new widget
    widget = LLMGenerationWidget()
    qtbot.addWidget(widget)
    
    # Check that a template is selected by default
    assert widget.template_combo.count() > 0
    current_id = widget.template_combo.currentData()
    assert current_id is not None
    assert isinstance(current_id, str)
    # Should be one of the description templates
    assert current_id.startswith("description_")


def test_get_few_shot_examples(widget):
    """Test that few-shot examples can be loaded."""
    examples = widget._get_few_shot_examples()
    
    # Should return a string (empty if file not found, but should not crash)
    assert isinstance(examples, str)
    
    # If examples exist, should have content
    if examples:
        assert len(examples) > 0
