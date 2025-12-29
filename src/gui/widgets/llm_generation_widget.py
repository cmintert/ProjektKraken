"""
LLM Generation Widget Module.

Provides a compact UI for generating text using configured LLM providers.
Supports streaming output and appending to existing text.
"""

import asyncio
import logging
from typing import Any, Optional, Protocol, runtime_checkable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper

logger = logging.getLogger(__name__)

# Default system prompt used for LLM content generation
# This defines the LLM's role, tone, and behavior for worldbuilding tasks.
# Can be customized via Settings → AI Settings → Text Generation tab.
# Stored in QSettings under key 'ai_gen_system_prompt'.
DEFAULT_SYSTEM_PROMPT = (
    "You are an expert fantasy world-builder assisting a user in creating a "
    "rich and immersive setting. Your tone is descriptive, evocative, and "
    "consistent with high-fantasy literature.\n\n"
    "IMPORTANT: Time in this world is represented as floating-point numbers "
    "where 1.0 = 1 day. The decimal portion represents time within the day "
    "(e.g., 0.5 = noon). When referencing dates or durations, understand "
    "that event dates and durations use this numeric format."
)


@runtime_checkable
class ContextProvider(Protocol):
    """Protocol for widgets that provide context for LLM generation."""

    def get_generation_context(self) -> dict:
        """Return context dictionary for generation."""
        ...


def perform_rag_search(prompt: str, db_path: Optional[str], top_k: int = 3) -> str:
    """
    Perform RAG search using search service.

    Args:
        prompt: The prompt text to query with.
        db_path: Path to the database.
        top_k: Number of context items to retrieve.

    Returns:
        str: Formatted context string or empty string.
    """
    if not db_path:
        logger.debug("RAG skipped: No db_path provided.")
        return ""

    try:
        logger.debug(f"Starting RAG search in {db_path} for prompt: {prompt[:50]}...")
        import sqlite3

        from src.services.search_service import create_search_service

        # Create strictly local read connection
        conn = sqlite3.connect(
            db_path,
            check_same_thread=False,  # Can be called from any thread
        )
        conn.row_factory = sqlite3.Row

        # Create search service - reuses the provider config logic
        # Use 'lmstudio' or configured provider - ideally we use the same as current
        # but search service factory can handle defaults
        search_service = create_search_service(conn)

        # Query
        # Extract main topic from prompt? Or just use full prompt
        # For now, use first 100 chars or full prompt
        query_text = prompt[:200]
        results = search_service.query(query_text, top_k=top_k)

        conn.close()

        if not results:
            logger.debug("RAG search returned no results.")
            return ""

        logger.info(f"RAG search found {len(results)} relevant items.")

        # Format results - exclude tags and attributes, only include core info
        # This keeps prompts focused on narrative descriptions rather than
        # technical metadata, reducing token usage and improving relevance.
        context_parts = ["### World Knowledge (RAG Data):"]
        for r in results:
            name = r.get("name", "Unknown")
            rtype = r.get("type", "Unknown")

            # Extract description from the indexed text
            # Format: "Name: X\nType: Y\nTags: ...\nDescription: ..."
            # We parse to extract ONLY the description for cleaner context
            full_text = r.get("text_content", "")

            # Parse to extract only description
            description = ""
            if full_text:
                lines = full_text.split("\n\n")
                for line in lines:
                    if line.startswith("Description: "):
                        description = line.replace("Description: ", "", 1).strip()
                        break

            # Fallback to metadata if no description found
            if not description:
                description = r.get("metadata", {}).get("description", "")

            # Skip if still no meaningful content
            if not description or len(description) < 20:
                continue

            # Truncate long descriptions
            truncated_description = description[:2000]
            if len(description) > 2000:
                truncated_description += "..."

            # Format: Name (Type): Description only
            context_parts.append(f"**{name}** ({rtype}):\\n{truncated_description}")

        return "\n\n".join(context_parts) + "\n\n"

    except Exception as e:
        logger.error(f"RAG search failed: {e}", exc_info=True)
        return ""


