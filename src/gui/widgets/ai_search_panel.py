"""
AI Search Panel Widget Module.

Provides a dockable panel for semantic search with live results and index status.
Supports future content creation features.
"""

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper


class SearchResultItem(QWidget):
    """
    Custom widget for displaying a single search result with metadata.
    """

    # Signal emitted when user clicks to open the result
    open_requested = Signal(str, str)  # object_type, object_id

    def __init__(
        self,
        name: str,
        object_type: str,
        object_id: str,
        score: float,
        obj_subtype: str = "",
        parent=None,
    ):
        """
        Initialize a search result item.

        Args:
            name: Object name.
            object_type: 'entity' or 'event'.
            object_id: Object UUID.
            score: Similarity score (0-1).
            obj_subtype: Entity/Event type (character, location, etc.).
            parent: Parent widget.
        """
        super().__init__(parent)
        self.object_type = object_type
        self.object_id = object_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Name label (bold)
        name_label = QLabel(f"<b>{name}</b>")
        name_label.setWordWrap(True)
        layout.addWidget(name_label, stretch=3)

        # Type badge
        type_text = obj_subtype if obj_subtype else object_type
        type_label = QLabel(f"[{type_text}]")
        type_label.setStyleSheet(
            f"color: {'#3498db' if object_type == 'event' else '#2ecc71'};"
            "font-size: 10px;"
        )
        layout.addWidget(type_label, stretch=1)

        # Score label
        score_label = QLabel(f"{score:.3f}")
        score_label.setStyleSheet("color: #95a5a6; font-size: 10px;")
        score_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(score_label, stretch=1)

        # Make clickable
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "SearchResultItem:hover { background-color: rgba(255, 255, 255, 0.1); }"
        )
        self.setMinimumHeight(40)

    def sizeHint(self):
        """Ensure item has sufficient height."""
        size = super().sizeHint()
        return size.expandedTo(self.minimumSize())

    def mousePressEvent(self, event):
        """Handle mouse click to open the result."""
        if event.button() == Qt.LeftButton:
            self.open_requested.emit(self.object_type, self.object_id)
        super().mousePressEvent(event)


