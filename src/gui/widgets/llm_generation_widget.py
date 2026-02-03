"""LLM Generation Widget Module.

Provides a compact UI for generating text using configured LLM providers. Supports
streaming output and appending to existing text.
"""

import asyncio
import logging
import re
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from PySide6.QtCore import QSettings, Qt, QThread, Signal, Slot
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
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

from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.prompt_editor import PromptEditorWidget
from src.services.llm_provider import create_provider
from src.services.prompt_loader import PromptLoader

# from src.services.search_service import create_search_service  # No longer needed directly
from src.services.rag_service import RAGService

logger = logging.getLogger(__name__)


# Regex pattern to match common reasoning/thinking tags from various models
# Matches: <think>, <thinking>, <thought>, <reasoning>, <scratchpad>, <reflection>
# Uses DOTALL to handle multiline content and non-greedy match
_REASONING_TAG_PATTERN = re.compile(
    r"<(think|thinking|thought|reasoning|scratchpad|reflection)>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)


def filter_reasoning_tags(text: str) -> str:
    """Remove reasoning/thinking tags from LLM output.

    Filters out content between common reasoning tags used by various models:
    - DeepSeek R1: <think>...</think>
    - Claude: <thinking>...</thinking>
    - Other models: <thought>, <reasoning>, <scratchpad>, <reflection>

    Args:
        text: Raw LLM output text.

    Returns:
        str: Text with reasoning tags and their content removed, stripped.

    """
    filtered = _REASONING_TAG_PATTERN.sub("", text)
    return filtered.strip()


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
class GenerationContextProvider(Protocol):
    """Protocol for widgets that provide context for LLM generation."""

    def get_generation_context(self) -> Dict[str, Any]:
        """Return context dictionary for generation.
        
        Returns:
            Dict[str, Any]: Context data for LLM prompt construction.
                Typically includes keys like 'name', 'type', 'existing_description'.
        """
        ...


# perform_rag_search removed; logic moved to src.services.rag_service.RAGService


class GenerationWorker(QThread):
    """Worker thread for LLM text generation.

    Runs generation in background to avoid blocking the UI.
    """

    # chunk_received = Signal(str)  # Removed as per user request
    generation_complete = Signal(str)  # Full generated text
    generation_error = Signal(str)  # Error message

    def __init__(
        self,
        provider: Any,
        prompt: Any,  # str or dict with system/user keys
        max_tokens: int,
        temperature: float,
        db_path: Optional[str] = None,
        rag_limit: int = 3,
        exclude_names: Optional[list[str]] = None,
    ) -> None:
        """Initialize generation worker.

        Args:
            provider: LLM provider instance.
            prompt: Text prompt (str) or structured prompt (dict with
                'system' and 'user' keys) for generation.
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
        self.exclude_names = exclude_names or []
        self._cancelled = False

    def _perform_rag_search(self, query_text: str) -> str:
        """Perform RAG search if db_path is set.

        Args:
            query_text: Text to use for RAG query.

        Returns:
            Formatted context string or empty string.

        """
        # This method is now effectively deprecated by the new _apply_rag_to_prompt
        # but kept for context of the original diff.
        # The new _apply_rag_to_prompt directly uses RAGService.
        return ""

    def _apply_rag_to_prompt(self) -> None:
        """Inject RAG context into the prompt."""
        # Check if RAG is useful/enabled
        if not self.db_path:
            return

        rag_context = ""
        user_msg = ""
        is_dict = isinstance(self.prompt, dict)

        # Extract user message for context key
        if is_dict:
            user_msg = self.prompt.get("user", "")
        else:
            user_msg = str(self.prompt)

        # Only perform RAG if placeholder exists OR forced
        # (though we usually rely on placeholder)
        # RAGService handles query cleaning, so we pass raw user input
        should_run = "{{RAG_CONTEXT}}" in user_msg or (self.rag_limit > 0)

        if should_run:
            try:
                # Use modular RAGService
                rag_service = RAGService(self.db_path)
                logger.info(
                    f"RAG: Searching context for query: '{user_msg[:50]}...' "
                    f"(Limit: {self.rag_limit})"
                )

                # Pass full user message; service cleans it.
                rag_context = rag_service.get_context(
                    user_msg, top_k=self.rag_limit, exclude_names=self.exclude_names
                )

                if rag_context:
                    logger.info(
                        f"RAG: Found context ({len(rag_context)} chars). "
                        f"Snippet: {rag_context[:100].replace(chr(10), ' ')}..."
                    )
                else:
                    logger.info("RAG: No context found or returned empty.")

            except Exception as e:
                logger.error(f"RAG Service failure: {e}", exc_info=True)
                rag_context = ""

        # Inject logic
        if is_dict:
            if "{{RAG_CONTEXT}}" in self.prompt["user"]:
                replacement = (
                    f"--- DATA: RAG CONTEXT ---\n{rag_context}" if rag_context else ""
                )
                self.prompt["user"] = self.prompt["user"].replace(
                    "{{RAG_CONTEXT}}", replacement
                )
            elif rag_context:
                # Prepend if no placeholder but content found
                self.prompt["user"] = (
                    f"--- DATA: RAG CONTEXT ---\n{rag_context}\n" + self.prompt["user"]
                )
        else:
            # String prompt
            if "{{RAG_CONTEXT}}" in self.prompt:
                replacement = (
                    f"--- DATA: RAG CONTEXT ---\n{rag_context}" if rag_context else ""
                )
                self.prompt = self.prompt.replace("{{RAG_CONTEXT}}", replacement)
            elif rag_context:
                self.prompt = (
                    f"--- DATA: RAG CONTEXT ---\n{rag_context}\n" + self.prompt
                )

        if rag_context:
            logger.debug(f"Applied RAG context: {len(rag_context)} chars")

    def run(self) -> None:
        """Run generation in background thread."""
        try:
            # 1. Perform RAG if enabled (synchronous in this thread)
            self._apply_rag_to_prompt()

            if isinstance(self.prompt, dict):
                sys_len = len(self.prompt.get("system", ""))
                usr_len = len(self.prompt.get("user", ""))
                logger.debug(
                    f"Final prompt (dict): system={sys_len} chars, user={usr_len} chars"
                )
                logger.debug(f"System Prompt: {self.prompt.get('system', '')[:100]}...")
                logger.debug(f"User Prompt: {self.prompt.get('user', '')[:200]}...")

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
                """Execute the streaming generation and collect the full text."""
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
    """Widget for LLM text generation with streaming output.

    Provides a compact UI below description fields to generate text using configured LLM
    providers.
    """

    text_generated = Signal(str)  # Emitted when generation completes

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        context_provider: Optional[GenerationContextProvider] = None,
    ) -> None:
        """Initialize LLM generation widget.

        Args:
            parent: Parent widget.
            context_provider: Optional provider for generation context.

        """
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._worker: Optional[GenerationWorker] = None
        self._current_provider = None
        self._context_provider = context_provider

        # Main layout
        main_layout = QVBoxLayout(self)
        StyleHelper.apply_compact_spacing(main_layout)

        # Main Separator line (Top)
        top_sep = QFrame()
        top_sep.setFrameShape(QFrame.Shape.HLine)
        top_sep.setFrameShadow(QFrame.Shadow.Sunken)
        top_sep.setStyleSheet("color: #444444; margin-bottom: 4px;")
        main_layout.addWidget(top_sep)

        # Controls grid layout (Revised to QGridLayout for alignment)
        # Col 0: Labels, Col 1: Inputs, Col 2: Labels/Checkboxes, Col 3: Inputs
        grid_layout = QGridLayout()
        # grid_layout.setVerticalSpacing(8) # Optional: StyleHelper handles spacing?

        # Row 0: Task Template
        grid_layout.addWidget(QLabel("Task Template:"), 0, 0)
        self.template_combo = QComboBox()
        self.template_combo.setToolTip(
            "Select task template. NOTE: Selecting a template overrides the\n"
            "global Persona configured in AI Settings."
        )
        self._populate_template_combo()
        self.template_combo.currentIndexChanged.connect(self._on_template_combo_changed)
        grid_layout.addWidget(self.template_combo, 0, 1, 1, 3)  # Span 3 cols

        # Row 1: Provider | Max Tokens
        grid_layout.addWidget(QLabel("Provider:"), 1, 0)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(
            ["LM Studio", "OpenAI", "Google Vertex AI", "Anthropic"]
        )
        self.provider_combo.setToolTip("Select LLM provider for generation")
        self.provider_combo.currentIndexChanged.connect(self._save_settings)
        # Removing manual size policy, Grid should handle it better
        from PySide6.QtWidgets import QSizePolicy

        self.provider_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        grid_layout.addWidget(self.provider_combo, 1, 1)

        grid_layout.addWidget(QLabel("Max Tokens:"), 1, 2)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(50, 4096)
        self.max_tokens_spin.setValue(512)
        self.max_tokens_spin.setToolTip("Maximum tokens to generate")
        self.max_tokens_spin.valueChanged.connect(self._save_settings)
        grid_layout.addWidget(self.max_tokens_spin, 1, 3)

        # Row 2: Temp | RAG
        grid_layout.addWidget(QLabel("Temp:"), 2, 0)

        self.temperature_spin = QSpinBox()
        self.temperature_spin.setRange(0, 200)
        self.temperature_spin.setValue(70)
        self.temperature_spin.setSuffix("%")
        self.temperature_spin.setToolTip("Temperature (0-200%, where 100% = 1.0)")
        self.temperature_spin.valueChanged.connect(self._save_settings)
        grid_layout.addWidget(self.temperature_spin, 2, 1)

        # RAG Checkbox in Col 2 (Label position)
        self.rag_cb = QCheckBox("Use RAG Context")
        self.rag_cb.setChecked(True)
        self.rag_cb.setToolTip("Include relevant context from database (RAG)")
        grid_layout.addWidget(self.rag_cb, 2, 2)

        # RAG Limit in Col 3
        # bg_rag_limit container removed as it was unused

        self.rag_limit_input = QLineEdit()
        self.rag_limit_input.setPlaceholderText("3")
        self.rag_limit_input.setToolTip("Number of context items to retrieve (1-20)")
        self.rag_limit_input.setFixedWidth(50)
        self.rag_limit_input.setValidator(QIntValidator(1, 20))
        self.rag_limit_input.setText("3")

        # Handle toggling
        self.rag_cb.toggled.connect(self.rag_limit_input.setVisible)
        self.rag_cb.toggled.connect(self._save_settings)
        self.rag_limit_input.editingFinished.connect(self._save_settings)

        grid_layout.addWidget(self.rag_limit_input, 2, 3)

        main_layout.addLayout(grid_layout)

        # Header for prompt section
        lbl_instruction = QLabel("Prompt Instructions")
        lbl_instruction.setStyleSheet(
            "font-weight: bold; font-size: 10px; color: #888888; margin-top: 4px;"
        )
        main_layout.addWidget(lbl_instruction)

        # Custom prompt input
        self.custom_prompt_edit = PromptEditorWidget()
        self.custom_prompt_edit.setPlaceholderText(
            "Enter your custom prompt here...\n\n"
            "Example: 'Write a mysterious backstory for {name}' or "
            "'Describe this {type} in vivid detail'"
        )
        self.custom_prompt_edit.set_variables(
            ["{name}", "{type}", "{description}", "{lore_date}"]
        )
        self.custom_prompt_edit.setMaximumHeight(120)  # Slightly taller for toolbar
        main_layout.addWidget(self.custom_prompt_edit)

        # Separator line before buttons
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        sep2.setStyleSheet("color: #444444; margin-top: 8px;")
        main_layout.addWidget(sep2)

        # Action Buttons Layout (Below text field)
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()  # Right align buttons

        # Cancel button (Left of Generate/Preview cluster? Or right aligned?
        # User said Generate Cancel Preview right aligned)
        # Usually Cancel is on the left of affirmative actions.
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setToolTip("Cancel generation")
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        buttons_layout.addWidget(self.cancel_btn)

        # Preview button
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setToolTip("Preview the prompt before generating")
        self.preview_btn.clicked.connect(self._on_preview_clicked)
        buttons_layout.addWidget(self.preview_btn)

        # Generate button
        self.generate_btn = QPushButton("Generate")
        self.generate_btn.setToolTip("Generate text and append to description")
        self.generate_btn.clicked.connect(self._on_generate_clicked)
        buttons_layout.addWidget(self.generate_btn)

        main_layout.addLayout(buttons_layout)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #95a5a6; font-size: 11px;")
        main_layout.addWidget(self.status_label)

        # Preview area removed as per user request
        # self.preview_text = QPlainTextEdit()
        # ...

        # Load settings
        self._load_settings()

    def _populate_template_combo(self) -> None:
        """Populate template combo box with available templates."""
        try:
            self.template_combo.clear()

            # Add option for no template (Free Text)
            self.template_combo.addItem("Free Text / Custom", None)

            loader = PromptLoader()
            templates = loader.list_templates()

            # Sort by name for consistent ordering
            templates.sort(key=lambda t: t.get("name", "").lower())

            # Store template info as user data for easy retrieval
            for template in templates:
                display_name = f"{template['name']}"
                template_id = template["template_id"]
                # Store template_id as item data
                self.template_combo.addItem(display_name, template_id)

        except Exception as e:
            logger.error(f"Failed to populate template combo: {e}")
            # Ensure at least the default exists
            if self.template_combo.count() == 0:
                self.template_combo.addItem("Free Text / Custom", None)

    @Slot()
    def _on_template_combo_changed(self) -> None:
        """Handle template selection change.

        Populates the custom prompt text edit with the selected template's content.
        This represents the 'Task' part of the Trinity.
        """
        template_id = self.template_combo.currentData()
        if not template_id:
            # Clears the prompt if "Free Text" is selected?
            # Or maybe we leave it as is?
            # User experience: if I type something, then accidentally switch, I lose it?
            # Let's decide to NOT clear automatically to be safe,
            # unless the user explicitly wants to.
            # BUT: If I select a template, I expect text.
            return

        try:
            loader = PromptLoader()
            template = loader.load_template(template_id)
            if template and template.content:
                self.custom_prompt_edit.setPlainText(template.content)
                # We do NOT save the template ID to settings as "system prompt override" anymore.
                # Use standard saving for valid settings if needed, but template selection
                # is now an ACTION, not a persisted SETTING for system prompt.
        except Exception as e:
            logger.error(f"Failed to load template content: {e}")
            self.status_label.setText(f"Error loading template: {e}")

    def _load_settings(self) -> None:
        """Load provider settings from QSettings."""
        try:
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

            # Load template selection
            self.template_combo.blockSignals(True)
            saved_template_id = settings.value("ai_gen_template_id", None)
            # Find the template in the combo box by its data (template_id)
            for i in range(self.template_combo.count()):
                if self.template_combo.itemData(i) == saved_template_id:
                    self.template_combo.setCurrentIndex(i)
                    break
            self.template_combo.blockSignals(False)

        except Exception as e:
            logger.warning(f"Failed to load generation settings: {e}")

    @Slot()
    def _save_settings(self) -> None:
        """Save current settings to QSettings."""
        try:
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

            # Save template selection
            # NOTE: We no longer persist 'ai_gen_template_id' as a System Prompt override.
            # Template selection is ephemeral or just fills the text box.

        except Exception as e:
            logger.error(f"Failed to save generation settings: {e}", exc_info=True)

    def _get_provider_id(self) -> str:
        """Get provider ID from combo box selection."""
        provider_map = {
            "LM Studio": "lmstudio",
            "OpenAI": "openai",
            "Google Vertex AI": "google",
            "Anthropic": "anthropic",
        }
        return provider_map.get(self.provider_combo.currentText(), "lmstudio")

    @Slot()
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

        # Validate custom prompt
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

        # Add any additional context fields
        context_lines.extend(
            f"{k.replace('_', ' ').title()}: {v}"
            for k, v in context.items()
            if k
            not in ["name", "type", "lore_date", "existing_description", "description"]
        )
        context_str = "\n".join(context_lines)

        # Substitute variables in user prompt
        user_prompt = self._get_substituted_prompt(user_prompt, context)

        prompt = self._construct_prompt(context_str, user_prompt)
        self.status_label.setText("Generating with context...")

        # Get temperature as float (0.0-2.0)
        temperature = self.temperature_spin.value() / 100.0

        # Determine DB path for RAG if enabled
        db_path = None

        # Determine DB path and run context logic if needed
        # Logic moved to GenerationWorker/_on_preview_clicked
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

    def _get_system_prompt(self) -> str:
        """Get the persona (system prompt) from settings.

        Loads the global persona associated with the current world settings.
        Unlike previous versions, this is NOT overridden by the Task Template.

        Returns:
            str: The configured persona, or default if not set.

        """
        try:
            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

            # Load from settings (was "Basic Assistant Prompt", now "Persona")
            custom_prompt = settings.value("ai_gen_system_prompt", None)

            if custom_prompt:
                logger.debug("Using configured Persona from QSettings")
                return custom_prompt

            # Fallback to hardcoded default
            logger.debug("Using DEFAULT_SYSTEM_PROMPT")
            return DEFAULT_SYSTEM_PROMPT

        except Exception as e:
            logger.warning(f"Failed to load system prompt: {e}")
            return DEFAULT_SYSTEM_PROMPT

    def _get_generation_context(self) -> Optional[dict]:
        """Get context from provider or parent editor for prompt construction.

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

    def _construct_prompt(self, context_str: str, user_prompt: str) -> Dict[str, Any]:
        """Construct the final prompt with persona and delimited context.

        Args:
            context_str: Formatted context string with entity/event details.
            user_prompt: User's custom prompt/task.

        Returns:
            Dict[str, Any]: Structured prompt dictionary containing:
                - 'system' (str): System persona/role instructions
                - 'user' (str): User message with context and prompt
                Used for chat-based LLM APIs.

        """
        # 1. Persona (System Role)
        system_persona = self._get_system_prompt()

        # 2. Data Injection (User Role) with Explicit Delimiters
        # RAG Context (if any)
        rag_placeholder = ""
        if self.rag_cb.isChecked():
            # RAG search happens inside GenerationWorker._apply_rag_to_prompt
            # We insert a placeholder here that the worker will replace with the full block
            rag_placeholder = "{{RAG_CONTEXT}}"

        # Build User Message
        user_message_parts = []

        # -- TASK --
        # Trinity Order: Persona -> Task -> Content
        # We prefix with "Task:" to be clear, or just use the raw prompt.
        # Given the clear separation, "Task:" prefix is good for structure.
        user_message_parts.append(f"Task: {user_prompt}\n")

        # -- DATA: ENTITY/EVENT DETAILS --
        user_message_parts.append("--- DATA: ENTITY/EVENT DETAILS ---")
        user_message_parts.append(context_str)

        # -- DATA: RAG CONTEXT --
        # Worker will replace this with:
        # --- DATA: RAG CONTEXT ---
        # [Content]
        # or remove it if empty.
        # We pre-format the placeholder to look like a placeholder for the block
        user_message_parts.append(rag_placeholder)

        user_message_parts.append("--- END DATA ---")

        # Assemble
        # Filter out empty parts (like placeholder if unchecked)
        final_user_message = "\n".join(filter(None, user_message_parts))

        return {"system": system_persona, "user": final_user_message}

    def _start_generation(
        self, prompt: dict, temperature: float, db_path: Optional[str] = None
    ) -> None:
        """Start generation in worker thread."""
        # Update UI
        self.generate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status_label.setText("Generating...")
        # self.preview_text.clear()  # Removed
        # self.preview_text.setVisible(True)  # Removed

        # Prepare exclusion list (current entity name)
        exclude_names = []
        current_context = self._get_generation_context()
        if current_context and "name" in current_context:
            exclude_names.append(current_context["name"])

        # Create worker
        self._worker = GenerationWorker(
            self._current_provider,
            prompt,
            self.max_tokens_spin.value(),
            temperature,
            db_path=db_path,
            rag_limit=self._get_rag_limit(),
            exclude_names=exclude_names,
        )

        # Connect signals
        self._worker.generation_complete.connect(self._on_generation_complete)
        self._worker.generation_error.connect(self._on_generation_error)

        # Start worker
        self._worker.start()

    def _get_rag_limit(self) -> int:
        """Safely retrieve RAG limit from input."""
        try:
            return int(self.rag_limit_input.text())
        except (ValueError, AttributeError):
            return 3  # Default fallback

    # def _on_chunk_received(self, chunk: str):
    #     """Handle streaming chunk."""
    #     self.preview_text.appendPlainText(chunk)

    @Slot(str)
    def _on_generation_complete(self, text: str) -> None:
        """Handle generation completion by showing review dialog."""
        logger.info(f"Generation complete. Received {len(text)} characters.")
        logger.debug(f"Generated Text:\n{text}")
        self.status_label.setText(f"Generated {len(text)} characters")
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        # Clean up worker first
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

        # Show review dialog
        from src.gui.dialogs.generation_review_dialog import (
            GenerationReviewDialog,
            ReviewAction,
        )

        # Check if filtering is enabled in settings (defaults to True)
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        filter_enabled = settings.value("ai_gen_filter_reasoning", True, type=bool)

        # Filter out reasoning/thinking tags if enabled
        if filter_enabled:
            filtered_text = filter_reasoning_tags(text)
            if len(filtered_text) < len(text):
                logger.info(
                    f"Filtered {len(text) - len(filtered_text)} chars of reasoning tags"
                )
        else:
            filtered_text = text

        dialog = GenerationReviewDialog(generated_text=filtered_text, parent=self)
        dialog.exec()  # Result code not needed, using dialog.get_result()

        result = dialog.get_result()
        action = result["action"]
        final_text = result["text"]
        rating = result["rating"]

        # Log rating if provided
        if rating is not None:
            logger.info(f"User rating: {'positive' if rating > 0 else 'negative'}")

        # Emit signal based on action
        if action == ReviewAction.REPLACE:
            self.text_generated.emit(f"REPLACE:{final_text}")
        elif action == ReviewAction.APPEND:
            self.text_generated.emit(f"APPEND:{final_text}")
        # DISCARD: do nothing

    @Slot(str)
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

    @Slot()
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

    @Slot()
    def _on_preview_clicked(self) -> None:
        """Show prompt preview dialog."""
        context = self._get_generation_context()
        if not context:
            QMessageBox.warning(
                self, 
                "Preview Error", 
                "Could not get context information for preview.\n\n"
                "Possible causes:\n"
                "• No item is currently loaded in the editor\n"
                "• Editor is in an invalid state\n\n"
                "To fix:\n"
                "1. Ensure an event or entity is loaded\n"
                "2. Try closing and reopening the editor\n"
                "3. If the issue persists, save your work and restart"
            )
            return

        # Reuse same logic as generate to ensure accuracy
        # Validate custom prompt
        user_prompt = self.custom_prompt_edit.toPlainText().strip()
        if not user_prompt:
            QMessageBox.warning(
                self, 
                "Preview Error", 
                "Please enter a prompt before previewing.\n\n"
                "The preview shows what will be sent to the AI, but requires\n"
                "a prompt to be entered in the text box above.\n\n"
                "To fix:\n"
                "1. Enter your generation prompt in the text field\n"
                "2. Click Preview Context again to see what will be sent"
            )
            return

        # Build context string dynamically
        context_lines = []
        if "name" in context:
            context_lines.append(f"Name: {context['name']}")
        if "type" in context:
            context_lines.append(f"Type: {context['type']}")
        if "lore_date" in context:
            context_lines.append(f"Lore Date: {context['lore_date']}")
        if "existing_description" in context:
            context_lines.append(f"Description: {context['existing_description']}")

        # Add any additional context fields
        context_lines.extend(
            f"{k.replace('_', ' ').title()}: {v}"
            for k, v in context.items()
            if k
            not in ["name", "type", "lore_date", "existing_description", "description"]
        )

        context_str = "\n".join(context_lines)

        # Substitute variables in user prompt
        user_prompt = self._get_substituted_prompt(user_prompt, context)

        # Construct prompt using helper method
        prompt = self._construct_prompt(context_str, user_prompt)

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
            # Robust lookup: Traverse up to find db_path or gui_db_service
            curr = self
            while curr:
                # Direct db_path attribute
                if hasattr(curr, "db_path") and curr.db_path:
                    db_path = curr.db_path
                    break
                # Via gui_db_service (MainWindow usually has this)
                if hasattr(curr, "gui_db_service") and hasattr(
                    curr.gui_db_service, "db_path"
                ):
                    db_path = curr.gui_db_service.db_path
                    break

                # If we hit a window that is not the main one (e.g. floating dock), keep going?
                # QWidget.parent() returns None for top-level windows unless set.
                # However, self.window() returns the window.
                # If we are at top level and haven't found it,
                # we might check self.window() explicitly
                # if the loop didn't cover it (parent() from child hits window? Yes).

                # Special jump for QDockWidget if floating?
                # If floating, parent() might be None, but it is effectively parented to main in logic?
                # No, floating dock matches window().

                parent = curr.parent()
                if not parent:
                    # If we reached top and didn't find it, consider checking QApplication.topLevelWidgets
                    # as last resort? Or just rely on what we found.
                    # Try accessing .window() just in case we started mid-hierarchy
                    # and parent() traversal failure
                    w = curr.window()
                    if w and w != curr:
                        curr = w
                        continue
                    break
                curr = parent

        # Perform RAG search for preview
        rag_context = ""
        # prompt is a dict with 'system' and 'user' keys
        user_msg = prompt.get("user", "")
        if db_path and "{{RAG_CONTEXT}}" in user_msg:
            # Show loading status (simple blocking for now as requested)
            try:
                rag_limit = self._get_rag_limit()
                if rag_limit > 0:
                    rag_service = RAGService(db_path)
                    logger.info(
                        f"Preview RAG: Searching context for query len: {len(user_msg)}"
                    )
                    rag_context = rag_service.get_context(user_msg, top_k=rag_limit)
                    if rag_context:
                        logger.info(
                            f"Preview RAG: Found context ({len(rag_context)} chars)."
                        )
                    else:
                        logger.info("Preview RAG: No context found.")
            except Exception as e:
                logger.error(f"RAG Preview failed: {e}")

            # Update the user message in the prompt dict
            replacement = (
                f"--- DATA: RAG CONTEXT ---\n{rag_context}"
                if rag_context
                else "--- DATA: RAG CONTEXT ---\n(No results found for query)"
            )
            prompt["user"] = user_msg.replace("{{RAG_CONTEXT}}", replacement)

        # Format for display in preview (show keys clearly)
        display_text = (
            f"--- SYSTEM ---\n{prompt.get('system', '')}\n\n"
            f"--- USER ---\n{prompt.get('user', '')}"
        )

        info = QLabel(
            "This is the prompt structure that will be sent to the LLM.\n"
            "Real RAG context has been fetched and included below."
        )
        # Re-apply text dim color manually or use a helper if available,
        # but StyleHelper.get_preview_label_style() looks appropriate or similar.
        info.setStyleSheet(StyleHelper.get_preview_label_style())
        layout.addWidget(info)

        text_edit = QPlainTextEdit()
        text_edit.setPlainText(display_text)
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet(
            f"{StyleHelper.get_input_field_style()}font-family: Consolas, monospace;"
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

    def _get_substituted_prompt(self, user_prompt: str, context: dict) -> str:
        """Substitute variables like {name} in the user prompt.

        Args:
            user_prompt: Raw user instruction.
            context: Context dictionary from editor.

        Returns:
            str: Substituted prompt.

        """
        # Normalize keys for substitution
        subst_context = {
            "name": context.get("name", ""),
            "type": context.get("type", ""),
            "description": context.get("existing_description", ""),
            "lore_date": context.get("lore_date", ""),
        }

        result = user_prompt
        for key, val in subst_context.items():
            result = result.replace(f"{{{key}}}", str(val))

        return result
