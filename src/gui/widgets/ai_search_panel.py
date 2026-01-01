"""
AI Search Panel Widget Module.

Provides a dockable panel for semantic search with live results and index status.
Supports future content creation features.
"""

from typing import List

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
        score_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(score_label, stretch=1)

        # Make clickable
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
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
        if event.button() == Qt.MouseButton.LeftButton:
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
    result_selected = Signal(str, str)  # object_type, object_id

    def __init__(self, parent=None):
        """
        Initialize the AI Search Panel.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

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
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(StyleHelper.get_empty_state_style())
        results_layout.addWidget(self.empty_label)
        self.empty_label.show()

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #95a5a6; font-size: 10px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        results_layout.addWidget(self.status_label)

        main_layout.addWidget(results_group)

        # Add stretch to push everything to the top
        main_layout.addStretch()

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

    def clear_results(self):
        """Clear the results list."""
        self.results_list.clear()
        self.results_list.hide()
        self.empty_label.setText("No results. Enter a query above.")
        self.empty_label.show()
        self.set_status("")