class AISearchPanelWidget(QWidget):
    """
    A dockable panel providing semantic search with live results and index status.

    Follows the "Dumb UI" pattern: emits signals for all user actions,
    displays data passed from controller.
    """

    # Signals for user actions
    search_requested = Signal(str, str, int)  # query_text, object_type_filter, top_k
    rebuild_index_requested = Signal(str)  # object_type ('entity', 'event', 'all')
    result_selected = Signal(str, str)  # object_type, object_id
    index_status_requested = Signal()  # Request to refresh index status

    def __init__(self, parent=None):
        """
        Initialize the AI Search Panel.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)

        # Main layout
        main_layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(main_layout)

        # === Search Section ===
        search_group = QGroupBox("Semantic Search")
        search_layout = QVBoxLayout(search_group)
        StyleHelper.apply_standard_list_spacing(search_layout)

        # Search input
        search_input_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search query...")
        self.search_input.returnPressed.connect(self._on_search_clicked)
        search_input_layout.addWidget(self.search_input)

        self.btn_search = QPushButton("Search")
        self.btn_search.clicked.connect(self._on_search_clicked)
        search_input_layout.addWidget(self.btn_search)

        search_layout.addLayout(search_input_layout)

        # Filters
        filter_layout = QHBoxLayout()

        # Type filter
        filter_layout.addWidget(QLabel("Filter:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Entities", "Events"])
        filter_layout.addWidget(self.filter_combo, stretch=1)

        # Top-K control
        filter_layout.addWidget(QLabel("Results:"))
        self.top_k_spin = QSpinBox()
        self.top_k_spin.setMinimum(1)
        self.top_k_spin.setMaximum(100)
        self.top_k_spin.setValue(10)
        filter_layout.addWidget(self.top_k_spin)

        search_layout.addLayout(filter_layout)

        main_layout.addWidget(search_group)

        # === Results Section ===
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        StyleHelper.apply_standard_list_spacing(results_layout)

        # Results list
        self.results_list = QListWidget()
        self.results_list.setSelectionMode(QListWidget.NoSelection)
        results_layout.addWidget(self.results_list)

        # Empty state
        self.empty_label = QLabel("No results. Enter a query above.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(StyleHelper.get_empty_state_style())
        results_layout.addWidget(self.empty_label)
        self.empty_label.show()

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #95a5a6; font-size: 10px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        results_layout.addWidget(self.status_label)

        main_layout.addWidget(results_group)

        # === Index Status Section ===
        index_group = QGroupBox("Index Status")
        index_layout = QVBoxLayout(index_group)
        StyleHelper.apply_standard_list_spacing(index_layout)

        # Status display
        status_grid = QVBoxLayout()

        self.lbl_model = QLabel("Model: --")
        self.lbl_model.setStyleSheet("font-size: 10px;")
        status_grid.addWidget(self.lbl_model)

        self.lbl_indexed_count = QLabel("Indexed: --")
        self.lbl_indexed_count.setStyleSheet("font-size: 10px;")
        status_grid.addWidget(self.lbl_indexed_count)

        self.lbl_last_indexed = QLabel("Last Updated: --")
        self.lbl_last_indexed.setStyleSheet("font-size: 10px;")
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

        # === Future: Content Creation Section (Placeholder) ===
        # This section will be activated in future updates
        # creation_group = QGroupBox("AI Content Creation (Coming Soon)")
        # creation_layout = QVBoxLayout(creation_group)
        # placeholder_label = QLabel(
        #     "Future features:\n"
        #     "• AI-assisted descriptions\n"
        #     "• Related content suggestions\n"
        #     "• Attribute generation"
        # )
        # placeholder_label.setStyleSheet("color: #95a5a6; font-size: 10px;")
        # creation_layout.addWidget(placeholder_label)
        # main_layout.addWidget(creation_group)

        # Add stretch to push everything to the top
        main_layout.addStretch()

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

        # Load settings
        self.load_settings()

    def get_excluded_attributes(self) -> List[str]:
        """
        Get list of attributes to exclude from indexing.

        Returns:
            List[str]: List of attribute keys.
        """
        text = self.excluded_attrs_input.text().strip()
        if not text:
            return []
        return [attr.strip() for attr in text.split(",") if attr.strip()]

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
        excluded = settings.value("ai_search_excluded_attrs", "", type=str)
        self.excluded_attrs_input.setText(excluded)

    def _on_search_clicked(self):
        """Handle search button click."""
        query = self.search_input.text().strip()
        if not query:
            self.set_status("Please enter a search query.")
            return

        # Map filter to object type
        filter_text = self.filter_combo.currentText()
        object_type_filter = ""
        if filter_text == "Entities":
            object_type_filter = "entity"
        elif filter_text == "Events":
            object_type_filter = "event"

        top_k = self.top_k_spin.value()

        self.search_requested.emit(query, object_type_filter, top_k)

    def _on_rebuild_clicked(self):
        """Handle rebuild index button click."""
        rebuild_type = self.rebuild_combo.currentText().lower()
        if rebuild_type == "entities":
            rebuild_type = "entity"
        elif rebuild_type == "events":
            rebuild_type = "event"

        self.rebuild_index_requested.emit(rebuild_type)

    def set_results(self, results: List[dict]):
        """
        Display search results.

        Args:
            results: List of result dicts with keys:
                - name: str
                - object_type: str ('entity' or 'event')
                - object_id: str
                - score: float
                - type: str (entity/event subtype)
        """
        self.results_list.clear()

        if not results:
            self.results_list.hide()
            self.empty_label.setText("No results found.")
            self.empty_label.show()
            self.set_status("")
            return

        self.results_list.show()
        self.empty_label.hide()

        for result in results:
            # Create custom widget
            result_widget = SearchResultItem(
                name=result.get("name", "Unknown"),
                object_type=result.get("object_type", ""),
                object_id=result.get("object_id", ""),
                score=result.get("score", 0.0),
                obj_subtype=result.get("type", ""),
            )
            result_widget.open_requested.connect(self.result_selected.emit)

            # Add to list
            item = QListWidgetItem(self.results_list)
            item.setSizeHint(result_widget.sizeHint())
            self.results_list.addItem(item)
            self.results_list.setItemWidget(item, result_widget)

        self.set_status(f"Found {len(results)} result(s)")

    def set_status(self, message: str):
        """
        Set the status message below results.

        Args:
            message: Status message to display.
        """
        self.status_label.setText(message)

    def set_index_status(
        self,
        model: Optional[str] = None,
        indexed_count: Optional[int] = None,
        last_indexed: Optional[str] = None,
    ):
        """
        Update the index status display.

        Args:
            model: Current model name.
            indexed_count: Total number of indexed objects.
            last_indexed: Last indexed timestamp (formatted string).
        """
        if model:
            self.lbl_model.setText(f"Model: {model}")
        else:
            self.lbl_model.setText("Model: Not configured")

        if indexed_count is not None:
            self.lbl_indexed_count.setText(f"Indexed: {indexed_count} objects")
        else:
            self.lbl_indexed_count.setText("Indexed: --")

        if last_indexed:
            self.lbl_last_indexed.setText(f"Last Updated: {last_indexed}")
        else:
            self.lbl_last_indexed.setText("Last Updated: Never")

    def set_searching(self, searching: bool):
        """
        Update UI to show search in progress.

        Args:
            searching: True if search is in progress.
        """
        self.btn_search.setEnabled(not searching)
        self.search_input.setEnabled(not searching)
        if searching:
            self.set_status("Searching...")

    def set_rebuilding(self, rebuilding: bool):
        """
        Update UI to show index rebuild in progress.

        Args:
            rebuilding: True if rebuild is in progress.
        """
        self.btn_rebuild.setEnabled(not rebuilding)
        self.rebuild_combo.setEnabled(not rebuilding)
        if rebuilding:
            selected = self.rebuild_combo.currentText()
            self.set_status(f"Rebuilding {selected} index...")

    def clear_results(self):
        """Clear the results list."""
        self.results_list.clear()
        self.results_list.hide()
        self.empty_label.setText("No results. Enter a query above.")
        self.empty_label.show()
        self.set_status("")
