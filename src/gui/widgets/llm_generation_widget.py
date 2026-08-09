"""LLM Generation Widget Module.

Provides a compact UI for generating text using configured LLM providers. Supports
streaming output and appending to existing text.
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import replace
from typing import Any, Dict, Optional, Protocol, cast, runtime_checkable

from PySide6.QtCore import QObject, QSettings, Qt, QThread, Signal, Slot
from PySide6.QtGui import QCloseEvent, QIntValidator, QStandardItemModel
from PySide6.QtWidgets import (
    QApplication,
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
from src.core.ai_generation import (
    GenerationApplyMode,
    GenerationRequest,
    ModelReply,
    TaskIntent,
    TaskTemplate,
)
from src.core.logging_config import get_world_audit_log_path
from src.gui.utils.settings_reader import (
    read_bool_setting,
    read_int_setting,
    read_str_setting,
)
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.prompt_editor import PromptEditorWidget
from src.services.ai_audit_service import (
    log_generation_event,
    log_review_event,
    new_interaction_id,
)
from src.services.llm_provider import Provider, create_provider
from src.services.prompt_builder import DEFAULT_SYSTEM_PROMPT, PromptBuilder
from src.services.rag_service import RAGService
from src.services.reasoning_filter import filter_reasoning_tags
from src.services.spatial_context_builder import lookup_spatial_context

logger = logging.getLogger(__name__)

GenerationPrompt = str | dict[str, str]


def _normalize_generation_prompt(prompt: object) -> GenerationPrompt:
    """Validate and copy a prompt crossing into the generation worker.

    Args:
        prompt: Legacy string prompt or structured prompt object.

    Returns:
        A string prompt or a detached ``system``/``user`` prompt dictionary.

    Raises:
        TypeError: If the prompt does not match the supported contract.

    """
    if isinstance(prompt, str):
        return prompt
    if not isinstance(prompt, dict):
        raise TypeError("Generation prompt must be a string or dictionary")

    system_prompt = prompt.get("system", "")
    user_prompt = prompt.get("user")
    if not isinstance(system_prompt, str) or not isinstance(user_prompt, str):
        raise TypeError(
            "Structured generation prompts require string 'system' and 'user' values"
        )
    return {"system": system_prompt, "user": user_prompt}


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
    generation_complete = Signal(object)  # ModelReply
    generation_error = Signal(str)  # Error message

    def __init__(
        self,
        provider: Any,
        prompt: GenerationPrompt,
        max_tokens: int,
        temperature: float,
        db_path: Optional[str] = None,
        rag_limit: int = 3,
        exclude_names: Optional[list[str]] = None,
        object_id: Optional[str] = None,
        object_type: Optional[str] = None,
        active_map_id: Optional[str] = None,
        spatial_enabled: bool = False,
        request: GenerationRequest | None = None,
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
            exclude_names: Entity/event names to exclude from RAG hits.
            object_id: UUID of the entity/event being generated for. Required
                together with ``active_map_id`` for spatial context.
            object_type: ``"entity"`` or ``"event"``.
            active_map_id: ID of the map currently selected in the map widget,
                used as the strict primary map for spatial context lookup.
            spatial_enabled: When True, the worker attempts to inject a
                ``[Spatial Context]`` block in place of ``{{SPATIAL_CONTEXT}}``.

        """
        super().__init__()
        self.provider = provider
        raw_prompt: object = request.prompt if request is not None else prompt
        self.prompt = _normalize_generation_prompt(raw_prompt)
        if request is not None:
            self.max_tokens = request.max_tokens
            self.temperature = request.temperature
            self.db_path = request.db_path
            self.rag_limit = request.rag_limit
            self.exclude_names = list(request.exclude_names)
            self.object_id = request.target_id
            self.object_type = request.object_type
            self.active_map_id = request.active_map_id
            self.spatial_enabled = request.spatial_enabled
        else:
            self.max_tokens = max_tokens
            self.temperature = temperature
            self.db_path = db_path
            self.rag_limit = rag_limit
            self.exclude_names = exclude_names or []
            self.object_id = object_id
            self.object_type = object_type
            self.active_map_id = active_map_id
            self.spatial_enabled = spatial_enabled
        # Populated during run() when spatial context is actually injected;
        # read by the widget to drive the post-generation transparency label.
        self.rag_context_used: Optional[str] = None
        self.spatial_context_used: Optional[str] = None
        self._cancelled = False

    def _apply_rag_to_prompt(self) -> None:
        """Inject RAG context into the prompt."""
        # Check if RAG is useful/enabled
        if not self.db_path:
            return

        rag_context = ""
        user_msg = ""
        prompt = self.prompt

        # Extract user message for context key
        if isinstance(prompt, dict):
            user_msg = prompt.get("user", "")
        else:
            user_msg = prompt

        # Only perform RAG if placeholder exists OR forced
        # (though we usually rely on placeholder)
        # RAGService handles query cleaning, so we pass raw user input
        should_run = "{{RAG_CONTEXT}}" in user_msg or (self.rag_limit > 0)

        if should_run:
            try:
                # Use modular RAGService
                rag_service = RAGService(self.db_path)
                logger.info(
                    "RAG: Searching context (query_chars=%d limit=%d)",
                    len(user_msg),
                    self.rag_limit,
                )

                # Pass full user message; service cleans it.
                rag_context = rag_service.get_context(
                    user_msg, top_k=self.rag_limit, exclude_names=self.exclude_names
                )

                if rag_context:
                    logger.info(
                        "RAG: Found context (chars=%d)", len(rag_context)
                    )
                else:
                    logger.info("RAG: No context found or returned empty.")

            except Exception as e:
                logger.error(f"RAG Service failure: {e}", exc_info=True)
                rag_context = ""

        # Inject logic
        if isinstance(prompt, dict):
            if "{{RAG_CONTEXT}}" in prompt["user"]:
                replacement = f"[Context]\n{rag_context}" if rag_context else ""
                prompt["user"] = prompt["user"].replace(
                    "{{RAG_CONTEXT}}", replacement
                )
            elif rag_context:
                # Prepend if no placeholder but content found
                prompt["user"] = (
                    f"[Context]\n{rag_context}\n\n" + prompt["user"]
                )
        else:
            # String prompt
            if "{{RAG_CONTEXT}}" in prompt:
                replacement = f"[Context]\n{rag_context}" if rag_context else ""
                prompt = prompt.replace("{{RAG_CONTEXT}}", replacement)
            elif rag_context:
                prompt = f"[Context]\n{rag_context}\n\n" + prompt

        self.prompt = prompt
        self.rag_context_used = rag_context or None

        if rag_context:
            logger.debug(f"Applied RAG context: {len(rag_context)} chars")

    def _apply_spatial_to_prompt(self) -> None:
        """Inject spatial context into the prompt (mirrors ``_apply_rag_to_prompt``).

        Runs synchronously on the worker thread. ``lookup_spatial_context``
        opens its own short-lived SQLite connection so the worker never
        touches the main thread's DB connection. Silently no-ops when
        spatial context is disabled, no DB is available, or the quality
        gate fails.
        """
        placeholder = "{{SPATIAL_CONTEXT}}"
        prompt = self.prompt
        user_msg = prompt.get("user", "") if isinstance(prompt, dict) else prompt
        if placeholder not in user_msg:
            return

        context_text: Optional[str] = None
        if (
            self.spatial_enabled
            and self.db_path
            and self.object_id
            and self.object_type
            and self.active_map_id
        ):
            context_text = lookup_spatial_context(
                self.db_path,
                self.object_id,
                self.object_type,
                self.active_map_id,
            )

        self.spatial_context_used = context_text
        replacement = context_text if context_text else ""
        if isinstance(prompt, dict):
            prompt["user"] = prompt["user"].replace(placeholder, replacement)
        else:
            prompt = prompt.replace(placeholder, replacement)
        self.prompt = prompt

        if context_text:
            logger.debug(
                f"Applied spatial context: {len(context_text)} chars for "
                f"{self.object_type}={self.object_id} on map={self.active_map_id}"
            )

    def run(self) -> None:
        """Run generation in background thread."""
        try:
            # 1. Perform RAG if enabled (synchronous in this thread)
            self._apply_rag_to_prompt()
            if self._cancelled:
                return
            # 2. Inject spatial context (also synchronous in this thread)
            self._apply_spatial_to_prompt()
            if self._cancelled:
                return

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
            if not self._cancelled:
                self.generation_error.emit(str(e))

    def _run_streaming(self) -> None:
        """Run streaming generation."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def generate() -> ModelReply:
                """Execute streaming generation and preserve its reply fields."""
                full_text = ""
                reasoning_content = ""
                tool_calls: list[dict[str, Any]] = []
                finish_reason = None
                usage: dict[str, Any] = {}
                model = ""
                system_fingerprint = None
                provider_metadata: dict[str, Any] = {}
                async for chunk in self.provider.stream_generate(
                    self.prompt,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                ):
                    delta = chunk.get("delta", "")
                    full_text += delta
                    reasoning_content += chunk.get("reasoning_delta", "")
                    tool_calls.extend(chunk.get("tool_calls_delta") or [])
                    finish_reason = chunk.get("finish_reason") or finish_reason
                    usage = chunk.get("usage") or usage
                    model = str(chunk.get("model") or model)
                    system_fingerprint = (
                        chunk.get("system_fingerprint") or system_fingerprint
                    )
                    provider_metadata.update(
                        chunk.get("provider_metadata") or {}
                    )
                return ModelReply(
                    content=full_text,
                    reasoning_content=reasoning_content,
                    tool_calls=tool_calls,
                    finish_reason=finish_reason,
                    usage=usage,
                    model=model,
                    system_fingerprint=system_fingerprint,
                    provider_metadata=provider_metadata,
                )

            result = loop.run_until_complete(generate())
            loop.close()

            if not self._cancelled:
                if not result.content:
                    raise ValueError("The model returned no visible content")
                self.generation_complete.emit(result)

        except Exception as e:
            logger.error(f"Streaming generation failed: {e}", exc_info=True)
            if not self._cancelled:
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
                reply = ModelReply.from_provider_result(result)
                if not reply.content:
                    raise ValueError("The model returned no visible content")
                self.generation_complete.emit(reply)

        except Exception as e:
            logger.error(f"Non-streaming generation failed: {e}", exc_info=True)
            if not self._cancelled:
                self.generation_error.emit(f"Generation failed: {e}")

    def cancel(self) -> None:
        """Cancel the generation."""
        self._cancelled = True
        cancel_request = getattr(self.provider, "cancel_current_request", None)
        if callable(cancel_request):
            cancel_request()


class LLMGenerationWidget(QWidget):
    """Widget for LLM text generation with streaming output.

    Provides a compact UI below description fields to generate text using configured LLM
    providers.
    """

    text_generated = Signal(object)  # GenerationReviewResult
    preferences_changed = Signal()

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
        self._generation_target_id: str | None = None
        self._generation_source_hash: str | None = None
        self._audit_interaction_id: str | None = None
        self._audit_started_at: float | None = None
        self._audit_provider_id = "unknown"
        self._audit_template: dict[str, Any] | None = None
        self._audit_generation_logged = False
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._shutdown_worker)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._worker: Optional[GenerationWorker] = None
        self._current_provider: Provider | None = None
        self._context_provider = context_provider
        self._current_db_path: Optional[str] = None
        self._task_templates: tuple[TaskTemplate, ...] = ()
        self._applied_template_content: str | None = None
        self._loading_prompt = False

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
            "Choose a reusable task. It is copied only when you select Use "
            "Template and does not change the configured Persona."
        )
        self._populate_template_combo()
        self.template_combo.currentIndexChanged.connect(self._on_template_combo_changed)
        grid_layout.addWidget(self.template_combo, 0, 1, 1, 2)
        self.use_template_btn = QPushButton("Use Template")
        self.use_template_btn.setEnabled(False)
        self.use_template_btn.setToolTip(
            "Copy the selected task into the editable prompt"
        )
        self.use_template_btn.clicked.connect(self._on_use_template_clicked)
        grid_layout.addWidget(self.use_template_btn, 0, 3)

        # Row 1: Provider | Max Tokens
        grid_layout.addWidget(QLabel("Provider:"), 1, 0)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(
            ["LM Studio", "OpenAI", "Google Vertex AI", "Anthropic"]
        )
        provider_model = cast(QStandardItemModel, self.provider_combo.model())
        for index in range(1, self.provider_combo.count()):
            item = provider_model.item(index)
            if item is not None:
                item.setEnabled(False)
                item.setToolTip("Cloud generation is not enabled in this release")
        self.provider_combo.setToolTip(
            "LM Studio is supported. Cloud providers are planned but disabled."
        )
        self.provider_combo.currentIndexChanged.connect(self._save_settings)
        # Removing manual size policy, Grid should handle it better
        from PySide6.QtWidgets import QSizePolicy

        self.provider_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        grid_layout.addWidget(self.provider_combo, 1, 1)

        grid_layout.addWidget(QLabel("Max Tokens:"), 1, 2)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(50, 100000)
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

        # Row 3: Spatial Context (opt-in). When enabled and the entity is
        # placed on the currently active map with sufficient data, the
        # worker injects a [Spatial Context] block into the prompt.
        self.spatial_cb = QCheckBox("Include spatial context")
        self.spatial_cb.setChecked(False)
        self.spatial_cb.setToolTip(
            "Include map placement, layer notes, raster classes, and nearby "
            "named entities when available on the active map."
        )
        self.spatial_cb.toggled.connect(self._save_settings)
        grid_layout.addWidget(self.spatial_cb, 3, 2, 1, 2)

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
        self.custom_prompt_edit.textChanged.connect(self._on_prompt_text_changed)
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

        # Post-generation transparency line for spatial context. Hidden until
        # a generation run produces a decision. A clickable "Show" link opens
        # a modal dialog containing the exact injected [Spatial Context] text.
        spatial_row = QHBoxLayout()
        spatial_row.setContentsMargins(0, 0, 0, 0)
        self.spatial_used_label = QLabel("")
        self.spatial_used_label.setStyleSheet("color: #888888; font-size: 11px;")
        spatial_row.addWidget(self.spatial_used_label)
        self.spatial_show_btn = QPushButton("Show")
        self.spatial_show_btn.setFlat(True)
        self.spatial_show_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.spatial_show_btn.setStyleSheet(
            "QPushButton { color: #5dade2; border: none; font-size: 11px; "
            "padding: 0px 4px; } QPushButton:hover { text-decoration: underline; }"
        )
        self.spatial_show_btn.clicked.connect(self._on_show_spatial_context_clicked)
        spatial_row.addWidget(self.spatial_show_btn)
        spatial_row.addStretch()
        main_layout.addLayout(spatial_row)
        self._last_spatial_context: Optional[str] = None
        self._set_spatial_used_visible(False)

        # Preview area removed as per user request
        # self.preview_text = QPlainTextEdit()
        # ...

        # Load settings
        self._load_settings()

    def _populate_template_combo(self) -> None:
        """Populate the selector from the coordinator-provided snapshot."""
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItem("Custom task", None)
        for template in sorted(
            self._task_templates,
            key=lambda item: (item.intent.value, item.name.casefold()),
        ):
            self.template_combo.addItem(template.name, template.template_id)
            self.template_combo.setItemData(
                self.template_combo.count() - 1,
                template.description,
                Qt.ItemDataRole.ToolTipRole,
            )
        self.template_combo.blockSignals(False)

    def set_task_templates(self, templates: tuple[TaskTemplate, ...]) -> None:
        """Apply an immutable task-template snapshot from the app manager."""
        selected_id = self.template_combo.currentData()
        self._task_templates = tuple(templates)
        self._populate_template_combo()

        context = self._get_generation_context() or {}
        object_type = str(context.get("object_type") or "")
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        saved_id = settings.value(f"ai_gen_{object_type}_template_id", "")
        self._select_template_id(str(selected_id or saved_id or ""))

        draft = self.custom_prompt_edit.toPlainText()
        selected = self._find_task_template(self.template_combo.currentData())
        if selected is not None and draft == selected.content:
            self._applied_template_content = selected.content
        elif draft.strip():
            self._select_template_id("")
            self._applied_template_content = None
        else:
            self._apply_recommended_template(context)

    def refresh_settings(self) -> None:
        """Reload settings and refresh the template list.

        Called when AI settings change in the settings dialog
        so the widget picks up new providers, models,
        and template changes without restarting.
        """
        logger.info("LLMGenerationWidget: refreshing settings")
        self._load_settings()

    @Slot()
    def _on_template_combo_changed(self) -> None:
        """Update selector affordances without overwriting the draft."""
        template = self._find_task_template(self.template_combo.currentData())
        self.use_template_btn.setEnabled(template is not None)
        if template is not None:
            self.template_combo.setToolTip(template.description)

    @Slot()
    def _on_use_template_clicked(self) -> None:
        """Copy the selected template into the editable task draft."""
        template = self._find_task_template(self.template_combo.currentData())
        if template is None:
            return
        self._loading_prompt = True
        try:
            self.custom_prompt_edit.setPlainText(template.content)
            self._applied_template_content = template.content
        finally:
            self._loading_prompt = False
        self._save_settings()

    @Slot()
    def _on_prompt_text_changed(self) -> None:
        """Mark edited template text as a custom draft and persist it."""
        if self._loading_prompt:
            return
        text = self.custom_prompt_edit.toPlainText()
        if self.template_combo.currentData() and text != self._applied_template_content:
            self._select_template_id("")
            self._applied_template_content = None
        self._save_settings()

    def _find_task_template(self, template_id: object) -> TaskTemplate | None:
        """Return a template from the current snapshot by stable ID."""
        if not template_id:
            return None
        return next(
            (
                template
                for template in self._task_templates
                if template.template_id == str(template_id)
            ),
            None,
        )

    def _select_template_id(self, template_id: str) -> None:
        """Select a task without applying its content."""
        index = self.template_combo.findData(template_id) if template_id else 0
        self.template_combo.setCurrentIndex(index if index >= 0 else 0)
        self._on_template_combo_changed()

    def _apply_recommended_template(self, context: dict[str, Any]) -> None:
        """Seed an untouched draft from create/update intent."""
        intent = (
            TaskIntent.UPDATE
            if str(context.get("existing_description") or "").strip()
            else TaskIntent.CREATE
        )
        preferred_id = (
            "revise_clarity_flow"
            if intent == TaskIntent.UPDATE
            else "create_complete_description"
        )
        template = next(
            (
                item
                for item in self._task_templates
                if item.template_id == preferred_id
            ),
            next(
                (item for item in self._task_templates if item.intent == intent),
                None,
            ),
        )
        if template is None:
            return
        self._select_template_id(template.template_id)
        self._on_use_template_clicked()

    def _load_settings(self) -> None:
        """Load provider settings from QSettings."""
        try:
            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

            # Load last used provider
            self.provider_combo.blockSignals(True)
            provider = read_str_setting(
                settings, "ai_gen_last_provider", "LM Studio"
            )
            if provider != "LM Studio":
                provider = "LM Studio"
                settings.setValue("ai_gen_last_provider", provider)
            index = self.provider_combo.findText(provider)
            if index >= 0:
                self.provider_combo.setCurrentIndex(index)
            self.provider_combo.blockSignals(False)

            # Load generation options
            self.max_tokens_spin.blockSignals(True)
            self.max_tokens_spin.setValue(
                read_int_setting(settings, "ai_gen_max_tokens", 512)
            )
            self.max_tokens_spin.blockSignals(False)

            self.temperature_spin.blockSignals(True)
            self.temperature_spin.setValue(
                read_int_setting(settings, "ai_gen_temperature", 70)
            )
            self.temperature_spin.blockSignals(False)

            # Load RAG settings
            self.rag_cb.blockSignals(True)
            self.rag_cb.setChecked(
                read_bool_setting(settings, "ai_gen_rag_enabled", True)
            )
            self.rag_cb.blockSignals(False)

            # Load spatial-context setting (opt-in; defaults off)
            self.spatial_cb.blockSignals(True)
            self.spatial_cb.setChecked(
                read_bool_setting(settings, "ai_gen_spatial_enabled", False)
            )
            self.spatial_cb.blockSignals(False)

            # rag_limit_input only saves on editingFinished, but for consistency:
            self.rag_limit_input.blockSignals(True)
            limit = str(read_int_setting(settings, "ai_gen_rag_limit", 3))
            self.rag_limit_input.setText(limit)
            self.rag_limit_input.setVisible(self.rag_cb.isChecked())
            self.rag_limit_input.blockSignals(False)

            context = self._get_generation_context() or {}
            object_type = str(context.get("object_type") or "")

            # Load object-specific template selection.
            self.template_combo.blockSignals(True)
            saved_template_id = settings.value(
                f"ai_gen_{object_type}_template_id", ""
            )
            saved_index = self.template_combo.findData(saved_template_id)
            self.template_combo.setCurrentIndex(
                saved_index if saved_index >= 0 else 0
            )
            self.template_combo.blockSignals(False)

            if object_type in {"entity", "event"}:
                draft = settings.value(f"ai_gen_{object_type}_prompt", "")
                if draft:
                    self._loading_prompt = True
                    try:
                        self.custom_prompt_edit.setPlainText(str(draft))
                    finally:
                        self._loading_prompt = False

            selected = self._find_task_template(self.template_combo.currentData())
            if selected is not None and self.custom_prompt_edit.toPlainText() == (
                selected.content
            ):
                self._applied_template_content = selected.content
            elif self.custom_prompt_edit.toPlainText().strip():
                self._select_template_id("")
                self._applied_template_content = None

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
            settings.setValue("ai_gen_spatial_enabled", self.spatial_cb.isChecked())

            # Make sure to save a valid integer
            try:
                limit_val = int(self.rag_limit_input.text())
            except ValueError:
                limit_val = 3
            settings.setValue("ai_gen_rag_limit", limit_val)

            context = self._get_generation_context() or {}
            object_type = context.get("object_type")
            if object_type in {"entity", "event"}:
                selected = self._find_task_template(self.template_combo.currentData())
                active_template_id = (
                    selected.template_id
                    if selected is not None
                    and self.custom_prompt_edit.toPlainText() == selected.content
                    else ""
                )
                settings.setValue(
                    f"ai_gen_{object_type}_template_id",
                    active_template_id,
                )
                settings.setValue(
                    f"ai_gen_{object_type}_prompt",
                    self.custom_prompt_edit.toPlainText(),
                )

            self.preferences_changed.emit()

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
        logger.debug("Generate clicked.")
        # Get context from parent (Entity/Event)
        context = self._get_generation_context()
        if not context:
            logger.warning("Generation aborted: No context found.")
            self.status_label.setText("Error: Could not get context for generation")
            return

        logger.debug(f"Generation context retrieved: {context.keys()}")
        self._generation_target_id = str(context.get("object_id") or "") or None
        self._generation_source_hash = self._hash_source_description(context)

        # Validate custom prompt
        user_prompt = self.custom_prompt_edit.toPlainText().strip()
        if not user_prompt:
            self.status_label.setText("Error: Custom prompt is empty")
            return

        # Build prompt using PromptBuilder service
        builder = PromptBuilder(system_prompt=self._get_system_prompt())
        context_str = builder.build_context_string(context)
        user_prompt = builder.substitute_variables(user_prompt, context)
        prompt = builder.construct_prompt(
            context_str,
            user_prompt,
            include_rag_placeholder=self.rag_cb.isChecked(),
            include_spatial_placeholder=self.spatial_cb.isChecked(),
            object_type=str(context.get("object_type") or ""),
        )
        self.status_label.setText("Generating with context...")

        # Get temperature as float (0.0-2.0)
        temperature = self.temperature_spin.value() / 100.0

        window = self.window()
        db_path = getattr(window, "db_path", None)
        self._current_db_path = db_path

        if self.rag_cb.isChecked():
            if db_path:
                logger.debug(f"RAG enabled. Using DB: {db_path}")
            else:
                logger.warning("RAG enabled but could not find db_path on window.")
            db_path_for_worker = db_path
        else:
            db_path_for_worker = None

        # Save settings
        self._save_settings()

        try:
            # Create provider
            provider_id = self._get_provider_id()
            logger.info(f"Creating LLM provider: {provider_id}")
            self._current_provider = create_provider(provider_id)

            # Start generation
            prompt_length = sum(
                len(str(value)) for value in prompt.values()
            )
            logger.info(
                "Starting generation: provider=%s prompt_chars=%d",
                provider_id,
                prompt_length,
            )
            self._start_generation(
                prompt,
                temperature,
                db_path_for_worker,
                object_id=context.get("object_id") or None,
                object_type=context.get("object_type") or None,
            )

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
            custom_prompt = read_str_setting(
                settings, "ai_gen_system_prompt", ""
            )

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
                if hasattr(current, "temporal_widget"):
                    formatted = current.temporal_widget.get_formatted_start_text()
                    if formatted:
                        context["lore_date"] = formatted
                elif hasattr(current, "date_edit"):
                    # Legacy fallback
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

    @staticmethod
    def _hash_source_description(context: dict[str, Any]) -> str:
        """Hash the source description used to build a request."""
        description = str(context.get("existing_description") or "")
        return hashlib.sha256(description.encode("utf-8")).hexdigest()

    def _get_audit_template_snapshot(self) -> dict[str, Any]:
        """Return the selected task identity and a stable content hash."""
        template = self._find_task_template(self.template_combo.currentData())
        if template is None:
            content = self.custom_prompt_edit.toPlainText()
            return {
                "template_id": None,
                "name": "Custom task",
                "intent": TaskIntent.GENERAL.value,
                "source": "custom",
                "content_hash": hashlib.sha256(
                    content.encode("utf-8")
                ).hexdigest(),
            }

        return {
            "template_id": template.template_id,
            "name": template.name,
            "intent": template.intent.value,
            "source": template.source.value,
            "content_hash": hashlib.sha256(
                template.content.encode("utf-8")
            ).hexdigest(),
        }

    def _construct_prompt(self, context_str: str, user_prompt: str) -> Dict[str, str]:
        """Construct the final prompt with persona and delimited context.

        .. deprecated::
            Use :class:`~src.services.prompt_builder.PromptBuilder` instead.
            Kept for backward compatibility with external callers.

        Args:
            context_str: Formatted context string with entity/event details.
            user_prompt: User's custom prompt/task.

        Returns:
            Dict[str, str]: Structured prompt dictionary.

        """
        builder = PromptBuilder(system_prompt=self._get_system_prompt())
        return builder.construct_prompt(
            context_str,
            user_prompt,
            include_rag_placeholder=self.rag_cb.isChecked(),
            include_spatial_placeholder=self.spatial_cb.isChecked(),
        )

    def _start_generation(
        self,
        prompt: dict[str, str],
        temperature: float,
        db_path: Optional[str] = None,
        object_id: Optional[str] = None,
        object_type: Optional[str] = None,
    ) -> None:
        """Start generation in worker thread."""
        self._audit_interaction_id = new_interaction_id()
        self._audit_started_at = time.monotonic()
        self._audit_provider_id = self._get_provider_id()
        self._audit_template = self._get_audit_template_snapshot()
        self._audit_generation_logged = False

        # Update UI
        self.generate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status_label.setText("Generating...")
        self._last_spatial_context = None
        self._set_spatial_used_visible(False)

        # Prepare exclusion list (current entity name)
        exclude_names = []
        current_context = self._get_generation_context()
        if current_context and "name" in current_context:
            exclude_names.append(current_context["name"])

        spatial_enabled = self.spatial_cb.isChecked()
        active_map_id = self._resolve_active_map_id() if spatial_enabled else None

        # Create worker
        request = GenerationRequest(
            prompt=dict(prompt),
            max_tokens=self.max_tokens_spin.value(),
            temperature=temperature,
            db_path=db_path,
            rag_limit=self._get_rag_limit(),
            exclude_names=tuple(exclude_names),
            target_id=object_id,
            source_hash=self._generation_source_hash,
            object_type=object_type,
            active_map_id=active_map_id,
            spatial_enabled=spatial_enabled,
        )
        self._worker = GenerationWorker(
            self._current_provider,
            prompt,
            self.max_tokens_spin.value(),
            temperature,
            request=request,
        )

        # Connect signals
        self._worker.generation_complete.connect(self._on_generation_complete)
        self._worker.generation_error.connect(self._on_generation_error)
        self._worker.finished.connect(self._on_worker_finished)

        # Start worker
        self._worker.start()

    def _preview_spatial_context(
        self, db_path: str, context: dict
    ) -> Optional[str]:
        """Run the same spatial lookup the worker performs, for preview use."""
        object_id = context.get("object_id") or ""
        object_type = context.get("object_type") or ""
        active_map_id = self._resolve_active_map_id()
        if not (object_id and object_type and active_map_id):
            return None
        return lookup_spatial_context(
            db_path, object_id, object_type, active_map_id
        )

    def _resolve_active_map_id(self) -> Optional[str]:
        """Walk the widget tree to find the MainWindow's active map id.

        Uses :meth:`MapWidget.get_selected_map_id` via the main window's
        ``map_widget`` attribute. Returns ``None`` if the widget is not
        embedded under a main window that exposes a map widget — in that
        case the spatial-context feature cleanly stands down.
        """
        window = self.window()
        try:
            map_widget = getattr(window, "map_widget", None)
            if map_widget is None:
                return None
            getter = getattr(map_widget, "get_selected_map_id", None)
            if getter is None:
                return None
            map_id = getter()
            return str(map_id) if map_id else None
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("Failed to resolve active map id: %s", e)
            return None

    def _set_spatial_used_visible(self, visible: bool, *, has_context: bool = False) -> None:
        """Toggle visibility of the spatial-context transparency row.

        Args:
            visible: Whether to show the label at all.
            has_context: When True, the "Show" link is revealed so the user
                can inspect the injected text. When False, the label carries
                a muted "no spatial context" hint only.
        """
        self.spatial_used_label.setVisible(visible)
        self.spatial_show_btn.setVisible(visible and has_context)

    def _get_rag_limit(self) -> int:
        """Safely retrieve RAG limit from input."""
        try:
            return int(self.rag_limit_input.text())
        except (ValueError, AttributeError):
            return 3  # Default fallback

    # def _on_chunk_received(self, chunk: str):
    #     """Handle streaming chunk."""
    #     self.preview_text.appendPlainText(chunk)

    @Slot(object)
    def _on_generation_complete(self, reply: ModelReply) -> None:
        """Handle generation completion by showing review dialog."""
        text = reply.content
        logger.info(f"Generation complete. Received {len(text)} characters.")
        self.status_label.setText(f"Generated {len(text)} characters")
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        worker_prompt: GenerationPrompt | None = None
        worker_model = "unknown"
        worker_rag_context: Optional[str] = None
        worker_spatial_context: Optional[str] = None
        worker_spatial_requested = False
        parameters: dict[str, Any] = {}
        target: dict[str, Any] = {
            "target_id": self._generation_target_id,
            "source_hash": self._generation_source_hash,
        }
        if self._worker:
            worker_prompt = self._worker.prompt
            worker_rag_context = self._worker.rag_context_used
            worker_spatial_context = self._worker.spatial_context_used
            worker_spatial_requested = self._worker.spatial_enabled
            parameters = {
                "max_tokens": self._worker.max_tokens,
                "temperature": self._worker.temperature,
                "rag_limit": self._worker.rag_limit,
                "rag_enabled": self._worker.db_path is not None,
                "spatial_enabled": self._worker.spatial_enabled,
            }
            target.update(
                {
                    "object_type": self._worker.object_type,
                    "active_map_id": self._worker.active_map_id,
                }
            )
            try:
                worker_model = self._worker.provider.get_model_name()
            except Exception:
                pass

        audit_path = get_world_audit_log_path(self._current_db_path)
        interaction_id = self._audit_interaction_id or new_interaction_id()
        if worker_prompt is not None:
            duration_ms = None
            if self._audit_started_at is not None:
                duration_ms = int(
                    (time.monotonic() - self._audit_started_at) * 1000
                )
            log_generation_event(
                interaction_id=interaction_id,
                prompt=worker_prompt,
                source="LLMGenerationWidget",
                provider=self._audit_provider_id,
                model=reply.model or worker_model,
                status="success",
                response=reply.to_dict(),
                parameters=parameters,
                template=self._audit_template,
                target=target,
                context={
                    "rag": worker_rag_context,
                    "spatial": worker_spatial_context,
                },
                duration_ms=duration_ms,
                audit_path=audit_path,
            )
            self._audit_generation_logged = True

        current_context = self._get_generation_context() or {}
        current_target_id = str(current_context.get("object_id") or "") or None
        current_source_hash = self._hash_source_description(current_context)
        if (
            current_target_id != self._generation_target_id
            or current_source_hash != self._generation_source_hash
        ):
            log_review_event(
                interaction_id=interaction_id,
                action="context_changed",
                raw_text=text,
                presented_text=text,
                reviewed_text=text,
                source="LLMGenerationWidget",
                audit_path=audit_path,
            )
            self.status_label.setText("Result discarded: editor context changed")
            QMessageBox.warning(
                self,
                "Generation Context Changed",
                "The selected item or its description changed while the model was "
                "working. The result was not applied. Generate again from the "
                "current editor state.",
            )
            return

        # Update the post-generation spatial-context transparency row.
        self._update_spatial_used_label(
            worker_spatial_requested, worker_spatial_context
        )

        # Show review dialog
        from src.gui.dialogs.generation_review_dialog import (
            GenerationReviewDialog,
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

        dialog = GenerationReviewDialog(
            generated_text=filtered_text,
            parent=self,
            reply=reply,
        )
        dialog.exec()  # Result code not needed, using dialog.get_result()

        result = dialog.get_review_result()
        result = replace(
            result,
            target_id=self._generation_target_id,
            source_hash=self._generation_source_hash,
        )
        final_text = result.text
        audit_action = dialog.action.value if dialog.action else "closed"
        log_review_event(
            interaction_id=interaction_id,
            action=audit_action,
            raw_text=text,
            presented_text=filtered_text,
            reviewed_text=final_text,
            source="LLMGenerationWidget",
            rating=result.rating or None,
            comment=result.comment or None,
            audit_path=audit_path,
        )

        if result.action != GenerationApplyMode.DISCARD:
            self.text_generated.emit(result)

    def _audit_unsuccessful_generation(
        self, status: str, error: str | None = None
    ) -> None:
        """Record an error or cancellation once for the active generation."""
        worker = self._worker
        if (
            worker is None
            or self._audit_generation_logged
            or self._audit_interaction_id is None
        ):
            return

        model = "unknown"
        try:
            model = worker.provider.get_model_name()
        except Exception:
            pass

        duration_ms = None
        if self._audit_started_at is not None:
            duration_ms = int((time.monotonic() - self._audit_started_at) * 1000)
        log_generation_event(
            interaction_id=self._audit_interaction_id,
            prompt=worker.prompt,
            source="LLMGenerationWidget",
            provider=self._audit_provider_id,
            model=model,
            status=status,
            error=error,
            parameters={
                "max_tokens": worker.max_tokens,
                "temperature": worker.temperature,
                "rag_limit": worker.rag_limit,
                "rag_enabled": worker.db_path is not None,
                "spatial_enabled": worker.spatial_enabled,
            },
            template=self._audit_template,
            target={
                "target_id": self._generation_target_id,
                "source_hash": self._generation_source_hash,
                "object_type": worker.object_type,
                "active_map_id": worker.active_map_id,
            },
            context={
                "rag": worker.rag_context_used,
                "spatial": worker.spatial_context_used,
            },
            duration_ms=duration_ms,
            audit_path=get_world_audit_log_path(self._current_db_path),
        )
        self._audit_generation_logged = True

    @Slot(str)
    def _on_generation_error(self, error: str) -> None:
        """Handle generation error."""
        self._audit_unsuccessful_generation("error", error)
        logger.error(f"Generation error: {error}")
        self.status_label.setText(f"Error: {error}")
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    @Slot()
    def _on_worker_finished(self) -> None:
        """Delete a worker only after its thread has actually stopped."""
        worker = self.sender()
        if isinstance(worker, GenerationWorker):
            if worker._cancelled:
                self._audit_unsuccessful_generation("cancelled")
                self.status_label.setText("Generation cancelled")
                self.generate_btn.setEnabled(True)
            worker.deleteLater()
            if worker is self._worker:
                self._worker = None

    def _update_spatial_used_label(
        self, spatial_requested: bool, context_text: Optional[str]
    ) -> None:
        """Render the post-generation spatial-context transparency line.

        Three states:

        * Feature disabled (checkbox off): hide the row.
        * Enabled but no context injected: show a muted "no spatial context"
          hint that nudges the user toward richer map data.
        * Enabled and context injected: show a summary + clickable "Show"
          link that opens the full injected text in a modal dialog.
        """
        if not spatial_requested:
            self._last_spatial_context = None
            self._set_spatial_used_visible(False)
            return

        if context_text:
            self._last_spatial_context = context_text
            summary = self._summarise_spatial_context(context_text)
            self.spatial_used_label.setText(f"Spatial context used · {summary}")
            self._set_spatial_used_visible(True, has_context=True)
        else:
            self._last_spatial_context = None
            self.spatial_used_label.setText(
                "No spatial context available for this entity on the active map."
            )
            self._set_spatial_used_visible(True, has_context=False)

    @staticmethod
    def _summarise_spatial_context(context_text: str) -> str:
        """Produce a one-line summary of an injected spatial-context block."""
        for line in context_text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("["):
                return stripped
        return "details available"

    @Slot()
    def _on_show_spatial_context_clicked(self) -> None:
        """Open a modal dialog showing the raw injected spatial-context text."""
        if not self._last_spatial_context:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Spatial Context Used")
        dlg.resize(520, 360)
        dlg.setStyleSheet(StyleHelper.get_dialog_base_style())
        layout = QVBoxLayout(dlg)
        info = QLabel(
            "Exact text inserted into the prompt in place of "
            "{{SPATIAL_CONTEXT}}."
        )
        info.setStyleSheet(StyleHelper.get_preview_label_style())
        layout.addWidget(info)
        text_edit = QPlainTextEdit()
        text_edit.setPlainText(self._last_spatial_context)
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet(
            f"{StyleHelper.get_input_field_style()}font-family: Consolas, monospace;"
        )
        layout.addWidget(text_edit)
        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        close_btn.setStyleSheet(StyleHelper.get_primary_button_style())
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        dlg.exec()

    @Slot()
    def _on_cancel_clicked(self) -> None:
        """Handle cancel button click."""
        if self._worker:
            self._worker.cancel()

        self.status_label.setText("Cancelling generation...")
        self.generate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

    def _shutdown_worker(self) -> None:
        """Request cancellation and retain the thread until it has stopped."""
        worker = self._worker
        if worker is None or not worker.isRunning():
            return
        worker.cancel()
        if not worker.wait(5000):
            logger.warning("Generation worker did not stop within shutdown timeout")

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop active generation before the widget can be destroyed."""
        self._shutdown_worker()
        super().closeEvent(event)

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
                "3. If the issue persists, save your work and restart",
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
                "2. Click Preview Context again to see what will be sent",
            )
            return

        # Build prompt using PromptBuilder (same as generate path)
        builder = PromptBuilder(system_prompt=self._get_system_prompt())
        context_str = builder.build_context_string(context)
        user_prompt = builder.substitute_variables(user_prompt, context)
        prompt = builder.construct_prompt(
            context_str,
            user_prompt,
            include_rag_placeholder=self.rag_cb.isChecked(),
            include_spatial_placeholder=self.spatial_cb.isChecked(),
            object_type=str(context.get("object_type") or ""),
        )

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
            curr: QObject | None = self
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
                    if isinstance(curr, QWidget):
                        window = curr.window()
                        if window != curr:
                            curr = window
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
                f"[Context]\n{rag_context}"
                if rag_context
                else "[Context]\n(No results found for query)"
            )
            prompt["user"] = user_msg.replace("{{RAG_CONTEXT}}", replacement)

        # Resolve spatial context for preview, mirroring the worker's path
        if self.spatial_cb.isChecked() and db_path:
            spatial_text = self._preview_spatial_context(db_path, context)
            replacement = (
                spatial_text
                if spatial_text
                else "[Spatial Context]\n(No spatial context available)"
            )
            prompt["user"] = prompt["user"].replace(
                "{{SPATIAL_CONTEXT}}", replacement
            )

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

        .. deprecated::
            Use :class:`~src.services.prompt_builder.PromptBuilder` instead.
            Kept for backward compatibility with external callers.

        Args:
            user_prompt: Raw user instruction.
            context: Context dictionary from editor.

        Returns:
            str: Substituted prompt.

        """
        return PromptBuilder().substitute_variables(user_prompt, context)
