"""
AI Settings Dialog.

Provides configuration for AI features, including Search Index status and
attribute exclusion.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from src.gui.utils.style_helper import StyleHelper


class AISettingsDialog(QDialog):
    """
    Dialog for AI Search settings and index status.
    """

    rebuild_index_requested = Signal(str)  # object_type ('entity', 'event', 'all')
    index_status_requested = Signal()  # Request to refresh index status

    def __init__(self, parent=None):
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

    def _on_rebuild_clicked(self):
        """Handle rebuild button click."""
        obj_type = (
            self.rebuild_combo.currentText().lower().rstrip("s")
        )  # entities->entity
        if obj_type == "all":
            obj_type = "all"
        self.rebuild_index_requested.emit(obj_type)

    def save_settings(self):
        """Save settings to QSettings."""
        from PySide6.QtCore import QSettings

        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        settings.setValue(
            "ai_search_excluded_attrs", self.excluded_attrs_input.text().strip()
        )

    def load_settings(self):
        """Load settings from QSettings."""
        from PySide6.QtCore import QSettings

        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        excluded = settings.value("ai_search_excluded_attrs", "")
        self.excluded_attrs_input.setText(excluded)

    def update_status(self, model: str, counts: str, last_updated: str):
        """Update the status labels."""
        self.lbl_model.setText(f"Model: {model}")
        self.lbl_indexed_count.setText(f"Indexed: {counts}")
        self.lbl_last_indexed.setText(f"Last Updated: {last_updated}")
