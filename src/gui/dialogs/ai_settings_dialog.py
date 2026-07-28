"""AI Settings Dialog.

Provides configuration for AI features, including Search Index status and attribute
exclusion.
"""

import logging
import uuid
from typing import Optional

from PySide6.QtCore import Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.ai_generation import (
    AIGenerationPreferences,
    TaskIntent,
    TaskTemplate,
    TaskTemplateSource,
)
from src.core.summary_data import DEFAULT_SUMMARY_PROMPT
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.prompt_editor import PromptEditorWidget
from src.services.lmstudio_config import (
    DEFAULT_LMSTUDIO_BASE_URL,
    discover_lmstudio_models,
    normalize_lmstudio_base_url,
)
from src.services.task_template_catalog import (
    TaskTemplateCatalog,
    TaskTemplateValidationError,
)

logger = logging.getLogger(__name__)


class LMStudioDiscoveryWorker(QThread):
    """Discover LM Studio models without blocking the Qt main thread."""

    models_discovered = Signal(object)
    discovery_failed = Signal(str)

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout

    def run(self) -> None:
        """Fetch model identifiers from the OpenAI-compatible API."""
        try:
            models = discover_lmstudio_models(
                self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
            )
            self.models_discovered.emit(models)
        except Exception as exc:
            self.discovery_failed.emit(str(exc))


