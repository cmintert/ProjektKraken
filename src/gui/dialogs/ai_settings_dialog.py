"""AI Settings Dialog.

Provides configuration for AI features, including Search Index status and attribute
exclusion.
"""

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.prompt_editor import PromptEditorWidget
from src.services.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


class AISettingsDialog(QDialog):
    """Dialog for AI Search settings and index status."""

    rebuild_index_requested = Signal(str)  # object_type ('entity', 'event', 'all')
    index_status_requested = Signal()  # Request to refresh index status

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
        self.sidebar_list.addItem(QListWidgetItem("Templates"))

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
        self.lm_gen_url_input.setPlaceholderText(
            "http://localhost:8080/v1/chat/completions"
        )
        self.lm_gen_url_input.editingFinished.connect(self.save_settings)
        lm_gen_form.addRow("API URL:", self.lm_gen_url_input)
        self.btn_test_lm_gen = QPushButton("Test Connection")
        self.btn_test_lm_gen.setFixedWidth(120)
        self.btn_test_lm_gen.clicked.connect(
            lambda: self._test_connection("lmstudio", "generate")
        )
        lm_gen_form.addRow("", self.btn_test_lm_gen)
        self.lm_gen_model_input = QLineEdit()
        self.lm_gen_model_input.setPlaceholderText("e.g. mistral-7b-instruct")
        self.lm_gen_model_input.editingFinished.connect(self.save_settings)
        lm_gen_form.addRow("Model:", self.lm_gen_model_input)
        self.gen_provider_stack.addWidget(lm_gen_page)

        # [OpenAI Gen Page]
        openai_gen_page = QGroupBox()
        openai_gen_form = QFormLayout(openai_gen_page)
        StyleHelper.apply_standard_list_spacing(openai_gen_form)
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

        # [Google Gen Page]
        google_gen_page = QGroupBox()
        google_gen_form = QFormLayout(google_gen_page)
        StyleHelper.apply_standard_list_spacing(google_gen_form)
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

        # [Anthropic Gen Page]
        anthropic_gen_page = QGroupBox()
        anthropic_gen_form = QFormLayout(anthropic_gen_page)
        StyleHelper.apply_standard_list_spacing(anthropic_gen_form)
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

        gen_layout.addWidget(self.gen_provider_stack)
        main_layout.addWidget(gen_group)

        # === Generation Parameters (Moved from old options tab) ===
        params_group = QGroupBox("Parameters")
        params_layout = QFormLayout(params_group)
        StyleHelper.apply_standard_list_spacing(params_layout)

        self.max_tokens_input = QSpinBox()
        self.max_tokens_input.setRange(100, 4096)
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
        self.provider_combo.addItems(["LM Studio", "Sentence Transformers"])
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self.provider_combo.currentIndexChanged.connect(self.save_settings)
        provider_layout.addWidget(self.provider_combo, stretch=1)
        llm_layout.addLayout(provider_layout)

        # Stacked widget for provider-specific settings
        self.provider_stack = QStackedWidget()

        # LM Studio settings page
        lm_studio_page = QGroupBox()
        lm_studio_form = QFormLayout(lm_studio_page)
        StyleHelper.apply_standard_list_spacing(lm_studio_form)
        self.lm_url_input = QLineEdit()
        self.lm_url_input.setPlaceholderText("http://localhost:8080/v1/embeddings")
        self.lm_url_input.editingFinished.connect(self.save_settings)
        lm_studio_form.addRow("API URL:", self.lm_url_input)
        self.lm_model_input = QLineEdit()
        self.lm_model_input.setPlaceholderText("e.g. nomic-embed-text-v1.5")
        self.lm_model_input.editingFinished.connect(self.save_settings)
        lm_studio_form.addRow("Embedding Model:", self.lm_model_input)
        self.lm_api_key_input = QLineEdit()
        self.lm_api_key_input.setPlaceholderText("Optional")
        self.lm_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.lm_api_key_input.editingFinished.connect(self.save_settings)
        lm_studio_form.addRow("API Key:", self.lm_api_key_input)
        self.btn_test_lm_embed = QPushButton("Test Connection")
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

        # Sentence Transformers settings page
        st_page = QGroupBox()
        st_form = QFormLayout(st_page)
        StyleHelper.apply_standard_list_spacing(st_form)
        self.st_model_input = QLineEdit()
        self.st_model_input.setPlaceholderText("all-MiniLM-L6-v2")
        st_form.addRow("Model:", self.st_model_input)
        self.provider_stack.addWidget(st_page)

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
        self.btn_refresh_status = QPushButton("Refresh Status")
        self.btn_refresh_status.clicked.connect(self.index_status_requested.emit)
        index_layout.addWidget(self.btn_refresh_status)
        main_layout.addWidget(index_group)

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
        system_group = QGroupBox("Basic Assistant Prompt")
        system_layout = QVBoxLayout(system_group)
        StyleHelper.apply_compact_spacing(system_layout)

        self.system_prompt_edit = PromptEditorWidget()
        self.system_prompt_edit.setPlaceholderText(
            "Enter the system prompt that defines the LLM's role and behavior..."
        )
        self.system_prompt_edit.setMinimumHeight(120)  # Taller for reading
        self.system_prompt_edit.setToolTip(
            "The system prompt defines how the LLM should behave and respond.\n\n"
            "NOTE: If a specific Template is selected in the Generation Widget,\n"
            "it will OVERRIDE this setting."
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
            [
                "{type}",
                "{name}",
                "{description}",
                "{lore_date}",
                "{attributes}",
                "{relations}",
            ]
        )
        system_layout.addWidget(self.system_prompt_edit)
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
        default_summary_prompt = (
            "Summarize the following content in a clear, structured, and concise way. "
            "Focus on the essential ideas, remove filler, and present the information "
            "as a summary.\n\n"
            "Requirements:\n"
            "- Start with a short, high-level overview (2–3 sentences)\n"
            "- Follow with bullet points capturing key details, decisions, "
            "and insights\n"
            "- Preserve factual accuracy without adding new information\n"
            "- Use neutral, professional language\n"
            "- Avoid repetition and avoid quoting large sections verbatim\n\n"
            "Content Data:\n"
            "Type: {type}\n"
            "Name: {name}\n"
            "Description: {description}"
        )
        self.summary_prompt_edit.set_default_text(default_summary_prompt)
        summary_layout.addWidget(self.summary_prompt_edit)
        main_layout.addWidget(summary_group)

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
        """Create the Templates management page."""
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

        lbl_list = QLabel("Templates")
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
        self.template_list.currentRowChanged.connect(self._on_template_selected)
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

        self.template_id_edit = QLineEdit()
        self.template_id_edit.setPlaceholderText("e.g. fantasy_prompt")
        meta_form.addRow("ID:", self.template_id_edit)

        self.template_name_edit = QLineEdit()
        self.template_name_edit.setPlaceholderText("e.g. Fantasy World Builder")
        meta_form.addRow("Name:", self.template_name_edit)

        right_layout.addWidget(meta_group)

        # Content editor
        content_group = QGroupBox("Prompt Content")
        content_layout = QVBoxLayout(content_group)
        content_layout.setContentsMargins(4, 8, 4, 4)

        self.template_content_edit = PromptEditorWidget()
        self.template_content_edit.setPlaceholderText("Enter template content here...")
        self.template_content_edit.set_variables(
            [
                "{type}",
                "{name}",
                "{description}",
                "{lore_date}",
                "{attributes}",
                "{relations}",
            ]
        )
        content_layout.addWidget(self.template_content_edit)
        right_layout.addWidget(content_group, stretch=1)

        # Editor actions
        editor_actions = QHBoxLayout()
        self.btn_delete_template = QPushButton("Delete")
        self.btn_delete_template.setStyleSheet(
            "background-color: #AF4448; color: white;"
        )
        self.btn_delete_template.clicked.connect(self._on_delete_template)
        editor_actions.addWidget(self.btn_delete_template)

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

        # Initial refresh
        self._refresh_templates_list()

        return page

    @Slot()
    def _refresh_templates_list(self) -> None:
        """Reload templates from disk."""
        self.template_list.clear()
        try:
            loader = PromptLoader()
            templates = loader.list_templates()
            # Sort by name
            templates.sort(key=lambda x: x.get("name", "").lower())

            for t in templates:
                item = QListWidgetItem(f"{t['name']} (v{t['version']})")
                item.setData(Qt.ItemDataRole.UserRole, t["template_id"])
                item.setToolTip(f"ID: {t['template_id']}\n{t.get('description', '')}")
                self.template_list.addItem(item)

        except Exception as e:
            logger.error(f"Failed to load templates: {e}")
            self._show_save_status(f"Error loading templates: {e}")

    @Slot(int)
    def _on_template_selected(self, row: int) -> None:
        """Load selected template into editor."""
        if row < 0:
            return

        item = self.template_list.item(row)
        template_id = item.data(Qt.ItemDataRole.UserRole)

        try:
            loader = PromptLoader()
            # Load latest version
            template = loader.load_template(template_id)

            self.template_id_edit.setText(template.template_id)
            self.template_id_edit.setReadOnly(True)  # Lock ID for existing templates
            self.template_name_edit.setText(template.name)
            self.template_content_edit.setPlainText(template.content)

            # Enable buttons
            self.btn_delete_template.setEnabled(True)
            self.btn_save_template.setEnabled(True)

        except Exception as e:
            logger.error(f"Failed to load template details: {e}")
            self._show_save_status("Error loading template")

    @Slot()
    def _on_new_template(self) -> None:
        """Prepare editor for new template."""
        self.template_list.clearSelection()
        self.template_id_edit.clear()
        self.template_id_edit.setReadOnly(False)
        self.template_name_edit.clear()
        self.template_content_edit.clear()
        self.template_id_edit.setFocus()
        self.btn_delete_template.setEnabled(False)

    @Slot()
    def _on_save_template(self) -> None:
        """Save the current template."""
        tid = self.template_id_edit.text().strip()
        name = self.template_name_edit.text().strip()
        content = self.template_content_edit.toPlainText()

        if not tid or not name:
            self._show_save_status("Error: ID and Name required")
            return

        try:
            loader = PromptLoader()
            metadata = {"name": name}
            loader.save_template(tid, content, metadata)

            self._show_save_status("Template saved")
            self._refresh_templates_list()

            # Find and reselet
            for i in range(self.template_list.count()):
                if self.template_list.item(i).data(Qt.ItemDataRole.UserRole) == tid:
                    self.template_list.setCurrentRow(i)
                    break

        except Exception as e:
            logger.error(f"Failed to save template: {e}")
            self._show_save_status(f"Error: {e}")

    @Slot()
    def _on_delete_template(self) -> None:
        """Delete the selected template."""
        row = self.template_list.currentRow()
        if row < 0:
            return

        tid = self.template_id_edit.text()

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete template '{tid}'?\n"
            "This will delete ALL versions.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                loader = PromptLoader()
                loader.delete_template(tid)
                self._show_save_status("Template deleted")
                self._new_template()  # Clear editor
                self._refresh_templates_list()
            except Exception as e:
                logger.error(f"Failed to delete template: {e}")
                self._show_save_status(f"Error: {e}")

    def _new_template(self) -> None:
        self._on_new_template()

    @Slot(int)
    def _on_provider_changed(self, index: int) -> None:
        """Handle embeddings provider selection change."""
        self.provider_stack.setCurrentIndex(index)

    @Slot(int)
    def _on_gen_provider_changed(self, index: int) -> None:
        """Handle generation provider selection change."""
        self.gen_provider_stack.setCurrentIndex(index)

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
        """Test connection to the specified provider.

        Args:
            provider_id: Provider ID (e.g. 'lmstudio')
            mode: 'embed' or 'generate' to determine which URL to test
        """
        try:
            from src.services.llm_provider import create_provider

            # Create a temporary provider instance with current UI values
            overrides = {}
            if provider_id == "lmstudio":
                overrides["timeout"] = self.lm_timeout_input.value()
                overrides["api_key"] = self.lm_api_key_input.text().strip()
                if mode == "embed":
                    overrides["embed_url"] = self.lm_url_input.text().strip()
                    overrides["model"] = self.lm_model_input.text().strip()
                else:  # generate
                    overrides["generate_url"] = self.lm_gen_url_input.text().strip()
                    overrides["model"] = self.lm_gen_model_input.text().strip()

            logger.info(
                f"Testing connection for {provider_id} ({mode}) "
                f"with overrides: {overrides}"
            )

            # Create provider and check health
            provider = create_provider(provider_id, **overrides)
            health = provider.health_check()

            if health["status"] == "healthy":
                QMessageBox.information(
                    self,
                    "Connection Successful",
                    f"Successfully connected to {provider_id}!\n\n"
                    f"Latency: {health.get('latency_ms', 0):.2f}ms",
                )
            else:
                QMessageBox.warning(
                    self,
                    "Connection Failed",
                    f"Connection failed:\n{health.get('message', 'Unknown error')}",
                )

        except Exception as e:
            logger.error(f"Test connection error: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Error", f"An error occurred while testing connection:\n{str(e)}"
            )

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

        # Save embedding provider settings
        provider = (
            "lmstudio"
            if self.provider_combo.currentIndex() == 0
            else "sentence_transformers"
        )
        settings.setValue("ai_embedding_provider", provider)

        # LM Studio embedding settings
        settings.setValue("ai_lmstudio_url", self.lm_url_input.text().strip())
        settings.setValue("ai_lmstudio_model", self.lm_model_input.text().strip())
        settings.setValue("ai_lmstudio_api_key", self.lm_api_key_input.text().strip())
        settings.setValue("ai_lmstudio_timeout", self.lm_timeout_input.value())

        # Sentence Transformers settings
        settings.setValue("ai_st_model", self.st_model_input.text().strip())

        # Save generation provider settings
        # LM Studio generation
        settings.setValue("ai_gen_lmstudio_enabled", self.lm_gen_enabled.isChecked())
        settings.setValue(
            "ai_gen_lmstudio_use_chat_api", self.lm_gen_use_chat_api.isChecked()
        )
        settings.setValue("ai_gen_lmstudio_url", self.lm_gen_url_input.text().strip())
        settings.setValue(
            "ai_gen_lmstudio_model", self.lm_gen_model_input.text().strip()
        )

        # OpenAI
        settings.setValue("ai_gen_openai_enabled", self.openai_gen_enabled.isChecked())
        settings.setValue(
            "ai_gen_openai_api_key", self.openai_api_key_input.text().strip()
        )
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
        settings.setValue(
            "ai_gen_anthropic_api_key", self.anthropic_api_key_input.text().strip()
        )
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

        logger.info(
            f"AI Settings saved. Embedding provider: {provider}, "
            f"Excluded attrs: {self.excluded_attrs_input.text()}"
        )
        self._show_save_status("Saved")

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

        # Load embedding provider settings
        provider = settings.value("ai_embedding_provider", "lmstudio")
        self.provider_combo.setCurrentIndex(0 if provider == "lmstudio" else 1)

        # LM Studio embedding settings
        self.lm_url_input.setText(
            settings.value("ai_lmstudio_url", "http://localhost:8080/v1/embeddings")
        )
        self.lm_model_input.setText(settings.value("ai_lmstudio_model", ""))
        self.lm_api_key_input.setText(settings.value("ai_lmstudio_api_key", ""))
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
        self.lm_gen_url_input.setText(
            settings.value(
                "ai_gen_lmstudio_url", "http://localhost:8080/v1/chat/completions"
            )
        )
        self.lm_gen_model_input.setText(settings.value("ai_gen_lmstudio_model", ""))

        # OpenAI
        self.openai_gen_enabled.setChecked(
            settings.value("ai_gen_openai_enabled", False, type=bool)
        )
        self.openai_api_key_input.setText(settings.value("ai_gen_openai_api_key", ""))
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
            settings.value("ai_gen_anthropic_api_key", "")
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

        # Summary prompt with default fallback
        default_summary_prompt = (
            "Summarize the following worldbuilding item neutrally, "
            "preserving all facts and the original tone. "
            "Crucially, PRESERVE any [[Wiki Links]] exactly as they appear.\n\n"
            "Item Data:\n"
            "Type: {type}\n"
            "Name: {name}\n"
            "Description: {description}"
        )
        self.summary_prompt_edit.setPlainText(
            settings.value("ai_gen_summary_prompt", default_summary_prompt)
        )

    def update_status(self, model: str, counts: str, last_updated: str) -> None:
        """Update the status labels."""
        self.lbl_model.setText(f"Model: {model}")
        self.lbl_indexed_count.setText(f"Indexed: {counts}")
        self.lbl_last_indexed.setText(f"Last Updated: {last_updated}")
