"""
AI Settings Dialog.

Provides configuration for AI features, including Search Index status and
attribute exclusion.
"""

import logging
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper

logger = logging.getLogger(__name__)


class AISettingsDialog(QDialog):
    """
    Dialog for AI Search settings and index status.
    """

    rebuild_index_requested = Signal(str)  # object_type ('entity', 'event', 'all')
    index_status_requested = Signal()  # Request to refresh index status

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the AI Settings Dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("AI Settings")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)
        # self.setAttribute(
        #     Qt.WA_DeleteOnClose, True
        # )  # Removed to prevent RuntimeError on re-open

        logger.info("Initializing AI Settings Dialog")

        # Main layout
        main_layout = QVBoxLayout(self)

        # Tab widget for organizing settings
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Create tabs
        self._create_embeddings_tab()
        self._create_generation_tab()

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

        # Load settings
        self.load_settings()

    def _on_ok_clicked(self) -> None:
        """Handle OK button click."""
        self.save_settings()
        self.accept()

    def _create_embeddings_tab(self) -> None:
        """Create the embeddings/search configuration tab."""
        embeddings_widget = QWidget()
        main_layout = QVBoxLayout(embeddings_widget)
        StyleHelper.apply_standard_list_spacing(main_layout)

        # === Index Status Section ===
        index_group = QGroupBox("Index Status")
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

        # Refresh button
        self.btn_refresh_status = QPushButton("Refresh Status")
        self.btn_refresh_status.clicked.connect(self.index_status_requested.emit)
        index_layout.addWidget(self.btn_refresh_status)

        main_layout.addWidget(index_group)

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
        lm_studio_form.addRow("API URL:", self.lm_url_input)

        self.lm_model_input = QLineEdit()
        self.lm_model_input.setPlaceholderText("e.g. nomic-embed-text-v1.5")
        lm_studio_form.addRow("Embedding Model:", self.lm_model_input)

        self.lm_api_key_input = QLineEdit()
        self.lm_api_key_input.setPlaceholderText("Optional")
        self.lm_api_key_input.setEchoMode(QLineEdit.Password)
        lm_studio_form.addRow("API Key:", self.lm_api_key_input)

        # Test connection button
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

        # Save LLM settings button
        save_llm_btn = QPushButton("Save LLM Settings")
        save_llm_btn.clicked.connect(self.save_settings)
        llm_layout.addWidget(save_llm_btn)

        main_layout.addWidget(llm_group)

        # === Settings Section ===
        settings_group = QGroupBox("Settings")
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

        # Add to tabs
        self.tabs.addTab(embeddings_widget, "Embeddings & Search")

    def _create_generation_tab(self) -> None:
        """Create the text generation configuration tab."""
        generation_widget = QWidget()
        main_layout = QVBoxLayout(generation_widget)
        StyleHelper.apply_standard_list_spacing(main_layout)

        # === Generation Providers Section ===
        gen_group = QGroupBox("Text Generation Providers")
        gen_layout = QVBoxLayout(gen_group)
        StyleHelper.apply_standard_list_spacing(gen_layout)

        # Provider selection
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Provider:"))
        self.gen_provider_combo = QComboBox()
        self.gen_provider_combo.addItems(
            ["LM Studio", "OpenAI", "Google Vertex AI", "Anthropic Claude"]
        )
        self.gen_provider_combo.currentIndexChanged.connect(
            self._on_gen_provider_changed
        )
        provider_layout.addWidget(self.gen_provider_combo, stretch=1)
        gen_layout.addLayout(provider_layout)

        # Stacked widget for provider-specific settings
        self.gen_provider_stack = QStackedWidget()

        # LM Studio generation settings
        lm_gen_page = QGroupBox()
        lm_gen_form = QFormLayout(lm_gen_page)
        StyleHelper.apply_standard_list_spacing(lm_gen_form)

        self.lm_gen_enabled = QCheckBox("Enable for this world")
        self.lm_gen_enabled.setChecked(True)
        lm_gen_form.addRow("Enabled:", self.lm_gen_enabled)

        self.lm_gen_url_input = QLineEdit()
        self.lm_gen_url_input.setPlaceholderText("http://localhost:8080/v1/completions")
        lm_gen_form.addRow("API URL:", self.lm_gen_url_input)

        # Test connection button
        self.btn_test_lm_gen = QPushButton("Test Connection")
        self.btn_test_lm_gen.setFixedWidth(120)
        self.btn_test_lm_gen.clicked.connect(
            lambda: self._test_connection("lmstudio", "generate")
        )
        lm_gen_form.addRow("", self.btn_test_lm_gen)

        self.lm_gen_model_input = QLineEdit()
        self.lm_gen_model_input.setPlaceholderText("e.g. mistral-7b-instruct")
        lm_gen_form.addRow("Model:", self.lm_gen_model_input)

        self.gen_provider_stack.addWidget(lm_gen_page)

        # OpenAI generation settings
        openai_gen_page = QGroupBox()
        openai_gen_form = QFormLayout(openai_gen_page)
        StyleHelper.apply_standard_list_spacing(openai_gen_form)

        self.openai_gen_enabled = QCheckBox("Enable for this world")
        openai_gen_form.addRow("Enabled:", self.openai_gen_enabled)

        self.openai_api_key_input = QLineEdit()
        self.openai_api_key_input.setPlaceholderText("sk-...")
        self.openai_api_key_input.setEchoMode(QLineEdit.Password)
        openai_gen_form.addRow("API Key:", self.openai_api_key_input)

        self.openai_model_input = QLineEdit()
        self.openai_model_input.setPlaceholderText("gpt-3.5-turbo")
        openai_gen_form.addRow("Model:", self.openai_model_input)

        self.gen_provider_stack.addWidget(openai_gen_page)

        # Google Vertex AI settings
        google_gen_page = QGroupBox()
        google_gen_form = QFormLayout(google_gen_page)
        StyleHelper.apply_standard_list_spacing(google_gen_form)

        self.google_gen_enabled = QCheckBox("Enable for this world")
        google_gen_form.addRow("Enabled:", self.google_gen_enabled)

        self.google_project_input = QLineEdit()
        self.google_project_input.setPlaceholderText("your-project-id")
        google_gen_form.addRow("Project ID:", self.google_project_input)

        self.google_location_input = QLineEdit()
        self.google_location_input.setPlaceholderText("us-central1")
        google_gen_form.addRow("Location:", self.google_location_input)

        self.google_model_input = QLineEdit()
        self.google_model_input.setPlaceholderText("text-bison@001")
        google_gen_form.addRow("Model:", self.google_model_input)

        self.google_creds_input = QLineEdit()
        self.google_creds_input.setPlaceholderText("/path/to/credentials.json")
        google_gen_form.addRow("Credentials Path:", self.google_creds_input)

        self.gen_provider_stack.addWidget(google_gen_page)

        # Anthropic Claude settings
        anthropic_gen_page = QGroupBox()
        anthropic_gen_form = QFormLayout(anthropic_gen_page)
        StyleHelper.apply_standard_list_spacing(anthropic_gen_form)

        self.anthropic_gen_enabled = QCheckBox("Enable for this world")
        anthropic_gen_form.addRow("Enabled:", self.anthropic_gen_enabled)

        self.anthropic_api_key_input = QLineEdit()
        self.anthropic_api_key_input.setPlaceholderText("sk-ant-...")
        self.anthropic_api_key_input.setEchoMode(QLineEdit.Password)
        anthropic_gen_form.addRow("API Key:", self.anthropic_api_key_input)

        self.anthropic_model_input = QLineEdit()
        self.anthropic_model_input.setPlaceholderText("claude-3-haiku-20240307")
        anthropic_gen_form.addRow("Model:", self.anthropic_model_input)

        self.gen_provider_stack.addWidget(anthropic_gen_page)

        gen_layout.addWidget(self.gen_provider_stack)

        # Save generation settings button
        save_gen_btn = QPushButton("Save Generation Settings")
        save_gen_btn.clicked.connect(self.save_settings)
        gen_layout.addWidget(save_gen_btn)

        main_layout.addWidget(gen_group)

        # === Generation Options ===
        options_group = QGroupBox("Generation Options")
        options_layout = QFormLayout(options_group)
        StyleHelper.apply_standard_list_spacing(options_layout)

        self.enable_audit_log = QCheckBox("Enable audit logging")
        self.enable_audit_log.setToolTip(
            "Log all generation requests and responses for auditing"
        )
        options_layout.addRow("Audit Log:", self.enable_audit_log)

        self.max_tokens_input = QSpinBox()
        self.max_tokens_input.setRange(100, 4096)
        self.max_tokens_input.setValue(512)
        self.max_tokens_input.setToolTip("Maximum tokens to generate per request")
        options_layout.addRow("Max Tokens:", self.max_tokens_input)

        self.temperature_input = QSpinBox()
        self.temperature_input.setRange(0, 200)
        self.temperature_input.setValue(70)
        self.temperature_input.setSuffix("%")
        self.temperature_input.setToolTip("Temperature (0-200%, where 100% = 1.0)")
        options_layout.addRow("Temperature:", self.temperature_input)

        # System Prompt
        system_prompt_label = QLabel("System Prompt:")
        options_layout.addRow(system_prompt_label, QWidget())  # Spacer

        self.system_prompt_edit = QPlainTextEdit()
        self.system_prompt_edit.setStyleSheet(StyleHelper.get_input_field_style())
        self.system_prompt_edit.setPlaceholderText(
            "Enter the system prompt that defines the LLM's role and behavior..."
        )
        self.system_prompt_edit.setMaximumHeight(120)
        self.system_prompt_edit.setToolTip(
            "The system prompt defines how the LLM should behave and respond. "
            "This will be prepended to all generation requests."
        )
        options_layout.addRow("", self.system_prompt_edit)

        # Restore default button
        restore_btn = QPushButton("Restore Default")
        restore_btn.setMaximumWidth(120)
        restore_btn.setToolTip(
            "Restore the default fantasy world-builder system prompt"
        )
        restore_btn.clicked.connect(self._on_restore_default_prompt)
        options_layout.addRow("", restore_btn)

        main_layout.addWidget(options_group)

        # Clear all settings button
        clear_btn = QPushButton("Clear All Generation Settings")
        clear_btn.setStyleSheet("QPushButton { color: #e74c3c; }")
        clear_btn.clicked.connect(self._on_clear_generation_settings)
        clear_btn.setToolTip("Clear all stored API keys and generation settings")
        main_layout.addWidget(clear_btn)

        main_layout.addStretch()

        # Add to tabs
        self.tabs.addTab(generation_widget, "Text Generation")

    def _on_provider_changed(self, index: int) -> None:
        """Handle embeddings provider selection change."""
        self.provider_stack.setCurrentIndex(index)

    def _on_gen_provider_changed(self, index: int) -> None:
        """Handle generation provider selection change."""
        self.gen_provider_stack.setCurrentIndex(index)

    def _on_clear_generation_settings(self) -> None:
        """Clear all generation provider settings."""
        from PySide6.QtCore import QSettings

        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

        reply = QMessageBox.question(
            self,
            "Clear Settings",
            "Are you sure you want to clear all generation provider settings "
            "including API keys?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
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

    def _on_rebuild_clicked(self) -> None:
        """Handle rebuild button click."""
        obj_type = (
            self.rebuild_combo.currentText().lower().rstrip("s")
        )  # entities->entity
        if obj_type == "all":
            obj_type = "all"

        logger.info(f"Rebuild index requested for type: {obj_type}")
        self.rebuild_index_requested.emit(obj_type)

    def _on_restore_default_prompt(self) -> None:
        """Restore the default system prompt."""
        default_prompt = (
            "You are an expert fantasy world-builder assisting a user in creating a "
            "rich and immersive setting. Your tone is descriptive, evocative, and "
            "consistent with high-fantasy literature.\n\n"
            "IMPORTANT: Time in this world is represented as floating-point numbers "
            "where 1.0 = 1 day. The decimal portion represents time within the day "
            "(e.g., 0.5 = noon). When referencing dates or durations, understand "
            "that event dates and durations use this numeric format."
        )
        self.system_prompt_edit.setPlainText(default_prompt)

    def _test_connection(self, provider_id: str, mode: str) -> None:
        """
        Test connection to the specified provider.

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

    def save_settings(self) -> None:
        """Save settings to QSettings."""
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

        logger.info(
            f"AI Settings saved. Embedding provider: {provider}, "
            f"Excluded attrs: {self.excluded_attrs_input.text()}"
        )

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
        self.lm_gen_url_input.setText(
            settings.value(
                "ai_gen_lmstudio_url", "http://localhost:8080/v1/completions"
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

    def update_status(self, model: str, counts: str, last_updated: str) -> None:
        """Update the status labels."""
        self.lbl_model.setText(f"Model: {model}")
        self.lbl_indexed_count.setText(f"Indexed: {counts}")
        self.lbl_last_indexed.setText(f"Last Updated: {last_updated}")