class GenerationWorker(QThread):
    """
    Worker thread for LLM text generation.

    Runs generation in background to avoid blocking the UI.
    """

    # chunk_received = Signal(str)  # Removed as per user request
    generation_complete = Signal(str)  # Full generated text
    generation_error = Signal(str)  # Error message

    def __init__(
        self,
        provider: Any,
        prompt: str,
        max_tokens: int,
        temperature: float,
        db_path: Optional[str] = None,
        rag_limit: int = 3,
    ) -> None:
        """
        Initialize generation worker.

        Args:
            provider: LLM provider instance.
            prompt: Text prompt for generation.
            max_tokens: Maximum tokens to generate.
            temperature: Temperature parameter (0.0-2.0).
            db_path: Optional path to database for RAG context.
            rag_limit: Number of RAG items to retrieve.
        """
        super().__init__()
        self.provider = provider
        self.prompt = prompt
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.db_path = db_path
        self.rag_limit = rag_limit
        self._cancelled = False

    def _perform_rag_search(self) -> str:
        """
        Perform RAG search if db_path is set.
        Returns formatted context string or empty string.
        """
        return perform_rag_search(self.prompt, self.db_path, self.rag_limit)

    def run(self) -> None:
        """Run generation in background thread."""
        try:
            # 1. Perform RAG if enabled (synchronous in this thread)
            rag_context = self._perform_rag_search()

            # Replace placeholder if present
            if "{{RAG_CONTEXT}}" in self.prompt:
                self.prompt = self.prompt.replace("{{RAG_CONTEXT}}", rag_context)
            elif rag_context:
                # Fallback for legacy behavior (prepend)
                logger.info("RAG Context found but no placeholder. Prepending.")
                self.prompt = rag_context + self.prompt

            if rag_context:
                logger.debug(f"Final Prompt with RAG:\n{self.prompt}")

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

    def _run_streaming(self) -> None:
        """Run streaming generation."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def generate() -> str:
                full_text = ""
                async for chunk in self.provider.stream_generate(
                    self.prompt,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                ):
                    delta = chunk.get("delta", "")
                    # We no longer emit chunk_received
                    full_text += delta
                return full_text

            result = loop.run_until_complete(generate())
            loop.close()

            if not self._cancelled:
                self.generation_complete.emit(result)

        except Exception as e:
            logger.error(f"Streaming generation failed: {e}", exc_info=True)
            self.generation_error.emit(f"Streaming failed: {e}")

    def _run_non_streaming(self) -> None:
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

    def cancel(self) -> None:
        """Cancel the generation."""
        self._cancelled = True


class LLMGenerationWidget(QWidget):
    """
    Widget for LLM text generation with streaming output.

    Provides a compact UI below description fields to generate text
    using configured LLM providers.
    """

    text_generated = Signal(str)  # Emitted when generation completes

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        context_provider: Optional[ContextProvider] = None,
    ) -> None:
        """
        Initialize LLM generation widget.

        Args:
            parent: Parent widget.
            context_provider: Optional provider for generation context.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._worker: Optional[GenerationWorker] = None
        self._current_provider = None
        self._context_provider = context_provider

        # Main layout
        main_layout = QVBoxLayout(self)
        StyleHelper.apply_compact_spacing(main_layout)

        # Controls row
        controls_layout = QHBoxLayout()

        # Provider selection
        controls_layout.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(
            ["LM Studio", "OpenAI", "Google Vertex AI", "Anthropic"]
        )
        self.provider_combo.setToolTip("Select LLM provider for generation")
        self.provider_combo.currentIndexChanged.connect(self._save_settings)
        controls_layout.addWidget(self.provider_combo)

        # Max tokens
        controls_layout.addWidget(QLabel("Max Tokens:"))
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(50, 4096)
        self.max_tokens_spin.setValue(512)
        self.max_tokens_spin.setToolTip("Maximum tokens to generate")
        self.max_tokens_spin.valueChanged.connect(self._save_settings)
        controls_layout.addWidget(self.max_tokens_spin)

        # Temperature
        controls_layout.addWidget(QLabel("Temp:"))
        self.temperature_spin = QSpinBox()
        self.temperature_spin.setRange(0, 200)
        self.temperature_spin.setValue(70)
        self.temperature_spin.setSuffix("%")
        self.temperature_spin.setToolTip("Temperature (0-200%, where 100% = 1.0)")
        self.temperature_spin.valueChanged.connect(self._save_settings)
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

        # Preview button
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setToolTip("Preview the prompt before generating")
        self.preview_btn.clicked.connect(self._on_preview_clicked)
        controls_layout.addWidget(self.preview_btn)

        controls_layout.addStretch()

        main_layout.addLayout(controls_layout)

        # Custom prompt section
        prompt_layout = (
            QHBoxLayout()
        )  # Renamed from prompt_header_layout to prompt_layout
        self.use_custom_prompt_cb = QCheckBox("Use Custom Prompt")
        self.use_custom_prompt_cb.setToolTip(
            "Check to use a custom prompt instead of auto-generated one"
        )
        self.use_custom_prompt_cb.stateChanged.connect(
            self._on_custom_prompt_toggled
        )  # Changed signal to stateChanged
        prompt_layout.addWidget(self.use_custom_prompt_cb)

        # RAG Context Checkbox
        self.rag_cb = QCheckBox("Use RAG Context")
        self.rag_cb.setChecked(True)
        self.rag_cb.setToolTip("Include relevant context from database (RAG)")
        prompt_layout.addWidget(self.rag_cb)

        # RAG Limit Input
        self.rag_limit_input = QLineEdit()
        self.rag_limit_input.setPlaceholderText("3")
        self.rag_limit_input.setToolTip("Number of context items to retrieve (1-20)")
        self.rag_limit_input.setFixedWidth(50)
        self.rag_limit_input.setValidator(QIntValidator(1, 20))
        self.rag_limit_input.setText("3")

        # Handle toggling with check box
        self.rag_cb.toggled.connect(self.rag_limit_input.setVisible)
        self.rag_cb.toggled.connect(self._save_settings)
        self.rag_limit_input.editingFinished.connect(self._save_settings)
        prompt_layout.addWidget(self.rag_limit_input)

        prompt_layout.addStretch()  # Added stretch to prompt_layout
        main_layout.addLayout(prompt_layout)  # Added prompt_layout to main_layout

        # Custom prompt input
        self.custom_prompt_edit = QPlainTextEdit()
        self.custom_prompt_edit.setStyleSheet(StyleHelper.get_input_field_style())
        self.custom_prompt_edit.setPlaceholderText(
            "Enter your custom prompt here...\n\n"
            "Example: 'Write a mysterious backstory for this character' or "
            "'Describe this location in vivid detail'"
        )
        self.custom_prompt_edit.setMaximumHeight(80)
        self.custom_prompt_edit.setVisible(False)  # Hidden by default
        main_layout.addWidget(self.custom_prompt_edit)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #95a5a6; font-size: 11px;")
        main_layout.addWidget(self.status_label)

        # Preview area removed as per user request
        # self.preview_text = QPlainTextEdit()
        # ...

        # Load settings
        self._load_settings()

    def _load_settings(self) -> None:
        """Load provider settings from QSettings."""
        try:
            from PySide6.QtCore import QSettings

            from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

            # Load last used provider
            self.provider_combo.blockSignals(True)
            provider = settings.value("ai_gen_last_provider", "LM Studio")
            index = self.provider_combo.findText(provider)
            if index >= 0:
                self.provider_combo.setCurrentIndex(index)
            self.provider_combo.blockSignals(False)

            # Load generation options
            self.max_tokens_spin.blockSignals(True)
            self.max_tokens_spin.setValue(int(settings.value("ai_gen_max_tokens", 512)))
            self.max_tokens_spin.blockSignals(False)

            self.temperature_spin.blockSignals(True)
            self.temperature_spin.setValue(
                int(settings.value("ai_gen_temperature", 70))
            )
            self.temperature_spin.blockSignals(False)

            # Load RAG settings
            self.rag_cb.blockSignals(True)
            self.rag_cb.setChecked(
                settings.value("ai_gen_rag_enabled", True, type=bool)
            )
            self.rag_cb.blockSignals(False)

            # rag_limit_input only saves on editingFinished, but for consistency:
            self.rag_limit_input.blockSignals(True)
            limit = str(settings.value("ai_gen_rag_limit", 3))
            self.rag_limit_input.setText(limit)
            self.rag_limit_input.setVisible(self.rag_cb.isChecked())
            self.rag_limit_input.blockSignals(False)

        except Exception as e:
            logger.warning(f"Failed to load generation settings: {e}")

    def _save_settings(self) -> None:
        """Save current settings to QSettings."""
        try:
            from PySide6.QtCore import QSettings

            from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            settings.setValue("ai_gen_last_provider", self.provider_combo.currentText())
            settings.setValue("ai_gen_max_tokens", self.max_tokens_spin.value())
            settings.setValue("ai_gen_temperature", self.temperature_spin.value())
            settings.setValue("ai_gen_rag_enabled", self.rag_cb.isChecked())

            # Make sure to save a valid integer
            try:
                limit_val = int(self.rag_limit_input.text())
            except ValueError:
                limit_val = 3
            settings.setValue("ai_gen_rag_limit", limit_val)

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

    def _on_generate_clicked(self) -> None:
        """Handle generate button click."""
        print("DEBUG: Generate button clicked")  # Direct stdout debug
        logger.warning("DEBUG: Generate button clicked")

        logger.debug("Generate clicked.")
        # Get context from parent (Entity/Event)
        context = self._get_generation_context()
        if not context:
            logger.warning("Generation aborted: No context found.")
            self.status_label.setText("Error: Could not get context for generation")
            return

        logger.debug(f"Generation context retrieved: {context.keys()}")

        # Check if using custom prompt
        if self.use_custom_prompt_cb.isChecked():
            user_prompt = self.custom_prompt_edit.toPlainText().strip()
            if not user_prompt:
                self.status_label.setText("Error: Custom prompt is empty")
                return

            # Construct composite prompt with context + user instruction
            # Build context string dynamically from available fields
            context_lines = []

            # Order matters for readability
            if "name" in context:
                context_lines.append(f"Name: {context['name']}")
            if "type" in context:
                context_lines.append(f"Type: {context['type']}")
            if "lore_date" in context:
                context_lines.append(f"Lore Date: {context['lore_date']}")
            if "existing_description" in context:
                context_lines.append(f"Description: {context['existing_description']}")

            # Fallback for any other keys
            for k, v in context.items():
                if k not in [
                    "name",
                    "type",
                    "lore_date",
                    "existing_description",
                    "description",
                ]:
                    context_lines.append(f"{k.replace('_', ' ').title()}: {v}")

            context_str = "\n".join(context_lines)

            system_persona = self._get_system_prompt()

            # Insert placeholder for RAG
            rag_placeholder = "{{RAG_CONTEXT}}" if self.rag_cb.isChecked() else ""

            prompt = (
                f"{system_persona}\n\n"
                f"{rag_placeholder}"
                f"Context:\n{context_str}\n\n"
                f"Task: {user_prompt}"
            )
            self.status_label.setText("Using custom prompt with context...")
        else:
            # Create auto-generated prompt
            prompt = self._build_prompt(context, self.rag_cb.isChecked())
            self.status_label.setText("Using auto-generated prompt...")

        # Get temperature as float (0.0-2.0)
        temperature = self.temperature_spin.value() / 100.0

        # Determine DB path for RAG if enabled
        db_path = None
        if self.rag_cb.isChecked():
            # Attempt to get db_path from main window via parent chain
            # Parent is EntityEditor -> SplitterTabInspector -> ... -> MainWindow?
            # Safer to traverse up to find window
            window = self.window()
            if hasattr(window, "db_path"):
                db_path = window.db_path
                logger.debug(f"RAG enabled. Using DB: {db_path}")
            else:
                logger.warning("RAG enabled but could not find db_path on window.")

        # Save settings
        self._save_settings()

        try:
            # Create provider
            from src.services.llm_provider import create_provider

            provider_id = self._get_provider_id()
            logger.info(f"Creating LLM provider: {provider_id}")
            self._current_provider = create_provider(provider_id)

            # Check provider health
            health = self._current_provider.health_check()
            if health["status"] == "unhealthy":
                logger.error(f"Provider health check failed: {health['message']}")
                self.status_label.setText(f"Error: {health['message']}")
                return

            # Start generation
            logger.info(f"Starting generation with prompt length: {len(prompt)}")
            logger.info(f"Full Prompt (Pre-RAG):\n{prompt}")
            self._start_generation(prompt, temperature, db_path)

        except Exception as e:
            logger.error(f"Failed to create provider: {e}", exc_info=True)
            self.status_label.setText(f"Error: {str(e)}")

    def _on_custom_prompt_toggled(self, checked: bool) -> None:
        """Handle custom prompt checkbox toggle."""
        self.custom_prompt_edit.setVisible(checked)
        if checked:
            self.custom_prompt_edit.setFocus()

    def _get_system_prompt(self) -> str:
        """
        Get the system prompt from settings.

        Loads the user's custom system prompt from QSettings if available,
        otherwise falls back to DEFAULT_SYSTEM_PROMPT. The system prompt
        defines the LLM's role, tone, and behavior.

        The prompt can be customized via:
        Settings → AI Settings → Text Generation tab → System Prompt field

        Returns:
            str: The configured system prompt, or default if not set.
        """
        try:
            from PySide6.QtCore import QSettings

            from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            return settings.value("ai_gen_system_prompt", DEFAULT_SYSTEM_PROMPT)
        except Exception as e:
            logger.warning(f"Failed to load system prompt: {e}")
            return DEFAULT_SYSTEM_PROMPT

    def _get_generation_context(self) -> Optional[dict]:
        """
        Get context from provider or parent editor for prompt construction.

        Returns:
            dict: Context with name, type, description, etc.
        """
        # 1. Try explicit provider
        if self._context_provider:
            return self._context_provider.get_generation_context()

        # 2. Fallback: Traverse up hierarchy (Legacy support)
        context = {}
        current = self.parent()
        max_depth = 10  # Prevent infinite loops
        depth = 0
        found_editor = False

        while current and depth < max_depth:
            # Check if this widget looks like an editor
            if hasattr(current, "name_edit"):
                found_editor = True
                context["name"] = current.name_edit.text()

                if hasattr(current, "type_edit"):
                    if isinstance(current.type_edit, QComboBox):
                        context["type"] = current.type_edit.currentText()
                    else:
                        context["type"] = current.type_edit.text()

                if hasattr(current, "desc_edit"):
                    context["existing_description"] = current.desc_edit.toPlainText()

                # Check for Lore Date (EventEditor specific)
                if hasattr(current, "date_edit"):
                    # Try to get formatted text from preview label
                    if hasattr(current.date_edit, "lbl_preview"):
                        text = current.date_edit.lbl_preview.text()
                        if text:
                            context["lore_date"] = text

                # Found the editor, stop traversing
                break

            # Move up
            current = current.parent()
            depth += 1

        return context if found_editor else None

    def _build_prompt(self, context: dict, use_rag: bool = False) -> str:
        """
        Build generation prompt from context.

        Args:
            context: Context dictionary with name, type, description, etc.
            use_rag: Whether to include RAG placeholder.

        Returns:
            str: Generated prompt.
        """
        name = context.get("name", "this item")
        item_type = context.get("type", "item")
        existing = context.get("existing_description", "")

        system_persona = self._get_system_prompt()

        rag_placeholder = "{{RAG_CONTEXT}}" if use_rag else ""

        base_context = f"### Item Context\n**Name:** {name}\n**Type:** {item_type}\n"

        if existing:
            prompt = (
                f"{system_persona}\n\n"
                f"{rag_placeholder}"
                f"{base_context}"
                f"**Current Description:**\n{existing}\n\n"
                f"### Task\n"
                f"Continue the description above. Add depth, sensory details, and "
                f"narrative significance. Do NOT repeat what is already written. "
                f"Maintain the existing style and flow."
            )
        else:
            prompt = (
                f"{system_persona}\n\n"
                f"{rag_placeholder}"
                f"{base_context}\n"
                f"### Task\n"
                f"Write a comprehensive description for this {item_type}. "
                f"Include vivid details about its appearance, history, purpose, "
                f"and significance to the world. Make it feel alive and grounded."
            )

        return prompt

    def _start_generation(
        self, prompt: str, temperature: float, db_path: Optional[str] = None
    ) -> None:
        """Start generation in worker thread."""
        # Update UI
        self.generate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status_label.setText("Generating...")
        # self.preview_text.clear()  # Removed
        # self.preview_text.setVisible(True)  # Removed

        # Create worker
        self._worker = GenerationWorker(
            self._current_provider,
            prompt,
            self.max_tokens_spin.value(),
            temperature,
            db_path,
            (
                int(self.rag_limit_input.text())
                if self.rag_limit_input.text().isdigit()
                else 3
            ),
        )

        # Connect signals
        # self._worker.chunk_received.connect(self._on_chunk_received)  # Removed
        self._worker.generation_complete.connect(self._on_generation_complete)
        self._worker.generation_error.connect(self._on_generation_error)

        # Start worker
        self._worker.start()

    # def _on_chunk_received(self, chunk: str):
    #     """Handle streaming chunk."""
    #     self.preview_text.appendPlainText(chunk)

    def _on_generation_complete(self, text: str) -> None:
        """Handle generation completion."""
        logger.info(f"Generation complete. Received {len(text)} characters.")
        logger.debug(f"Generated Text:\n{text}")
        self.status_label.setText(f"Generated {len(text)} characters")
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        # Emit signal for parent to handle
        self.text_generated.emit(text)

        # Clean up worker
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    def _on_generation_error(self, error: str) -> None:
        """Handle generation error."""
        logger.error(f"Generation error: {error}")
        self.status_label.setText(f"Error: {error}")
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        # Clean up worker
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    def _on_cancel_clicked(self) -> None:
        """Handle cancel button click."""
        if self._worker:
            self._worker.cancel()
            self._worker.wait(1000)  # Wait up to 1 second
            self._worker.deleteLater()
            self._worker = None

        self.status_label.setText("Generation cancelled")
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def _on_preview_clicked(self) -> None:
        """Show prompt preview dialog."""
        context = self._get_generation_context()
        if not context:
            QMessageBox.warning(self, "Preview Error", "Could not get context.")
            return

        # Reuse same logic as generate to ensure accuracy
        if self.use_custom_prompt_cb.isChecked():
            user_prompt = self.custom_prompt_edit.toPlainText().strip()
            # Logic duplicated for now to ensure consistency - ideally refactor
            # ... (Copied logic from above or refactored into helper)
            # For compactness, let's refactor the prompt build part into a method?
            # Or just duplicate the lightweight construction logic here.

            context_lines = []
            if "name" in context:
                context_lines.append(f"Name: {context['name']}")
            if "type" in context:
                context_lines.append(f"Type: {context['type']}")
            if "lore_date" in context:
                context_lines.append(f"Lore Date: {context['lore_date']}")
            if "existing_description" in context:
                context_lines.append(f"Description: {context['existing_description']}")
            for k, v in context.items():
                if k not in [
                    "name",
                    "type",
                    "lore_date",
                    "existing_description",
                    "description",
                ]:
                    context_lines.append(f"{k.replace('_', ' ').title()}: {v}")
            context_str = "\n".join(context_lines)

            system_persona = self._get_system_prompt()
            rag_placeholder = "{{RAG_CONTEXT}}" if self.rag_cb.isChecked() else ""
            prompt = (
                f"{system_persona}\n\n"
                f"{rag_placeholder}"
                f"Context:\n{context_str}\n\n"
                f"Task: {user_prompt}"
            )
        else:
            prompt = self._build_prompt(context, self.rag_cb.isChecked())

        # Show dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Prompt Preview")
        dlg.resize(600, 400)

        # Apply theme
        dlg.setStyleSheet(StyleHelper.get_dialog_base_style())

        layout = QVBoxLayout(dlg)

        # Determine DB path for RAG if enabled
        db_path = None
        if self.rag_cb.isChecked():
            window = self.window()
            if hasattr(window, "db_path"):
                db_path = window.db_path

        # Perform RAG search for preview
        rag_context = ""
        if db_path and "{{RAG_CONTEXT}}" in prompt:
            # Show loading status (simple blocking for now as requested)
            rag_context = perform_rag_search(prompt, db_path)
            prompt = prompt.replace("{{RAG_CONTEXT}}", rag_context)
            if not rag_context:
                # Remove placeholder clean
                prompt = prompt.replace("{{RAG_CONTEXT}}", "")

        info = QLabel(
            "This is the prompt structure that will be sent to the LLM.\n"
            "Real RAG context has been fetched and included below."
        )
        # Re-apply text dim color manually or use a helper if available,
        # but StyleHelper.get_preview_label_style() looks appropriate or similar.
        info.setStyleSheet(StyleHelper.get_preview_label_style())
        layout.addWidget(info)

        text_edit = QPlainTextEdit()
        text_edit.setPlainText(prompt)
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet(
            StyleHelper.get_input_field_style() + "font-family: Consolas, monospace;"
        )
        layout.addWidget(text_edit)

        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        close_btn.setStyleSheet(StyleHelper.get_primary_button_style())

        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        dlg.exec()