class AISettingsDialog(QDialog):
    """Dialog for AI Search settings and index status."""

    rebuild_index_requested = Signal(str)  # object_type ('entity', 'event', 'all')
    index_status_requested = Signal()  # Request to refresh index status
    settings_saved = Signal()  # Emitted after settings are persisted to QSettings
    task_templates_changed = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the AI Settings Dialog.

        Args:
            parent: Parent widget.

        """
        super().__init__(parent)
        self.setWindowTitle("AI Settings")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)
        # self.setAttribute(
        #     Qt.WidgetAttribute.WA_DeleteOnClose, True
        # )  # Removed to prevent RuntimeError on re-open

        self._initializing = True
        self._discovery_worker: LMStudioDiscoveryWorker | None = None
        self._task_templates: tuple[TaskTemplate, ...] = ()
        self._editing_template_id: str | None = None
        self._template_editor_dirty = False
        self._restoring_template_selection = False
        self._task_template_catalog = TaskTemplateCatalog()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._shutdown_discovery)
        logger.info("Initializing AI Settings Dialog")

        # Main layout
        main_layout = QVBoxLayout(self)

        # Main layout (Horizontal split)
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        # Sidebar (Left)
        self.sidebar_list = QListWidget()
        self.sidebar_list.setFixedWidth(200)
        self.sidebar_list.setSpacing(4)
        self.sidebar_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.sidebar_list.setStyleSheet(
            """
            QListWidget {
                background-color: #2b2b2b;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px;
                outline: none;
            }
            QListWidget::item {
                padding: 12px;
                border-radius: 4px;
                color: #b0b0b0;
                font-size: 13px;
            }
            QListWidget::item:selected {
                background-color: #3d3d3d;
                color: #ffffff;
                font-weight: bold;
                border-left: 3px solid #3498db;
            }
            QListWidget::item:hover {
                background-color: #323232;
            }
        """
        )

        # Add sidebar items
        self.sidebar_list.addItem(QListWidgetItem("Generative AI"))
        self.sidebar_list.addItem(QListWidgetItem("Knowledge Base"))
        self.sidebar_list.addItem(QListWidgetItem("Prompts & Persona"))
        self.sidebar_list.addItem(QListWidgetItem("Task Templates"))

        content_layout.addWidget(self.sidebar_list)

        # Pages (Right)
        self.pages_stack = QStackedWidget()
        content_layout.addWidget(self.pages_stack)

        # Connect sidebar navigation
        self.sidebar_list.currentRowChanged.connect(self.pages_stack.setCurrentIndex)

        # Create Pages
        self.pages_stack.addWidget(self._create_generative_ai_page())
        self.pages_stack.addWidget(self._create_knowledge_base_page())
        self.pages_stack.addWidget(self._create_prompts_page())
        self.pages_stack.addWidget(self._create_templates_page())

        # Select first item
        self.sidebar_list.setCurrentRow(0)

        # Button box
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("primary_btn")  # For styling if needed
        ok_btn.setStyleSheet(StyleHelper.get_primary_button_style())
        ok_btn.clicked.connect(self._on_ok_clicked)
        btn_box.addWidget(ok_btn)

        main_layout.addLayout(btn_box)

        # Save status label (autosave feedback)
        self.save_status_label = QLabel("")
        self.save_status_label.setStyleSheet(
            "color: #27ae60; font-size: 11px; font-style: italic;"
        )
        self.save_status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(self.save_status_label)

        # Autohide timer for save status
        self._status_hide_timer = QTimer(self)
        self._status_hide_timer.setSingleShot(True)
        self._status_hide_timer.timeout.connect(
            lambda: self.save_status_label.setText("")
        )

        # Load settings
        self.load_settings()
        self._initializing = False

    @Slot()
    def _on_ok_clicked(self) -> None:
        """Handle OK button click."""
        self._show_save_status("Saving...")
        self.save_settings()
        self._show_save_status("Saved")
        self.accept()

    def reject(self) -> None:
        """Protect unsaved world-template edits when closing the dialog."""
        if self._confirm_discard_template_changes():
            super().reject()

    def _create_generative_ai_page(self) -> QWidget:
        """Create the Generative AI (Text Generation) page."""
        page = QWidget()
        main_layout = QVBoxLayout(page)
        StyleHelper.apply_standard_list_spacing(main_layout)

        # === Text Generation Providers Section ===
        gen_group = QGroupBox("Text Generation Providers")
        gen_layout = QVBoxLayout(gen_group)
        StyleHelper.apply_standard_list_spacing(gen_layout)

        # Gen Provider selection
        gen_provider_layout = QHBoxLayout()
        gen_provider_layout.addWidget(QLabel("Provider:"))
        self.gen_provider_combo = QComboBox()
        self.gen_provider_combo.addItems(
            ["LM Studio", "OpenAI", "Google Vertex AI", "Anthropic Claude"]
        )
        for index in range(1, self.gen_provider_combo.count()):
            item = self.gen_provider_combo.model().item(index)
            if item is not None:
                item.setEnabled(False)
                item.setToolTip("Cloud providers are not enabled in this release")
        self.gen_provider_combo.currentIndexChanged.connect(
            self._on_gen_provider_changed
        )
        self.gen_provider_combo.currentIndexChanged.connect(self.save_settings)
        gen_provider_layout.addWidget(self.gen_provider_combo, stretch=1)
        gen_layout.addLayout(gen_provider_layout)

        # Stacked widget for provider-specific settings
        self.gen_provider_stack = QStackedWidget()

        # [LM Studio Gen Page]
        lm_gen_page = QGroupBox()
        lm_gen_form = QFormLayout(lm_gen_page)
        StyleHelper.apply_standard_list_spacing(lm_gen_form)
        self.lm_gen_enabled = QCheckBox("Enable for this world")
        self.lm_gen_enabled.setChecked(True)
        self.lm_gen_enabled.toggled.connect(self.save_settings)
        lm_gen_form.addRow("Enabled:", self.lm_gen_enabled)
        self.lm_gen_use_chat_api = QCheckBox("Use Chat API (recommended)")
        self.lm_gen_use_chat_api.setChecked(True)
        self.lm_gen_use_chat_api.setToolTip(
            "Use /v1/chat/completions with messages format. "
            "Recommended for modern models."
        )
        self.lm_gen_use_chat_api.toggled.connect(self.save_settings)
        lm_gen_form.addRow("Chat Mode:", self.lm_gen_use_chat_api)
        self.lm_gen_url_input = QLineEdit()
        self.lm_gen_url_input.setPlaceholderText(DEFAULT_LMSTUDIO_BASE_URL)
        self.lm_gen_url_input.setToolTip(
            "LM Studio server address. Kraken derives /v1/models and API endpoints."
        )
        self.lm_gen_url_input.editingFinished.connect(
            lambda: self._sync_lmstudio_base_url(self.lm_gen_url_input)
        )
        lm_gen_form.addRow("Server URL:", self.lm_gen_url_input)
        self.btn_test_lm_gen = QPushButton("Refresh Models")
        self.btn_test_lm_gen.setFixedWidth(120)
        self.btn_test_lm_gen.clicked.connect(
            lambda: self._test_connection("lmstudio", "generate")
        )
        lm_gen_form.addRow("", self.btn_test_lm_gen)
        self.lm_gen_model_input = QComboBox()
        self.lm_gen_model_input.setEditable(True)
        self.lm_gen_model_input.setPlaceholderText("e.g. mistral-7b-instruct")
        if self.lm_gen_model_input.lineEdit() is not None:
            self.lm_gen_model_input.lineEdit().editingFinished.connect(
                self.save_settings
            )
        self.lm_gen_model_input.currentIndexChanged.connect(self.save_settings)
        lm_gen_form.addRow("Model:", self.lm_gen_model_input)
        lm_gen_help = QLabel(
            "Choose the loaded text-generation model Kraken should request."
        )
        lm_gen_help.setWordWrap(True)
        lm_gen_form.addRow("", lm_gen_help)
        self.gen_provider_stack.addWidget(lm_gen_page)

        # [OpenAI Gen Page]
        openai_gen_page = QGroupBox()
        openai_gen_form = QFormLayout(openai_gen_page)
        StyleHelper.apply_standard_list_spacing(openai_gen_form)
        openai_notice = QLabel("Cloud providers are visible for future support only.")
        openai_notice.setWordWrap(True)
        openai_gen_form.addRow(openai_notice)
        self.openai_gen_enabled = QCheckBox("Enable for this world")
        self.openai_gen_enabled.toggled.connect(self.save_settings)
        openai_gen_form.addRow("Enabled:", self.openai_gen_enabled)
        self.openai_api_key_input = QLineEdit()
        self.openai_api_key_input.setPlaceholderText("sk-...")
        self.openai_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_api_key_input.editingFinished.connect(self.save_settings)
        openai_gen_form.addRow("API Key:", self.openai_api_key_input)
        self.openai_model_input = QLineEdit()
        self.openai_model_input.setPlaceholderText("gpt-3.5-turbo")
        self.openai_model_input.editingFinished.connect(self.save_settings)
        openai_gen_form.addRow("Model:", self.openai_model_input)
        self.gen_provider_stack.addWidget(openai_gen_page)
        openai_gen_page.setEnabled(False)

        # [Google Gen Page]
        google_gen_page = QGroupBox()
        google_gen_form = QFormLayout(google_gen_page)
        StyleHelper.apply_standard_list_spacing(google_gen_form)
        google_notice = QLabel("Cloud providers are visible for future support only.")
        google_notice.setWordWrap(True)
        google_gen_form.addRow(google_notice)
        self.google_gen_enabled = QCheckBox("Enable for this world")
        self.google_gen_enabled.toggled.connect(self.save_settings)
        google_gen_form.addRow("Enabled:", self.google_gen_enabled)
        self.google_project_input = QLineEdit()
        self.google_project_input.setPlaceholderText("your-project-id")
        google_gen_form.addRow("Project ID:", self.google_project_input)
        self.google_location_input = QLineEdit()
        self.google_location_input.setPlaceholderText("us-central1")
        google_gen_form.addRow("Location:", self.google_location_input)
        self.google_model_input = QLineEdit()
        self.google_model_input.setPlaceholderText("text-bison@001")
        self.google_model_input.editingFinished.connect(self.save_settings)
        google_gen_form.addRow("Model:", self.google_model_input)
        self.google_creds_input = QLineEdit()
        self.google_creds_input.setPlaceholderText("/path/to/credentials.json")
        self.google_creds_input.editingFinished.connect(self.save_settings)
        google_gen_form.addRow("Credentials Path:", self.google_creds_input)
        self.gen_provider_stack.addWidget(google_gen_page)
        google_gen_page.setEnabled(False)

        # [Anthropic Gen Page]
        anthropic_gen_page = QGroupBox()
        anthropic_gen_form = QFormLayout(anthropic_gen_page)
        StyleHelper.apply_standard_list_spacing(anthropic_gen_form)
        anthropic_notice = QLabel(
            "Cloud providers are visible for future support only."
        )
        anthropic_notice.setWordWrap(True)
        anthropic_gen_form.addRow(anthropic_notice)
        self.anthropic_gen_enabled = QCheckBox("Enable for this world")
        self.anthropic_gen_enabled.toggled.connect(self.save_settings)
        anthropic_gen_form.addRow("Enabled:", self.anthropic_gen_enabled)
        self.anthropic_api_key_input = QLineEdit()
        self.anthropic_api_key_input.setPlaceholderText("sk-ant-...")
        self.anthropic_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        anthropic_gen_form.addRow("API Key:", self.anthropic_api_key_input)
        self.anthropic_model_input = QLineEdit()
        self.anthropic_model_input.setPlaceholderText("claude-3-haiku-20240307")
        self.anthropic_model_input.editingFinished.connect(self.save_settings)
        anthropic_gen_form.addRow("Model:", self.anthropic_model_input)
        self.gen_provider_stack.addWidget(anthropic_gen_page)
        anthropic_gen_page.setEnabled(False)

        gen_layout.addWidget(self.gen_provider_stack)
        main_layout.addWidget(gen_group)

        # === Generation Parameters (Moved from old options tab) ===
        params_group = QGroupBox("Parameters")
        params_layout = QFormLayout(params_group)
        StyleHelper.apply_standard_list_spacing(params_layout)

        self.max_tokens_input = QSpinBox()
        self.max_tokens_input.setRange(100, 100000)
        self.max_tokens_input.setValue(512)
        self.max_tokens_input.setToolTip("Maximum tokens to generate per request")
        self.max_tokens_input.valueChanged.connect(self.save_settings)
        params_layout.addRow("Max Tokens:", self.max_tokens_input)

        self.temperature_input = QSpinBox()
        self.temperature_input.setRange(0, 200)
        self.temperature_input.setValue(70)
        self.temperature_input.setSuffix("%")
        self.temperature_input.setToolTip("Temperature (0-200%, where 100% = 1.0)")
        self.temperature_input.valueChanged.connect(self.save_settings)
        params_layout.addRow("Temperature:", self.temperature_input)

        self.enable_audit_log = QCheckBox("Enable audit logging")
        self.enable_audit_log.setToolTip(
            "Log all generation requests and responses for auditing"
        )
        self.enable_audit_log.toggled.connect(self.save_settings)
        params_layout.addRow("Audit Log:", self.enable_audit_log)

        main_layout.addWidget(params_group)

        # Clear settings button (Local to Generative AI?)
        # Let's keep it global-ish but on the relevant pages or just here
        clear_btn = QPushButton("Clear All AI Settings")
        clear_btn.setStyleSheet("QPushButton { color: #e74c3c; }")
        clear_btn.clicked.connect(self._on_clear_generation_settings)
        clear_btn.setToolTip("Clear all stored API keys and settings")
        main_layout.addWidget(clear_btn)

        main_layout.addStretch()

        return page

    def _create_knowledge_base_page(self) -> QWidget:
        """Create the Knowledge Base (Embeddings & Index) page."""
        page = QWidget()
        main_layout = QVBoxLayout(page)
        StyleHelper.apply_standard_list_spacing(main_layout)

        # === Embedding Configuration Section ===
        llm_group = QGroupBox("Embedding Configuration")
        llm_layout = QVBoxLayout(llm_group)
        StyleHelper.apply_standard_list_spacing(llm_layout)

        # Provider selection
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(
            ["Sentence Transformers (default)", "LM Studio (optional upgrade)"]
        )
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self.provider_combo.currentIndexChanged.connect(self.save_settings)
        provider_layout.addWidget(self.provider_combo, stretch=1)
        llm_layout.addLayout(provider_layout)

        # Stacked widget for provider-specific settings
        self.provider_stack = QStackedWidget()

        # Sentence Transformers settings page (index 0 — default)
        st_page = QGroupBox()
        st_form = QFormLayout(st_page)
        StyleHelper.apply_standard_list_spacing(st_form)
        st_info_label = QLabel(
            "Runs locally with no external service required. "
            "The model is downloaded automatically on first use (~90 MB)."
        )
        st_info_label.setWordWrap(True)
        st_info_label.setStyleSheet("color: #27ae60; font-size: 11px;")
        st_form.addRow(st_info_label)
        self.st_model_input = QLineEdit()
        self.st_model_input.setPlaceholderText("all-MiniLM-L6-v2")
        self.st_model_input.editingFinished.connect(self.save_settings)
        st_form.addRow("Model:", self.st_model_input)
        self.provider_stack.addWidget(st_page)

        # LM Studio settings page (index 1 — optional upgrade)
        lm_studio_page = QGroupBox()
        lm_studio_form = QFormLayout(lm_studio_page)
        StyleHelper.apply_standard_list_spacing(lm_studio_form)
        lm_info_label = QLabel(
            "Optional upgrade: requires LM Studio to be running locally with an "
            "embedding model loaded. Provides higher-quality embeddings."
        )
        lm_info_label.setWordWrap(True)
        lm_info_label.setStyleSheet("font-size: 11px;")
        lm_studio_form.addRow(lm_info_label)
        self.lm_url_input = QLineEdit()
        self.lm_url_input.setPlaceholderText(DEFAULT_LMSTUDIO_BASE_URL)
        self.lm_url_input.setToolTip(
            "Uses the same LM Studio server as text generation."
        )
        self.lm_url_input.editingFinished.connect(
            lambda: self._sync_lmstudio_base_url(self.lm_url_input)
        )
        lm_studio_form.addRow("Server URL:", self.lm_url_input)
        self.lm_model_input = QComboBox()
        self.lm_model_input.setEditable(True)
        self.lm_model_input.setPlaceholderText("e.g. nomic-embed-text-v1.5")
        if self.lm_model_input.lineEdit() is not None:
            self.lm_model_input.lineEdit().editingFinished.connect(self.save_settings)
        self.lm_model_input.currentIndexChanged.connect(self.save_settings)
        lm_studio_form.addRow("Embedding Model:", self.lm_model_input)
        lm_model_help = QLabel(
            "Choose a separate embedding-capable model for semantic search."
        )
        lm_model_help.setWordWrap(True)
        lm_studio_form.addRow("", lm_model_help)
        self.lm_api_key_input = QLineEdit()
        self.lm_api_key_input.setPlaceholderText("Optional")
        self.lm_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.lm_api_key_input.editingFinished.connect(self.save_settings)
        lm_studio_form.addRow("API Key:", self.lm_api_key_input)
        self.btn_test_lm_embed = QPushButton("Refresh Models")
        self.btn_test_lm_embed.setFixedWidth(120)
        self.btn_test_lm_embed.clicked.connect(
            lambda: self._test_connection("lmstudio", "embed")
        )
        lm_studio_form.addRow("", self.btn_test_lm_embed)
        self.lm_timeout_input = QSpinBox()
        self.lm_timeout_input.setRange(5, 300)
        self.lm_timeout_input.setValue(30)
        self.lm_timeout_input.setSuffix(" seconds")
        self.lm_timeout_input.valueChanged.connect(self.save_settings)
        lm_studio_form.addRow("Timeout:", self.lm_timeout_input)
        self.provider_stack.addWidget(lm_studio_page)

        llm_layout.addWidget(self.provider_stack)
        main_layout.addWidget(llm_group)

        # === Index Status Section ===
        index_group = QGroupBox("Index Management")
        index_layout = QVBoxLayout(index_group)
        StyleHelper.apply_standard_list_spacing(index_layout)

        # Status display
        status_grid = QVBoxLayout()
        self.lbl_model = QLabel("Model: --")
        status_grid.addWidget(self.lbl_model)
        self.lbl_indexed_count = QLabel("Indexed: --")
        status_grid.addWidget(self.lbl_indexed_count)
        self.lbl_last_indexed = QLabel("Last Updated: --")
        status_grid.addWidget(self.lbl_last_indexed)
        index_layout.addLayout(status_grid)

        # Rebuild controls
        rebuild_layout = QHBoxLayout()
        self.rebuild_combo = QComboBox()
        self.rebuild_combo.addItems(["All", "Entities", "Events"])
        rebuild_layout.addWidget(self.rebuild_combo, stretch=1)
        self.btn_rebuild = QPushButton("Rebuild Index")
        self.btn_rebuild.clicked.connect(self._on_rebuild_clicked)
        rebuild_layout.addWidget(self.btn_rebuild, stretch=1)
        index_layout.addLayout(rebuild_layout)

        # Progress label (hidden by default)
        self.lbl_rebuild_progress = QLabel("")
        self.lbl_rebuild_progress.setVisible(False)
        index_layout.addWidget(self.lbl_rebuild_progress)

        self.btn_refresh_status = QPushButton("Refresh Status")
        self.btn_refresh_status.clicked.connect(self.index_status_requested.emit)
        index_layout.addWidget(self.btn_refresh_status)
        main_layout.addWidget(index_group)

        # === Auto-Index Section ===
        auto_group = QGroupBox("Automatic Indexing")
        auto_layout = QVBoxLayout(auto_group)
        StyleHelper.apply_standard_list_spacing(auto_layout)
        self.chk_auto_index = QCheckBox("Auto-index on save")
        self.chk_auto_index.setToolTip(
            "Re-embed entities and events immediately after each save."
        )
        self.chk_auto_index.stateChanged.connect(self.save_settings)
        auto_layout.addWidget(self.chk_auto_index)
        main_layout.addWidget(auto_group)

        # === Search Settings Section ===
        settings_group = QGroupBox("Search Rules")
        settings_layout = QVBoxLayout(settings_group)
        StyleHelper.apply_standard_list_spacing(settings_layout)

        settings_layout.addWidget(QLabel("Excluded Attributes (comma-separated):"))
        self.excluded_attrs_input = QLineEdit()
        self.excluded_attrs_input.setPlaceholderText("e.g. secret_notes, internal_id")
        self.excluded_attrs_input.setToolTip(
            "Attributes starting with '_' are automatically excluded."
        )
        self.excluded_attrs_input.editingFinished.connect(self.save_settings)
        settings_layout.addWidget(self.excluded_attrs_input)
        main_layout.addWidget(settings_group)

        main_layout.addStretch()

        return page

    def _create_prompts_page(self) -> QWidget:
        """Create the Prompts & Persona page."""
        page = QWidget()
        main_layout = QVBoxLayout(page)
        StyleHelper.apply_standard_list_spacing(main_layout)

        # System Prompt
        system_group = QGroupBox("Persona")
        system_layout = QVBoxLayout(system_group)
        StyleHelper.apply_compact_spacing(system_layout)

        self.system_prompt_edit = PromptEditorWidget()
        self.system_prompt_edit.setPlaceholderText(
            "Enter the persona that defines the LLM's role and behavior..."
        )
        self.system_prompt_edit.setMinimumHeight(120)  # Taller for reading
        self.system_prompt_edit.setToolTip(
            "The persona defines how the LLM should behave and respond. "
            "Task templates provide a separate instruction for the current request."
        )
        # Default prompt
        default_prompt = (
            "You are an expert fantasy world-builder assisting a user in creating a "
            "rich and immersive setting. Your tone is descriptive, evocative, and "
            "consistent with high-fantasy literature.\n\n"
            "IMPORTANT: Time in this world is represented as floating-point numbers "
            "where 1.0 = 1 day. The decimal portion represents time within the day "
            "(e.g., 0.5 = noon). When referencing dates or durations, understand "
            "that event dates and durations use this numeric format."
        )
        self.system_prompt_edit.set_default_text(default_prompt)
        self.system_prompt_edit.set_variables(
            ["{type}", "{name}", "{description}", "{lore_date}"]
        )
        system_layout.addWidget(self.system_prompt_edit)
        self.system_prompt_edit.textChanged.connect(self.save_settings)
        main_layout.addWidget(system_group)

        # Summary Prompt
        summary_group = QGroupBox("Summary Prompt")
        summary_layout = QVBoxLayout(summary_group)
        StyleHelper.apply_compact_spacing(summary_layout)

        self.summary_prompt_edit = PromptEditorWidget()
        self.summary_prompt_edit.setPlaceholderText(
            "Enter the prompt used to summarize Entities and Events..."
        )
        self.summary_prompt_edit.setMinimumHeight(120)
        self.summary_prompt_edit.setToolTip(
            "This prompt instructs the LLM how to summarize worldbuilding items."
        )
        self.summary_prompt_edit.set_variables(
            ["{type}", "{name}", "{description}", "{lore_date}"]
        )
        self.summary_prompt_edit.set_default_text(DEFAULT_SUMMARY_PROMPT)
        summary_layout.addWidget(self.summary_prompt_edit)
        self.summary_prompt_edit.textChanged.connect(self.save_settings)
        main_layout.addWidget(summary_group)

        # Summary Generation Parameters
        summary_params_group = QGroupBox("Summary Parameters")
        summary_params_layout = QFormLayout(summary_params_group)
        StyleHelper.apply_compact_spacing(summary_params_layout)

        self.summary_max_tokens_input = QSpinBox()
        self.summary_max_tokens_input.setRange(100, 100000)
        self.summary_max_tokens_input.setValue(2048)
        self.summary_max_tokens_input.setToolTip(
            "Provider safety ceiling for summary generation. Visible summaries "
            "are separately limited to 30% of the description and 150 words.\n"
            "Reasoning models (e.g. DeepSeek R1) need higher values\n"
            "because <think> tags consume part of the budget."
        )
        self.summary_max_tokens_input.valueChanged.connect(self.save_settings)
        summary_params_layout.addRow(
            "Summary Max Tokens:", self.summary_max_tokens_input
        )

        self.summary_temperature_input = QSpinBox()
        self.summary_temperature_input.setRange(0, 200)
        self.summary_temperature_input.setValue(0)  # Default to 0 for determinism
        self.summary_temperature_input.setToolTip(
            "Temperature for summary generation (0-200, representing 0.0-2.0).\n"
            "Lower values (e.g., 0) produce more deterministic and focused results.\n"
            "Higher values produce more creative but less predictable results."
        )
        self.summary_temperature_input.valueChanged.connect(self.save_settings)
        summary_params_layout.addRow(
            "Summary Temperature:", self.summary_temperature_input
        )
        main_layout.addWidget(summary_params_group)

        # Output Filters
        filters_group = QGroupBox("Output Control")
        filters_layout = QVBoxLayout(filters_group)
        StyleHelper.apply_compact_spacing(filters_layout)

        # Filter reasoning tags checkbox
        self.filter_reasoning_cb = QCheckBox(
            "Filter reasoning tags (<think>, <reasoning>)"
        )
        self.filter_reasoning_cb.setChecked(True)
        self.filter_reasoning_cb.setToolTip(
            "Remove <think>, <thinking>, <reasoning> and similar tags from output."
        )
        self.filter_reasoning_cb.toggled.connect(self.save_settings)
        filters_layout.addWidget(self.filter_reasoning_cb)
        main_layout.addWidget(filters_group)  # BUG FIX: was missing!

        main_layout.addStretch()
        return page

    def _create_templates_page(self) -> QWidget:
        """Create the Task Templates management page."""
        page = QWidget()
        main_layout = QVBoxLayout(page)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Splitter for Master-Detail view
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: #3d3d3d; }")

        # === Left: Template List ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)

        lbl_list = QLabel("Task Templates")
        lbl_list.setStyleSheet("font-weight: bold; color: #b0b0b0;")
        left_layout.addWidget(lbl_list)

        self.template_list = QListWidget()
        self.template_list.setStyleSheet(
            """
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
                color: #cccccc;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: #ffffff;
            }
        """
        )
        self.template_list.currentItemChanged.connect(self._on_template_selected)
        left_layout.addWidget(self.template_list)

        # Actions below list
        list_actions = QHBoxLayout()
        self.btn_new_template = QPushButton("New")
        self.btn_new_template.clicked.connect(self._on_new_template)
        list_actions.addWidget(self.btn_new_template)
        self.btn_refresh_templates = QPushButton("Refresh")
        self.btn_refresh_templates.clicked.connect(self._refresh_templates_list)
        list_actions.addWidget(self.btn_refresh_templates)
        left_layout.addLayout(list_actions)

        splitter.addWidget(left_widget)

        # === Right: Editor ===
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)
        StyleHelper.apply_standard_list_spacing(right_layout)

        # Metadata form
        meta_group = QGroupBox("Template Metadata")
        meta_form = QFormLayout(meta_group)
        StyleHelper.apply_compact_spacing(meta_form)

        self.template_name_edit = QLineEdit()
        self.template_name_edit.setPlaceholderText("e.g. Revise — Preserve Tone")
        meta_form.addRow("Name:", self.template_name_edit)

        self.template_description_edit = QLineEdit()
        self.template_description_edit.setPlaceholderText(
            "Explain when this task is useful"
        )
        meta_form.addRow("Description:", self.template_description_edit)

        self.template_intent_combo = QComboBox()
        self.template_intent_combo.addItem("Create", TaskIntent.CREATE.value)
        self.template_intent_combo.addItem("Update", TaskIntent.UPDATE.value)
        self.template_intent_combo.addItem("General", TaskIntent.GENERAL.value)
        meta_form.addRow("Intent:", self.template_intent_combo)

        right_layout.addWidget(meta_group)

        # Content editor
        content_group = QGroupBox("Prompt Content")
        content_layout = QVBoxLayout(content_group)
        content_layout.setContentsMargins(4, 8, 4, 4)

        self.template_content_edit = PromptEditorWidget()
        self.template_content_edit.setPlaceholderText("Enter template content here...")
        self.template_content_edit.set_variables(
            ["{type}", "{name}", "{description}", "{lore_date}"]
        )
        content_layout.addWidget(self.template_content_edit)
        right_layout.addWidget(content_group, stretch=1)

        # Editor actions
        editor_actions = QHBoxLayout()
        self.btn_delete_template = QPushButton("Delete")
        self.btn_delete_template.setStyleSheet(
            StyleHelper.get_destructive_button_style()
        )
        self.btn_delete_template.clicked.connect(self._on_delete_template)
        editor_actions.addWidget(self.btn_delete_template)

        self.btn_duplicate_template = QPushButton("Duplicate to World")
        self.btn_duplicate_template.clicked.connect(self._on_duplicate_template)
        editor_actions.addWidget(self.btn_duplicate_template)

        editor_actions.addStretch()

        self.btn_save_template = QPushButton("Save Template")
        self.btn_save_template.setStyleSheet(
            "background-color: #3498db; color: white; font-weight: bold;"
        )
        self.btn_save_template.clicked.connect(self._on_save_template)
        editor_actions.addWidget(self.btn_save_template)

        right_layout.addLayout(editor_actions)

        splitter.addWidget(right_widget)

        # Set splitter sizes (30% / 70%)
        splitter.setSizes([200, 500])

        main_layout.addWidget(splitter)

        for editor in (
            self.template_name_edit,
            self.template_description_edit,
            self.template_content_edit,
        ):
            editor.textChanged.connect(self._mark_template_editor_dirty)
        self.template_intent_combo.currentIndexChanged.connect(
            self._mark_template_editor_dirty
        )

        self._set_template_editor_enabled(False)
        self._refresh_templates_list()

        return page

    @Slot()
    def _refresh_templates_list(self) -> None:
        """Render the coordinator-provided task-template snapshot."""
        selected_id = self._editing_template_id
        self._restoring_template_selection = True
        try:
            self.template_list.clear()
            for template in sorted(
                self._task_templates,
                key=lambda item: (
                    item.source != TaskTemplateSource.BUILT_IN,
                    item.intent.value,
                    item.name.casefold(),
                ),
            ):
                prefix = "🔒 " if template.source == TaskTemplateSource.BUILT_IN else ""
                item = QListWidgetItem(f"{prefix}{template.name}")
                item.setData(Qt.ItemDataRole.UserRole, template.template_id)
                item.setToolTip(
                    f"{template.intent.value.title()} · {template.description}"
                )
                self.template_list.addItem(item)
                if template.template_id == selected_id:
                    self.template_list.setCurrentItem(item)
        finally:
            self._restoring_template_selection = False

    @Slot(object, object)
    def _on_template_selected(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        """Load a selection after protecting unsaved editor changes."""
        if self._restoring_template_selection:
            return
        if self._template_editor_dirty and previous is not None:
            reply = QMessageBox.question(
                self,
                "Discard Template Changes?",
                "The current template has unsaved changes. Discard them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._restoring_template_selection = True
                self.template_list.setCurrentItem(previous)
                self._restoring_template_selection = False
                return
        if current is None:
            return
        template_id = str(current.data(Qt.ItemDataRole.UserRole) or "")
        template = self._find_task_template(template_id)
        if template is not None:
            self._load_template_editor(template)

    @Slot()
    def _on_new_template(self) -> None:
        """Prepare editor for new template."""
        if not self._confirm_discard_template_changes():
            return
        self._template_editor_dirty = False
        self.template_list.clearSelection()
        self._editing_template_id = str(uuid.uuid4())
        self._set_template_editor_enabled(True)
        self._set_template_editor_read_only(False)
        self._template_editor_dirty = False
        self.template_name_edit.clear()
        self.template_description_edit.clear()
        self.template_intent_combo.setCurrentIndex(2)
        self.template_content_edit.clear()
        self.template_name_edit.setFocus()
        self.btn_delete_template.setEnabled(False)
        self.btn_duplicate_template.setEnabled(False)
        self.btn_save_template.setEnabled(True)
        self._template_editor_dirty = False

    @Slot()
    def _on_save_template(self) -> None:
        """Create or update a world-owned template in place."""
        template_id = self._editing_template_id or str(uuid.uuid4())
        name = self.template_name_edit.text().strip()
        description = self.template_description_edit.text().strip()
        content = self.template_content_edit.toPlainText()
        intent = TaskIntent(str(self.template_intent_combo.currentData()))
        template = TaskTemplate(
            template_id=template_id,
            name=name,
            description=description,
            intent=intent,
            content=content,
            source=TaskTemplateSource.WORLD,
        )
        custom = self.get_custom_task_templates()
        try:
            self._task_template_catalog.validate_world_template(
                template, self._task_templates
            )
            updated = tuple(
                candidate
                for candidate in custom
                if candidate.template_id != template.template_id
            ) + (template,)
            built_ins = tuple(
                candidate
                for candidate in self._task_templates
                if candidate.source == TaskTemplateSource.BUILT_IN
            )
            self._task_templates = built_ins + updated
            self._editing_template_id = template.template_id
            self._template_editor_dirty = False
            self._show_save_status("Template saved")
            self._refresh_templates_list()
            self._select_template_list_item(template.template_id)
            self.task_templates_changed.emit(updated)
        except TaskTemplateValidationError as exc:
            self._show_save_status(f"Error: {exc}")

    @Slot()
    def _on_delete_template(self) -> None:
        """Delete one mutable world template."""
        template = self._find_task_template(self._editing_template_id)
        if template is None or template.source != TaskTemplateSource.WORLD:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete the world template '{template.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            updated = tuple(
                candidate
                for candidate in self.get_custom_task_templates()
                if candidate.template_id != template.template_id
            )
            self._task_templates = tuple(
                candidate
                for candidate in self._task_templates
                if candidate.template_id != template.template_id
            )
            self._show_save_status("Template deleted")
            self._clear_template_editor()
            self._refresh_templates_list()
            self.task_templates_changed.emit(updated)

    @Slot()
    def _on_duplicate_template(self) -> None:
        """Copy a bundled task into the active world's mutable collection."""
        source = self._find_task_template(self._editing_template_id)
        if source is None:
            return
        existing_names = {
            template.name.casefold() for template in self.get_custom_task_templates()
        }
        base_name = f"Copy of {source.name}"
        name = base_name
        suffix = 2
        while name.casefold() in existing_names:
            name = f"{base_name} {suffix}"
            suffix += 1
        self._editing_template_id = str(uuid.uuid4())
        self._set_template_editor_read_only(False)
        self.template_name_edit.setText(name)
        self.template_description_edit.setText(source.description)
        self.template_intent_combo.setCurrentIndex(
            self.template_intent_combo.findData(source.intent.value)
        )
        self.template_content_edit.setPlainText(source.content)
        self._template_editor_dirty = True
        self.btn_delete_template.setEnabled(False)
        self.btn_duplicate_template.setEnabled(False)
        self.btn_save_template.setEnabled(True)
        self._on_save_template()

    def _new_template(self) -> None:
        """Handle new template action."""
        self._on_new_template()

    def set_task_templates(self, templates: tuple[TaskTemplate, ...]) -> None:
        """Apply the merged template snapshot owned by the app manager."""
        self._task_templates = tuple(templates)
        self._refresh_templates_list()

    def get_custom_task_templates(self) -> tuple[TaskTemplate, ...]:
        """Return only mutable templates for portable world preferences."""
        return tuple(
            template
            for template in self._task_templates
            if template.source == TaskTemplateSource.WORLD
        )

    def _find_task_template(self, template_id: object) -> TaskTemplate | None:
        """Find a task in the current UI snapshot."""
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

    def _load_template_editor(self, template: TaskTemplate) -> None:
        """Render one selected template without marking it dirty."""
        self._editing_template_id = template.template_id
        self._set_template_editor_enabled(True)
        self._set_template_editor_read_only(
            template.source == TaskTemplateSource.BUILT_IN
        )
        for widget in (
            self.template_name_edit,
            self.template_description_edit,
            self.template_content_edit,
            self.template_intent_combo,
        ):
            widget.blockSignals(True)
        self.template_name_edit.setText(template.name)
        self.template_description_edit.setText(template.description)
        self.template_intent_combo.setCurrentIndex(
            self.template_intent_combo.findData(template.intent.value)
        )
        self.template_content_edit.setPlainText(template.content)
        for widget in (
            self.template_name_edit,
            self.template_description_edit,
            self.template_content_edit,
            self.template_intent_combo,
        ):
            widget.blockSignals(False)
        built_in = template.source == TaskTemplateSource.BUILT_IN
        self.btn_delete_template.setEnabled(not built_in)
        self.btn_duplicate_template.setEnabled(built_in)
        self.btn_save_template.setEnabled(not built_in)
        self._template_editor_dirty = False

    def _set_template_editor_enabled(self, enabled: bool) -> None:
        """Enable or disable all task editor fields."""
        for widget in (
            self.template_name_edit,
            self.template_description_edit,
            self.template_intent_combo,
            self.template_content_edit,
        ):
            widget.setEnabled(enabled)
        self.btn_save_template.setEnabled(enabled)

    def _set_template_editor_read_only(self, read_only: bool) -> None:
        """Protect bundled templates while keeping them inspectable."""
        self.template_name_edit.setReadOnly(read_only)
        self.template_description_edit.setReadOnly(read_only)
        self.template_content_edit.setReadOnly(read_only)
        self.template_intent_combo.setEnabled(not read_only)

    @Slot()
    def _mark_template_editor_dirty(self) -> None:
        """Record unsaved edits for selection and close protection."""
        if self._editing_template_id is not None:
            self._template_editor_dirty = True

    def _confirm_discard_template_changes(self) -> bool:
        """Confirm abandoning an unsaved world-template edit."""
        if not self._template_editor_dirty:
            return True
        reply = QMessageBox.question(
            self,
            "Discard Template Changes?",
            "Discard the unsaved changes to this task template?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _clear_template_editor(self) -> None:
        """Reset the editor after deletion or an empty selection."""
        self._editing_template_id = None
        self._template_editor_dirty = False
        self.template_name_edit.clear()
        self.template_description_edit.clear()
        self.template_content_edit.clear()
        self._set_template_editor_enabled(False)
        self.btn_delete_template.setEnabled(False)
        self.btn_duplicate_template.setEnabled(False)

    def _select_template_list_item(self, template_id: str) -> None:
        """Select a list row by stable ID."""
        for index in range(self.template_list.count()):
            item = self.template_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == template_id:
                self.template_list.setCurrentItem(item)
                break

    @Slot(int)
    def _on_provider_changed(self, index: int) -> None:
        """Handle embeddings provider selection change."""
        self.provider_stack.setCurrentIndex(index)

    @Slot(int)
    def _on_gen_provider_changed(self, index: int) -> None:
        """Handle generation provider selection change."""
        self.gen_provider_stack.setCurrentIndex(index)

    def _sync_lmstudio_base_url(self, source: QLineEdit) -> None:
        """Normalize one edited server address and mirror it across both pages."""
        try:
            base_url = normalize_lmstudio_base_url(source.text())
        except ValueError:
            base_url = source.text().strip()
        self.lm_gen_url_input.setText(base_url)
        self.lm_url_input.setText(base_url)
        self.save_settings()

    @Slot()
    def _on_clear_generation_settings(self) -> None:
        """Clear all generation provider settings."""
        from PySide6.QtCore import QSettings

        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

        reply = QMessageBox.question(
            self,
            "Clear Settings",
            "Are you sure you want to clear all generation provider settings "
            "including API keys?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            from src.services.secret_store import set_api_key

            # Clear generation settings for all providers
            for provider in ["lmstudio", "openai", "google", "anthropic"]:
                settings.remove(f"ai_gen_{provider}_enabled")
                settings.remove(f"ai_gen_{provider}_url")
                settings.remove(f"ai_gen_{provider}_model")
                settings.remove(f"ai_gen_{provider}_api_key")
                settings.remove(f"ai_gen_{provider}_project_id")
                settings.remove(f"ai_gen_{provider}_location")
                settings.remove(f"ai_gen_{provider}_credentials_path")

            # Clear generation options
            settings.remove("ai_gen_audit_log")
            settings.remove("ai_gen_max_tokens")
            settings.remove("ai_gen_temperature")
            for provider in ("lmstudio", "openai", "anthropic"):
                set_api_key(provider, "")

            # Reload settings to update UI
            self.load_settings()

            QMessageBox.information(
                self, "Settings Cleared", "All generation settings have been cleared."
            )

    @Slot()
    def _on_rebuild_clicked(self) -> None:
        """Handle rebuild button click."""
        obj_type = (
            self.rebuild_combo.currentText().lower().rstrip("s")
        )  # entities->entity
        if obj_type == "all":
            obj_type = "all"

        logger.info(f"Rebuild index requested for type: {obj_type}")
        self.rebuild_index_requested.emit(obj_type)

    def _test_connection(self, provider_id: str, mode: str) -> None:
        """Discover models from LM Studio without blocking the UI.

        Args:
            provider_id: Provider ID (e.g. 'lmstudio')
            mode: 'embed' or 'generate' to determine which URL to test

        """
        if provider_id != "lmstudio" or self._discovery_worker is not None:
            return

        source = self.lm_url_input if mode == "embed" else self.lm_gen_url_input
        try:
            base_url = normalize_lmstudio_base_url(source.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Server URL", str(exc))
            return

        self.lm_url_input.setText(base_url)
        self.lm_gen_url_input.setText(base_url)
        self.btn_test_lm_embed.setEnabled(False)
        self.btn_test_lm_gen.setEnabled(False)
        self._show_save_status("Discovering models...")

        self._discovery_worker = LMStudioDiscoveryWorker(
            base_url,
            self.lm_api_key_input.text().strip(),
            min(float(self.lm_timeout_input.value()), 10.0),
            self,
        )
        self._discovery_worker.models_discovered.connect(
            self._on_models_discovered
        )
        self._discovery_worker.discovery_failed.connect(
            self._on_model_discovery_failed
        )
        self._discovery_worker.finished.connect(self._on_discovery_finished)
        self._discovery_worker.start()

    @Slot(object)
    def _on_models_discovered(self, models: object) -> None:
        """Populate both model selectors while retaining manual selections."""
        model_ids = [str(model) for model in models] if isinstance(models, list) else []
        generation_model = self.lm_gen_model_input.currentText()
        embedding_model = self.lm_model_input.currentText()
        for combo, selected in (
            (self.lm_gen_model_input, generation_model),
            (self.lm_model_input, embedding_model),
        ):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(model_ids)
            combo.setCurrentText(selected)
            combo.blockSignals(False)

        self._show_save_status(f"Found {len(model_ids)} models")
        self.save_settings()

    @Slot(str)
    def _on_model_discovery_failed(self, error: str) -> None:
        """Report model discovery errors without exposing credentials."""
        logger.warning("LM Studio model discovery failed: %s", error)
        self._show_save_status("Model discovery failed")
        QMessageBox.warning(
            self,
            "LM Studio Unavailable",
            f"Could not load models from LM Studio:\n{error}",
        )

    @Slot()
    def _on_discovery_finished(self) -> None:
        """Clean up a completed discovery thread."""
        worker = self._discovery_worker
        self._discovery_worker = None
        self.btn_test_lm_embed.setEnabled(True)
        self.btn_test_lm_gen.setEnabled(True)
        if worker is not None:
            worker.deleteLater()

    def _shutdown_discovery(self) -> None:
        """Keep a discovery QThread alive until its bounded request exits."""
        worker = self._discovery_worker
        if worker is not None and worker.isRunning() and not worker.wait(11_000):
            logger.warning("LM Studio discovery did not stop during shutdown")

    @Slot()
    def save_settings(self) -> None:
        """Save settings to QSettings."""
        if getattr(self, "_initializing", False):
            return

        # Check validity (guard against destruction races)
        try:
            if not self.isVisible() and not self.parent():
                # Just a heuristic; if we can't access a widget, we stop
                _ = self.filter_reasoning_cb.isChecked()
        except RuntimeError:
            return  # Already deleted

        logger.debug("save_settings called - triggering autosave")
        self._show_save_status("Saving...")

        from PySide6.QtCore import QSettings

        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

        # Save excluded attributes
        settings.setValue(
            "ai_search_excluded_attrs", self.excluded_attrs_input.text().strip()
        )

        # Save auto-index on save setting
        settings.setValue(
            "ai_auto_index_on_save", self.chk_auto_index.isChecked()
        )

        # Save embedding provider settings
        provider = (
            "lmstudio"
            if self.provider_combo.currentIndex() == 1
            else "sentence-transformers"
        )
        settings.setValue("ai_embedding_provider", provider)

        # LM Studio connection is machine-global. Retain the legacy endpoint
        # keys temporarily for older search code while storing one canonical base.
        from src.services.lmstudio_config import derive_lmstudio_endpoints
        from src.services.secret_store import set_api_key

        try:
            base_url = normalize_lmstudio_base_url(
                self.lm_gen_url_input.text()
            )
        except ValueError as exc:
            logger.warning("Invalid LM Studio server URL: %s", exc)
            self._show_save_status("Invalid LM Studio server URL")
            return
        endpoints = derive_lmstudio_endpoints(base_url)
        settings.setValue("ai_lmstudio_base_url", endpoints.base_url)
        settings.setValue("ai_lmstudio_url", endpoints.embeddings_url)
        settings.setValue(
            "ai_lmstudio_model", self.lm_model_input.currentText().strip()
        )
        if set_api_key("lmstudio", self.lm_api_key_input.text().strip()):
            settings.remove("ai_lmstudio_api_key")
        settings.setValue("ai_lmstudio_timeout", self.lm_timeout_input.value())

        # Sentence Transformers settings
        settings.setValue("ai_st_model", self.st_model_input.text().strip())

        # Save generation provider settings
        # LM Studio generation
        settings.setValue("ai_gen_lmstudio_enabled", self.lm_gen_enabled.isChecked())
        settings.setValue(
            "ai_gen_lmstudio_use_chat_api", self.lm_gen_use_chat_api.isChecked()
        )
        settings.setValue("ai_gen_lmstudio_url", endpoints.chat_completions_url)
        settings.setValue(
            "ai_gen_lmstudio_model", self.lm_gen_model_input.currentText().strip()
        )

        # OpenAI
        settings.setValue("ai_gen_openai_enabled", self.openai_gen_enabled.isChecked())
        if set_api_key("openai", self.openai_api_key_input.text().strip()):
            settings.remove("ai_gen_openai_api_key")
        settings.setValue("ai_gen_openai_model", self.openai_model_input.text().strip())

        # Google Vertex AI
        settings.setValue("ai_gen_google_enabled", self.google_gen_enabled.isChecked())
        settings.setValue(
            "ai_gen_google_project_id", self.google_project_input.text().strip()
        )
        settings.setValue(
            "ai_gen_google_location", self.google_location_input.text().strip()
        )
        settings.setValue("ai_gen_google_model", self.google_model_input.text().strip())
        settings.setValue(
            "ai_gen_google_credentials_path", self.google_creds_input.text().strip()
        )

        # Anthropic
        settings.setValue(
            "ai_gen_anthropic_enabled", self.anthropic_gen_enabled.isChecked()
        )
        if set_api_key("anthropic", self.anthropic_api_key_input.text().strip()):
            settings.remove("ai_gen_anthropic_api_key")
        settings.setValue(
            "ai_gen_anthropic_model", self.anthropic_model_input.text().strip()
        )

        # Generation options
        settings.setValue("ai_gen_audit_log", self.enable_audit_log.isChecked())
        settings.setValue("ai_gen_max_tokens", self.max_tokens_input.value())
        settings.setValue("ai_gen_temperature", self.temperature_input.value())
        settings.setValue("ai_gen_system_prompt", self.system_prompt_edit.toPlainText())
        settings.setValue(
            "ai_gen_filter_reasoning", self.filter_reasoning_cb.isChecked()
        )
        settings.setValue(
            "ai_gen_summary_prompt", self.summary_prompt_edit.toPlainText()
        )
        settings.setValue(
            "ai_gen_summary_max_tokens", self.summary_max_tokens_input.value()
        )
        settings.setValue(
            "ai_gen_summary_temperature", self.summary_temperature_input.value()
        )

        logger.info(
            f"AI Settings saved. Embedding provider: {provider}, "
            f"Excluded attrs: {self.excluded_attrs_input.text()}"
        )
        self._show_save_status("Saved")
        self.settings_saved.emit()

    def _show_save_status(self, message: str) -> None:
        """Show save status message with autohide.

        Args:
            message: Status message to display (e.g., "Saving...", "Saved").

        """
        self.save_status_label.setText(message)

        # Auto-hide after 3 seconds if message is "Saved"
        if message == "Saved":
            self._status_hide_timer.start(3000)

    def load_settings(self) -> None:
        """Load settings from QSettings."""
        from PySide6.QtCore import QSettings

        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

        # Load excluded attributes
        excluded = settings.value("ai_search_excluded_attrs", "")
        self.excluded_attrs_input.setText(excluded)

        # Load auto-index on save setting
        auto_index = settings.value("ai_auto_index_on_save", False)
        if isinstance(auto_index, str):
            auto_index = auto_index.lower() == "true"
        self.chk_auto_index.setChecked(bool(auto_index))

        # Load embedding provider settings
        provider = settings.value("ai_embedding_provider", "sentence-transformers")
        # Migrate old underscore variant saved by a previous dialog bug
        if provider == "sentence_transformers":
            provider = "sentence-transformers"
        self.provider_combo.setCurrentIndex(1 if provider == "lmstudio" else 0)

        # LM Studio connection settings. Endpoint-shaped legacy values are
        # normalized automatically to the new canonical base URL.
        legacy_url = str(
            settings.value(
                "ai_lmstudio_base_url",
                settings.value(
                    "ai_gen_lmstudio_url",
                    settings.value("ai_lmstudio_url", DEFAULT_LMSTUDIO_BASE_URL),
                ),
            )
        )
        base_url = normalize_lmstudio_base_url(legacy_url)
        self.lm_url_input.setText(base_url)
        self.lm_gen_url_input.setText(base_url)
        self.lm_model_input.setCurrentText(
            str(settings.value("ai_lmstudio_model", ""))
        )
        from src.services.secret_store import migrate_qsettings_secret

        self.lm_api_key_input.setText(
            migrate_qsettings_secret(
                settings,
                "ai_lmstudio_api_key",
                "lmstudio",
            )
        )
        self.lm_timeout_input.setValue(int(settings.value("ai_lmstudio_timeout", 30)))

        # Sentence Transformers settings
        self.st_model_input.setText(settings.value("ai_st_model", "all-MiniLM-L6-v2"))

        # Load generation provider settings
        # LM Studio generation
        self.lm_gen_enabled.setChecked(
            settings.value("ai_gen_lmstudio_enabled", True, type=bool)
        )
        self.lm_gen_use_chat_api.setChecked(
            settings.value("ai_gen_lmstudio_use_chat_api", True, type=bool)
        )
        self.lm_gen_model_input.setCurrentText(
            str(settings.value("ai_gen_lmstudio_model", ""))
        )

        # OpenAI
        self.openai_gen_enabled.setChecked(
            settings.value("ai_gen_openai_enabled", False, type=bool)
        )
        self.openai_api_key_input.setText(
            migrate_qsettings_secret(
                settings,
                "ai_gen_openai_api_key",
                "openai",
            )
        )
        self.openai_model_input.setText(
            settings.value("ai_gen_openai_model", "gpt-3.5-turbo")
        )

        # Google Vertex AI
        self.google_gen_enabled.setChecked(
            settings.value("ai_gen_google_enabled", False, type=bool)
        )
        self.google_project_input.setText(
            settings.value("ai_gen_google_project_id", "")
        )
        self.google_location_input.setText(
            settings.value("ai_gen_google_location", "us-central1")
        )
        self.google_model_input.setText(
            settings.value("ai_gen_google_model", "text-bison@001")
        )
        self.google_creds_input.setText(
            settings.value("ai_gen_google_credentials_path", "")
        )

        # Anthropic
        self.anthropic_gen_enabled.setChecked(
            settings.value("ai_gen_anthropic_enabled", False, type=bool)
        )
        self.anthropic_api_key_input.setText(
            migrate_qsettings_secret(
                settings,
                "ai_gen_anthropic_api_key",
                "anthropic",
            )
        )
        self.anthropic_model_input.setText(
            settings.value("ai_gen_anthropic_model", "claude-3-haiku-20240307")
        )

        # Generation options
        self.enable_audit_log.setChecked(
            settings.value("ai_gen_audit_log", False, type=bool)
        )
        self.max_tokens_input.setValue(int(settings.value("ai_gen_max_tokens", 512)))
        self.temperature_input.setValue(int(settings.value("ai_gen_temperature", 70)))
        self.filter_reasoning_cb.setChecked(
            settings.value("ai_gen_filter_reasoning", True, type=bool)
        )

        # System prompt with default fallback
        default_prompt = (
            "You are an expert fantasy world-builder assisting a user in creating a "
            "rich and immersive setting. Your tone is descriptive, evocative, and "
            "consistent with high-fantasy literature.\n\n"
            "IMPORTANT: Time in this world is represented as floating-point numbers "
            "where 1.0 = 1 day. The decimal portion represents time within the day "
            "(e.g., 0.5 = noon). When referencing dates or durations, understand "
            "that event dates and durations use this numeric format."
        )
        self.system_prompt_edit.setPlainText(
            settings.value("ai_gen_system_prompt", default_prompt)
        )

        self.summary_prompt_edit.setPlainText(
            settings.value("ai_gen_summary_prompt", DEFAULT_SUMMARY_PROMPT)
        )
        self.summary_max_tokens_input.setValue(
            int(settings.value("ai_gen_summary_max_tokens", 2048))
        )
        self.summary_temperature_input.setValue(
            int(settings.value("ai_gen_summary_temperature", 0))
        )

    def export_world_preferences(self) -> AIGenerationPreferences:
        """Build the portable creative settings for the current world."""
        from PySide6.QtCore import QSettings

        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        return AIGenerationPreferences(
            persona=self.system_prompt_edit.toPlainText(),
            max_tokens=self.max_tokens_input.value(),
            temperature_percent=self.temperature_input.value(),
            rag_enabled=settings.value("ai_gen_rag_enabled", True, type=bool),
            rag_limit=int(settings.value("ai_gen_rag_limit", 3)),
            spatial_enabled=settings.value(
                "ai_gen_spatial_enabled", False, type=bool
            ),
            filter_reasoning=self.filter_reasoning_cb.isChecked(),
            audit_enabled=self.enable_audit_log.isChecked(),
            selected_entity_template_id=str(
                settings.value("ai_gen_entity_template_id", "") or ""
            ),
            selected_event_template_id=str(
                settings.value("ai_gen_event_template_id", "") or ""
            ),
            entity_prompt_draft=str(
                settings.value("ai_gen_entity_prompt", "") or ""
            ),
            event_prompt_draft=str(
                settings.value("ai_gen_event_prompt", "") or ""
            ),
            custom_task_templates=self.get_custom_task_templates(),
        )

    def apply_world_preferences(self, preferences: AIGenerationPreferences) -> None:
        """Apply portable world settings to the dialog and compatibility cache."""
        from PySide6.QtCore import QSettings

        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

        self._initializing = True
        try:
            self.system_prompt_edit.setPlainText(preferences.persona)
            self.max_tokens_input.setValue(preferences.max_tokens)
            self.temperature_input.setValue(preferences.temperature_percent)
            self.filter_reasoning_cb.setChecked(preferences.filter_reasoning)
            self.enable_audit_log.setChecked(preferences.audit_enabled)

            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            settings.setValue("ai_gen_system_prompt", preferences.persona)
            settings.setValue("ai_gen_max_tokens", preferences.max_tokens)
            settings.setValue(
                "ai_gen_temperature", preferences.temperature_percent
            )
            settings.setValue("ai_gen_rag_enabled", preferences.rag_enabled)
            settings.setValue("ai_gen_rag_limit", preferences.rag_limit)
            settings.setValue(
                "ai_gen_spatial_enabled", preferences.spatial_enabled
            )
            settings.setValue(
                "ai_gen_filter_reasoning", preferences.filter_reasoning
            )
            settings.setValue("ai_gen_audit_log", preferences.audit_enabled)
            settings.setValue(
                "ai_gen_entity_template_id",
                preferences.selected_entity_template_id,
            )
            settings.setValue(
                "ai_gen_event_template_id",
                preferences.selected_event_template_id,
            )
            settings.setValue(
                "ai_gen_entity_prompt", preferences.entity_prompt_draft
            )
            settings.setValue(
                "ai_gen_event_prompt", preferences.event_prompt_draft
            )
            built_ins = tuple(
                template
                for template in self._task_templates
                if template.source == TaskTemplateSource.BUILT_IN
            )
            self._task_templates = built_ins + preferences.custom_task_templates
            self._refresh_templates_list()
        finally:
            self._initializing = False

    def update_status(self, model: str, counts: str, last_updated: str) -> None:
        """Update the status labels."""
        self.lbl_model.setText(f"Model: {model}")
        self.lbl_indexed_count.setText(f"Indexed: {counts}")
        self.lbl_last_indexed.setText(f"Last Updated: {last_updated}")

    def set_rebuild_in_progress(self, in_progress: bool) -> None:
        """Toggle rebuild-in-progress state on the dialog.

        Disables/enables the rebuild button and shows/hides the progress label.

        Args:
            in_progress: True to indicate a rebuild is running.

        """
        self.btn_rebuild.setEnabled(not in_progress)
        self.lbl_rebuild_progress.setVisible(in_progress)
        if not in_progress:
            self.lbl_rebuild_progress.setText("")

    def update_rebuild_progress(self, done: int, total: int, pct: int) -> None:
        """Update the rebuild progress label.

        Args:
            done: Number of items processed so far.
            total: Total number of items to process.
            pct: Percentage complete.

        """
        self.lbl_rebuild_progress.setVisible(True)
        self.lbl_rebuild_progress.setText(
            f"Indexing {done}/{total} ({pct}%)"
        )
