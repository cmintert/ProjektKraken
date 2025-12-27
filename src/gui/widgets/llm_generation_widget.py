"""
LLM Generation Widget Module.

Provides a compact UI for generating text using configured LLM providers.
Supports streaming output and appending to existing text.
"""

import asyncio
import logging
from typing import Optional

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper

logger = logging.getLogger(__name__)


class GenerationWorker(QThread):
    """
    Worker thread for LLM text generation.

    Runs generation in background to avoid blocking the UI.
    """

    chunk_received = Signal(str)  # Text chunk from streaming
    generation_complete = Signal(str)  # Full generated text
    generation_error = Signal(str)  # Error message

    def __init__(self, provider, prompt: str, max_tokens: int, temperature: float):
        """
        Initialize generation worker.

        Args:
            provider: LLM provider instance.
            prompt: Text prompt for generation.
            max_tokens: Maximum tokens to generate.
            temperature: Temperature parameter (0.0-2.0).
        """
        super().__init__()
        self.provider = provider
        self.prompt = prompt
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._cancelled = False

    def run(self):
        """Run generation in background thread."""
        try:
            # Check if provider supports streaming
            meta = self.provider.metadata()
            if meta.get("supports_streaming", False):
                # Use streaming generation
                self._run_streaming()
            else:
                # Fallback to non-streaming
                self._run_non_streaming()
        except Exception as e:
            logger.error(f"Generation failed: {e}", exc_info=True)
            self.generation_error.emit(str(e))

    def _run_streaming(self):
        """Run streaming generation."""
        try:
            # Create event loop for async operations
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            full_text = ""
            async_gen = self.provider.stream_generate(
                prompt=self.prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            # Iterate through chunks
            async def consume_stream():
                nonlocal full_text
                async for chunk in async_gen:
                    if self._cancelled:
                        break

                    delta = chunk.get("delta", "")
                    if delta:
                        full_text += delta
                        self.chunk_received.emit(delta)

                    if chunk.get("finish_reason"):
                        break

                return full_text

            result = loop.run_until_complete(consume_stream())
            loop.close()

            if not self._cancelled:
                self.generation_complete.emit(result)

        except Exception as e:
            logger.error(f"Streaming generation failed: {e}", exc_info=True)
            self.generation_error.emit(f"Streaming failed: {e}")

    def _run_non_streaming(self):
        """Run non-streaming generation."""
        try:
            result = self.provider.generate(
                prompt=self.prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            if not self._cancelled:
                text = result.get("text", "")
                self.generation_complete.emit(text)

        except Exception as e:
            logger.error(f"Non-streaming generation failed: {e}", exc_info=True)
            self.generation_error.emit(f"Generation failed: {e}")

    def cancel(self):
        """Cancel the generation."""
        self._cancelled = True


class LLMGenerationWidget(QWidget):
    """
    Widget for LLM text generation with streaming output.

    Provides a compact UI below description fields to generate text
    using configured LLM providers.
    """

    text_generated = Signal(str)  # Emitted when generation completes

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize LLM generation widget.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._worker: Optional[GenerationWorker] = None
        self._current_provider = None

        # Main layout
        main_layout = QVBoxLayout(self)
        StyleHelper.apply_compact_spacing(main_layout)

        # Controls row
        controls_layout = QHBoxLayout()

        # Provider selection
        controls_layout.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["LM Studio", "OpenAI", "Google Vertex AI", "Anthropic"])
        self.provider_combo.setToolTip("Select LLM provider for generation")
        controls_layout.addWidget(self.provider_combo)

        # Max tokens
        controls_layout.addWidget(QLabel("Max Tokens:"))
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(50, 4096)
        self.max_tokens_spin.setValue(512)
        self.max_tokens_spin.setToolTip("Maximum tokens to generate")
        controls_layout.addWidget(self.max_tokens_spin)

        # Temperature
        controls_layout.addWidget(QLabel("Temp:"))
        self.temperature_spin = QSpinBox()
        self.temperature_spin.setRange(0, 200)
        self.temperature_spin.setValue(70)
        self.temperature_spin.setSuffix("%")
        self.temperature_spin.setToolTip("Temperature (0-200%, where 100% = 1.0)")
        controls_layout.addWidget(self.temperature_spin)

        # Generate button
        self.generate_btn = QPushButton("Generate")
        self.generate_btn.setToolTip("Generate text and append to description")
        self.generate_btn.clicked.connect(self._on_generate_clicked)
        controls_layout.addWidget(self.generate_btn)

        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setToolTip("Cancel generation")
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        controls_layout.addWidget(self.cancel_btn)

        controls_layout.addStretch()

        main_layout.addLayout(controls_layout)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #95a5a6; font-size: 11px;")
        main_layout.addWidget(self.status_label)

        # Preview area (collapsible)
        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(100)
        self.preview_text.setPlaceholderText("Generated text preview (streaming)...")
        self.preview_text.setVisible(False)
        main_layout.addWidget(self.preview_text)

        # Load settings
        self._load_settings()

    def _load_settings(self):
        """Load provider settings from QSettings."""
        try:
            from PySide6.QtCore import QSettings

            from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

            # Load last used provider
            provider = settings.value("ai_gen_last_provider", "LM Studio")
            index = self.provider_combo.findText(provider)
            if index >= 0:
                self.provider_combo.setCurrentIndex(index)

            # Load generation options
            self.max_tokens_spin.setValue(
                int(settings.value("ai_gen_max_tokens", 512))
            )
            self.temperature_spin.setValue(
                int(settings.value("ai_gen_temperature", 70))
            )

        except Exception as e:
            logger.warning(f"Failed to load generation settings: {e}")

    def _save_settings(self):
        """Save current settings to QSettings."""
        try:
            from PySide6.QtCore import QSettings

            from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            settings.setValue("ai_gen_last_provider", self.provider_combo.currentText())
            settings.setValue("ai_gen_max_tokens", self.max_tokens_spin.value())
            settings.setValue("ai_gen_temperature", self.temperature_spin.value())

        except Exception as e:
            logger.warning(f"Failed to save generation settings: {e}")

    def _get_provider_id(self) -> str:
        """Get provider ID from combo box selection."""
        provider_map = {
            "LM Studio": "lmstudio",
            "OpenAI": "openai",
            "Google Vertex AI": "google",
            "Anthropic": "anthropic",
        }
        return provider_map.get(self.provider_combo.currentText(), "lmstudio")

    def _on_generate_clicked(self):
        """Handle generate button click."""
        # Get context from parent
        context = self._get_generation_context()
        if not context:
            self.status_label.setText("Error: Could not get context for generation")
            return

        # Create prompt
        prompt = self._build_prompt(context)

        # Get temperature as float (0.0-2.0)
        temperature = self.temperature_spin.value() / 100.0

        # Save settings
        self._save_settings()

        try:
            # Create provider
            from src.services.llm_provider import create_provider

            provider_id = self._get_provider_id()
            self._current_provider = create_provider(provider_id)

            # Check provider health
            health = self._current_provider.health_check()
            if health["status"] == "unhealthy":
                self.status_label.setText(f"Error: {health['message']}")
                return

            # Start generation
            self._start_generation(prompt, temperature)

        except Exception as e:
            logger.error(f"Failed to create provider: {e}", exc_info=True)
            self.status_label.setText(f"Error: {str(e)}")

    def _get_generation_context(self) -> Optional[dict]:
        """
        Get context from parent editor for prompt construction.

        Returns:
            dict: Context with name, type, description, etc.
        """
        # Try to get context from parent editor
        parent = self.parent()
        if not parent:
            return None

        context = {}

        # Look for common editor fields
        if hasattr(parent, "name_edit"):
            context["name"] = parent.name_edit.text()

        if hasattr(parent, "type_edit"):
            if isinstance(parent.type_edit, QComboBox):
                context["type"] = parent.type_edit.currentText()
            else:
                context["type"] = parent.type_edit.text()

        if hasattr(parent, "desc_edit"):
            context["existing_description"] = parent.desc_edit.toPlainText()

        return context if context else None

    def _build_prompt(self, context: dict) -> str:
        """
        Build generation prompt from context.

        Args:
            context: Context dictionary with name, type, description, etc.

        Returns:
            str: Generated prompt.
        """
        name = context.get("name", "this item")
        item_type = context.get("type", "item")
        existing = context.get("existing_description", "")

        if existing:
            prompt = f"""Continue the description for {name} (a {item_type}):

Current description:
{existing}

Continue with additional details (do not repeat what's already written):"""
        else:
            prompt = f"""Write a detailed description for {name}, a {item_type} in a fantasy world.

Include vivid details about appearance, history, significance, and any notable characteristics:"""

        return prompt

    def _start_generation(self, prompt: str, temperature: float):
        """Start generation in worker thread."""
        # Update UI
        self.generate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status_label.setText("Generating...")
        self.preview_text.clear()
        self.preview_text.setVisible(True)

        # Create worker
        self._worker = GenerationWorker(
            self._current_provider,
            prompt,
            self.max_tokens_spin.value(),
            temperature,
        )

        # Connect signals
        self._worker.chunk_received.connect(self._on_chunk_received)
        self._worker.generation_complete.connect(self._on_generation_complete)
        self._worker.generation_error.connect(self._on_generation_error)

        # Start worker
        self._worker.start()

    def _on_chunk_received(self, chunk: str):
        """Handle streaming chunk."""
        # Append to preview
        self.preview_text.appendPlainText(chunk)

    def _on_generation_complete(self, text: str):
        """Handle generation completion."""
        self.status_label.setText(f"Generated {len(text)} characters")
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        # Emit signal for parent to handle
        self.text_generated.emit(text)

        # Clean up worker
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    def _on_generation_error(self, error: str):
        """Handle generation error."""
        self.status_label.setText(f"Error: {error}")
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        # Clean up worker
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    def _on_cancel_clicked(self):
        """Handle cancel button click."""
        if self._worker:
            self._worker.cancel()
            self._worker.wait(1000)  # Wait up to 1 second
            self._worker.deleteLater()
            self._worker = None

        self.status_label.setText("Generation cancelled")
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def get_preview_text(self) -> str:
        """
        Get current preview text.

        Returns:
            str: Generated text from preview.
        """
        return self.preview_text.toPlainText()
