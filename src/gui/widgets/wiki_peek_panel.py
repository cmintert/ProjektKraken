"""Read-only reference pane that leaves the active authoring editor intact."""

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper


class WikiPeekPanel(QWidget):
    """Show an existing or provisional wiki target beside the draft."""

    open_requested = Signal(str, str)
    create_requested = Signal(str, str)
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the read-only reference view and its explicit actions."""
        super().__init__(parent)
        self._item_type = ""
        self._item_id = ""
        self._target_name = ""
        layout = QVBoxLayout(self)
        self.title = QLabel("Peek")
        self.detail = QLabel("")
        self.description = QPlainTextEdit()
        self.description.setReadOnly(True)
        self.choices = QListWidget()
        self.choices.hide()
        layout.addWidget(self.title)
        layout.addWidget(self.detail)
        layout.addWidget(self.choices)
        layout.addWidget(self.description, 1)

        actions = QHBoxLayout()
        self.open_button = QPushButton("Open / Edit")
        self.create_entity_button = QPushButton("Create Entity")
        self.create_event_button = QPushButton("Create Event")
        self.close_button = QPushButton("Close Peek")
        for button in (
            self.open_button,
            self.create_entity_button,
            self.create_event_button,
            self.close_button,
        ):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.open_button.clicked.connect(self._open)
        self.create_entity_button.clicked.connect(
            lambda: self.create_requested.emit("entity", self._target_name)
        )
        self.create_event_button.clicked.connect(
            lambda: self.create_requested.emit("event", self._target_name)
        )
        self.close_button.clicked.connect(self.close_requested)
        self.choices.currentRowChanged.connect(self._choose)
        theme_manager = ThemeManager()
        self._apply_theme(theme_manager.get_theme())
        theme_manager.theme_changed.connect(self._apply_theme)

    @Slot(dict)
    def _apply_theme(self, theme: dict) -> None:
        """Repaint Peek content and actions when the application theme changes."""
        self.setStyleSheet(f"background-color: {theme['surface']};")
        self.title.setStyleSheet(
            f"color: {theme['text_main']}; background: transparent;"
            "font-weight: bold;"
        )
        self.detail.setStyleSheet(
            f"color: {theme['text_dim']}; background: transparent;"
        )
        self.description.setStyleSheet(
            f"QPlainTextEdit {{ {StyleHelper.get_input_field_style()} }}"
        )
        self.choices.setStyleSheet(StyleHelper.get_list_widget_style())
        self.open_button.setStyleSheet(StyleHelper.get_primary_button_style())
        for button in (
            self.create_entity_button,
            self.create_event_button,
            self.close_button,
        ):
            button.setStyleSheet(StyleHelper.get_secondary_button_style())

    def show_object(
        self, item_type: str, item_id: str, name: str, description: str
    ) -> None:
        """Display a cached object without making it the global selection."""
        self._item_type = item_type
        self._item_id = item_id
        self._target_name = name
        self.title.setText(name)
        self.detail.setText(item_type.title())
        self.description.setPlainText(description)
        self.choices.hide()
        self.open_button.show()
        self.create_entity_button.hide()
        self.create_event_button.hide()

    def show_provisional(self, target_name: str) -> None:
        """Keep an unresolved authoring reference valid and actionable."""
        self._item_type = ""
        self._item_id = ""
        self._target_name = target_name
        self.title.setText(target_name)
        self.detail.setText("Provisional link · no object yet")
        self.description.setPlainText(
            "This reference stays in your draft. Create an object when ready; "
            "the current editor will stay open."
        )
        self.choices.hide()
        self.open_button.hide()
        self.create_entity_button.show()
        self.create_event_button.show()

    def show_ambiguous(
        self, target_name: str, choices: list[tuple[str, str, str]]
    ) -> None:
        """Ask the reader to choose an exact object before opening it."""
        self._target_name = target_name
        self.title.setText(target_name)
        self.detail.setText("Several objects have this name")
        self.description.setPlainText("Choose an object to inspect or open.")
        self.choices.clear()
        for item_type, item_id, name in choices:
            self.choices.addItem(f"{name} · {item_type.title()} · {item_id[:8]}")
            self.choices.item(self.choices.count() - 1).setData(
                Qt.ItemDataRole.UserRole, (item_type, item_id)
            )
        self.choices.show()
        self.open_button.show()
        self.create_entity_button.hide()
        self.create_event_button.hide()
        self.choices.setCurrentRow(0)

    def show_broken_id(self, target_id: str) -> None:
        """Explain a missing stable ID without creating a misnamed object."""
        self.show_provisional(target_id)
        self.detail.setText("Broken ID link · object not found")
        self.create_entity_button.hide()
        self.create_event_button.hide()

    def _choose(self, row: int) -> None:
        if row < 0:
            return
        data = self.choices.item(row).data(Qt.ItemDataRole.UserRole)
        if isinstance(data, (tuple, list)) and len(data) == 2:  # noqa: PLR2004
            self._item_type, self._item_id = data

    def _open(self) -> None:
        if self._item_type and self._item_id:
            self.open_requested.emit(self._item_type, self._item_id)
