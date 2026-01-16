"""
LLM Generation Widget Module.

Provides a compact UI for generating text using configured LLM providers.
Supports streaming output and appending to existing text.
"""

import asyncio
import logging
import re
import sqlite3
from typing import Any, Optional, Protocol, runtime_checkable

from PySide6.QtCore import QSettings, Qt, QThread, Signal, Slot
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
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
from src.services.llm_provider import create_provider
from src.services.prompt_loader import PromptLoader
from src.services.search_service import create_search_service

logger = logging.getLogger(__name__)


# Regex pattern to match common reasoning/thinking tags from various models
# Matches: <think>, <thinking>, <thought>, <reasoning>, <scratchpad>, <reflection>
# Uses DOTALL to handle multiline content and non-greedy match
_REASONING_TAG_PATTERN = re.compile(
    r"<(think|thinking|thought|reasoning|scratchpad|reflection)>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)


def filter_reasoning_tags(text: str) -> str:
    """
    Remove reasoning/thinking tags from LLM output.

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
        prompt: Any,  # str or dict with system/user keys
        max_tokens: int,
        temperature: float,
        db_path: Optional[str] = None,
        rag_limit: int = 3,
    ) -> None:
        """
        Initialize generation worker.

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
        self._cancelled = False

    def _perform_rag_search(self, query_text: str) -> str:
        """
        Perform RAG search if db_path is set.

        Args:
            query_text: Text to use for RAG query.

        Returns:
            Formatted context string or empty string.
        """
        return perform_rag_search(query_text, self.db_path, self.rag_limit)

    def _apply_rag_to_prompt(self) -> None:
        """Apply RAG context to the prompt (modifies self.prompt in place)."""
        # Determine query text for RAG
        if isinstance(self.prompt, dict):
            query_text = self.prompt.get("user", "")[:200]
        else:
            query_text = str(self.prompt)[:200]

        rag_context = self._perform_rag_search(query_text)

        if isinstance(self.prompt, dict):
            # For dict prompts, inject RAG into user message
            user_msg = self.prompt.get("user", "")
            if "{{RAG_CONTEXT}}" in user_msg:
                self.prompt["user"] = user_msg.replace("{{RAG_CONTEXT}}", rag_context)
            elif rag_context:
                logger.info(
                    "RAG Context found but no placeholder. Prepending to user msg."
                )
                self.prompt["user"] = rag_context + user_msg
        else:
            # For string prompts (backward compatibility)
            if "{{RAG_CONTEXT}}" in self.prompt:
                self.prompt = self.prompt.replace("{{RAG_CONTEXT}}", rag_context)
            elif rag_context:
                logger.info("RAG Context found but no placeholder. Prepending.")
                self.prompt = rag_context + self.prompt

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

        # Template selection row
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Template:"))
        self.template_combo = QComboBox()
        self.template_combo.setToolTip("Select prompt template for generation")
        self._populate_template_combo()
        self.template_combo.currentIndexChanged.connect(self._save_settings)
        template_layout.addWidget(self.template_combo)
        template_layout.addStretch()
        main_layout.addLayout(template_layout)

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

        # RAG Context Checkbox
        self.rag_cb = QCheckBox("Use RAG Context")
        self.rag_cb.setChecked(True)
        self.rag_cb.setToolTip("Include relevant context from database (RAG)")
        controls_layout.addWidget(self.rag_cb)

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
        controls_layout.addWidget(self.rag_limit_input)

        controls_layout.addStretch()

        main_layout.addLayout(controls_layout)

        # Header for prompt section
        lbl_instruction = QLabel("Prompt Instructions")
        lbl_instruction.setStyleSheet(
            "font-weight: bold; font-size: 10px; color: #888888; margin-top: 4px;"
        )
        main_layout.addWidget(lbl_instruction)

        # Custom prompt input
        self.custom_prompt_edit = QPlainTextEdit()
        self.custom_prompt_edit.setStyleSheet(StyleHelper.get_input_field_style())
        self.custom_prompt_edit.setPlaceholderText(
            "Enter your custom prompt here...\n\n"
            "Example: 'Write a mysterious backstory for this character' or "
            "'Describe this location in vivid detail'"
        )
        self.custom_prompt_edit.setMaximumHeight(80)
        self.custom_prompt_edit.setVisible(True)  # Always visible
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
            loader = PromptLoader()
            templates = loader.list_templates()

            # Filter to only description templates
            description_templates = [
                t for t in templates if t["template_id"].startswith("description_")
            ]

            # Sort by template_id for consistent ordering
            description_templates.sort(key=lambda t: t["template_id"])

            self.template_combo.clear()

            # Store template info as user data for easy retrieval
            for template in description_templates:
                display_name = f"{template['name']}"
                template_id = template["template_id"]
                # Store template_id as item data
                self.template_combo.addItem(display_name, template_id)

            # If no description templates found, add a fallback
            if self.template_combo.count() == 0:
                self.template_combo.addItem("Default (Fallback)", "description_default")
                logger.warning("No description templates found, using fallback")

        except Exception as e:
            logger.error(f"Failed to populate template combo: {e}")
            # Add fallback option
            self.template_combo.addItem("Default (Error)", "description_default")

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
            saved_template_id = settings.value(
                "ai_gen_template_id", "description_default"
            )
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
            current_template_id = self.template_combo.currentData()
            logger.debug(f"Saving template_id: {current_template_id}")
            if current_template_id:
                settings.setValue("ai_gen_template_id", current_template_id)
                settings.sync()  # Ensure settings are written immediately
                logger.debug(f"Template ID saved: {current_template_id}")
            else:
                logger.warning("Template ID is empty, not saving")

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

        prompt = self._construct_prompt(context_str, user_prompt)
        self.status_label.setText("Generating with context...")

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
        """
        Get the system prompt from settings or selected template.

        Loads the system prompt using the following priority:
        1. Template selected in the UI dropdown (ai_gen_template_id)
        2. Custom prompt from QSettings (ai_gen_system_prompt)
           - backward compatibility
        3. Template-based prompt from PromptLoader
           (ai_gen_system_prompt_template_id/version)
        4. DEFAULT_SYSTEM_PROMPT as fallback

        The prompt can be customized via:
        Settings → AI Settings → Text Generation tab → System Prompt field

        Returns:
            str: The configured system prompt, or default if not set.
        """
        try:
            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

            # First priority: Use template selected in UI
            template_id = self.template_combo.currentData()
            if template_id:
                try:
                    loader = PromptLoader()
                    template = loader.load_template(template_id)
                    logger.info(
                        f"Loaded system prompt from UI template: "
                        f"{template.template_id} v{template.version} "
                        f"({template.name})"
                    )
                    return template.content
                except Exception as e:
                    logger.warning(
                        f"Failed to load UI template {template_id}: {e}. "
                        f"Trying fallback..."
                    )

            # Second priority: Check for custom prompt (backward compatibility)
            custom_prompt = settings.value("ai_gen_system_prompt", None)
            if custom_prompt:
                logger.debug("Using custom system prompt from QSettings")
                return custom_prompt

            # Third priority: Try to load from old template settings
            old_template_id = settings.value("ai_gen_system_prompt_template_id", None)
            old_template_version = settings.value("ai_gen_system_prompt_version", None)

            if old_template_id:
                try:
                    loader = PromptLoader()
                    template = loader.load_template(
                        old_template_id, version=old_template_version
                    )
                    logger.info(
                        f"Loaded system prompt from old template settings: "
                        f"{template.template_id} v{template.version} "
                        f"({template.name})"
                    )
                    return template.content
                except Exception as e:
                    logger.warning(
                        f"Failed to load template {old_template_id} "
                        f"v{old_template_version}: {e}. Falling back to default."
                    )

            # Final fallback to hardcoded default
            logger.debug("Using DEFAULT_SYSTEM_PROMPT")
            return DEFAULT_SYSTEM_PROMPT

        except Exception as e:
            logger.warning(f"Failed to load system prompt: {e}")
            return DEFAULT_SYSTEM_PROMPT

    def _get_few_shot_examples(self) -> str:
        """
        Load few-shot examples for inclusion in prompts.

        Returns:
            str: Few-shot examples content, or empty string if not available.
        """
        try:
            loader = PromptLoader()
            few_shot = loader.load_few_shot()
            logger.debug(f"Loaded few-shot examples: {len(few_shot)} characters")
            return few_shot
        except FileNotFoundError:
            logger.warning("Few-shot examples file not found, skipping")
            return ""
        except Exception as e:
            logger.error(f"Failed to load few-shot examples: {e}")
            return ""

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

    def _construct_prompt(self, context_str: str, user_prompt: str) -> dict:
        """
        Construct the final prompt with system prompt, few-shot examples, and context.

        Args:
            context_str: Formatted context string with entity/event details.
            user_prompt: User's custom prompt/task.

        Returns:
            dict: Structured prompt with 'system' and 'user' keys for chat API.
        """
        system_persona = self._get_system_prompt()
        few_shot_examples = self._get_few_shot_examples()

        # Build system prompt with few-shot examples
        system_parts = [system_persona]
        if few_shot_examples:
            system_parts.append("\n\n## Examples\n\n" + few_shot_examples)

        # Insert placeholder for RAG in user message
        rag_placeholder = "{{RAG_CONTEXT}}" if self.rag_cb.isChecked() else ""

        # Build user message with context and task
        user_message = (
            f"{rag_placeholder}Context:\n{context_str}\n\nTask: {user_prompt}"
        )

        return {"system": "".join(system_parts), "user": user_message}

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
            QMessageBox.warning(self, "Preview Error", "Could not get context.")
            return

        # Reuse same logic as generate to ensure accuracy
        # Validate custom prompt
        user_prompt = self.custom_prompt_edit.toPlainText().strip()
        if not user_prompt:
            QMessageBox.warning(self, "Preview Error", "Please enter a prompt first.")
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
