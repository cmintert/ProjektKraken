"""
AI Settings Dialog.

Provides configuration for AI features, including Search Index status and
attribute exclusion.
"""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper


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
        self.setWindowTitle("AI Search Index and Settings")
        self.setMinimumWidth(400)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # Main layout
        main_layout = QVBoxLayout(self)
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

        # === LLM Configuration Section ===
        llm_group = QGroupBox("LLM Configuration")
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
        lm_studio_form.addRow("Model:", self.lm_model_input)

        self.lm_api_key_input = QLineEdit()
        self.lm_api_key_input.setPlaceholderText("Optional")
        self.lm_api_key_input.setEchoMode(QLineEdit.Password)
        lm_studio_form.addRow("API Key:", self.lm_api_key_input)

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

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        main_layout.addWidget(close_btn)

        # Load settings
        self.load_settings()

    def _on_provider_changed(self, index: int) -> None:
        """Handle provider selection change."""
        self.provider_stack.setCurrentIndex(index)

    def _on_rebuild_clicked(self) -> None:
        """Handle rebuild button click."""
        obj_type = (
            self.rebuild_combo.currentText().lower().rstrip("s")
        )  # entities->entity
        if obj_type == "all":
            obj_type = "all"
        self.rebuild_index_requested.emit(obj_type)

    def save_settings(self) -> None:
        """Save settings to QSettings."""
        from PySide6.QtCore import QSettings

        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

        # Save excluded attributes
        settings.setValue(
            "ai_search_excluded_attrs", self.excluded_attrs_input.text().strip()
        )

        # Save LLM settings
        provider = (
            "lmstudio"
            if self.provider_combo.currentIndex() == 0
            else "sentence_transformers"
        )
        settings.setValue("ai_embedding_provider", provider)

        # LM Studio settings
        settings.setValue("ai_lmstudio_url", self.lm_url_input.text().strip())
        settings.setValue("ai_lmstudio_model", self.lm_model_input.text().strip())
        settings.setValue("ai_lmstudio_api_key", self.lm_api_key_input.text().strip())
        settings.setValue("ai_lmstudio_timeout", self.lm_timeout_input.value())

        # Sentence Transformers settings
        settings.setValue("ai_st_model", self.st_model_input.text().strip())

    def load_settings(self) -> None:
        """Load settings from QSettings."""
        from PySide6.QtCore import QSettings

        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

        # Load excluded attributes
        excluded = settings.value("ai_search_excluded_attrs", "")
        self.excluded_attrs_input.setText(excluded)

        # Load LLM settings
        provider = settings.value("ai_embedding_provider", "lmstudio")
        self.provider_combo.setCurrentIndex(0 if provider == "lmstudio" else 1)

        # LM Studio settings
        self.lm_url_input.setText(
            settings.value("ai_lmstudio_url", "http://localhost:8080/v1/embeddings")
        )
        self.lm_model_input.setText(settings.value("ai_lmstudio_model", ""))
        self.lm_api_key_input.setText(settings.value("ai_lmstudio_api_key", ""))
        self.lm_timeout_input.setValue(int(settings.value("ai_lmstudio_timeout", 30)))

        # Sentence Transformers settings
        self.st_model_input.setText(settings.value("ai_st_model", "all-MiniLM-L6-v2"))

    def update_status(self, model: str, counts: str, last_updated: str) -> None:
        """Update the status labels."""
        self.lbl_model.setText(f"Model: {model}")
        self.lbl_indexed_count.setText(f"Indexed: {counts}")
        self.lbl_last_indexed.setText(f"Last Updated: {last_updated}")
