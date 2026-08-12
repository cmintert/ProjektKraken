"""Modern model/view tag editor used by entity and event inspectors."""

from typing import Optional

from PySide6.QtCore import QStringListModel, Qt, Signal, Slot
from PySide6.QtWidgets import QCompleter, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.standard_buttons import StandardButton
from src.gui.widgets.tag_chip_view import TagChipDelegate, TagChipView, TagListModel


class TagEditorWidget(QWidget):
    """Fast tag input with a dedicated entry row and wrapping painted chips."""

    tags_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize editable normalized tag controls."""
        super().__init__(parent)
        self._base_color: Optional[str] = None
        self._suggestions: list[str] = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)

        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Type a tag and press Enter…")
        self.tag_input.setClearButtonEnabled(True)
        self.tag_input.returnPressed.connect(self._on_add)
        self.tag_input.textChanged.connect(self._update_add_button)
        input_layout.addWidget(self.tag_input, stretch=1)

        self.btn_add = StandardButton("Add")
        self.btn_add.setEnabled(False)
        self.btn_add.setToolTip("Add tag")
        self.btn_add.clicked.connect(self._on_add)
        input_layout.addWidget(self.btn_add)
        main_layout.addLayout(input_layout)

        self._completer_model = QStringListModel(self)
        self._completer = QCompleter(self._completer_model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.activated.connect(self._on_completion_activated)
        self.tag_input.setCompleter(self._completer)

        self._model = TagListModel(self)
        self._delegate = TagChipDelegate(self)
        self.tag_view = TagChipView(self)
        self.tag_view.setModel(self._model)
        self.tag_view.setItemDelegate(self._delegate)
        self._delegate.remove_requested.connect(self._remove_row)
        self.tag_view.remove_requested.connect(self._remove_row)
        main_layout.addWidget(self.tag_view)
        main_layout.addStretch(1)

        theme_manager = ThemeManager()
        theme_manager.theme_changed.connect(self._on_theme_changed)
        self._on_theme_changed(theme_manager.get_theme())

    def set_base_color(self, color: str) -> None:
        """Set the chip accent without rebuilding tag items."""
        self._base_color = color
        self._delegate.set_base_color(color)
        self.tag_view.viewport().update()

    def load_tags(self, tags: list[str]) -> None:
        """Replace tags in one model reset without emitting ``tags_changed``."""
        self._model.set_tags(tags)
        self._refresh_completer()
        self._update_add_button()

    def get_tags(self) -> list[str]:
        """Return current tags in display order."""
        return self._model.tags()

    def update_suggestions(self, tags: list[str]) -> None:
        """Replace autocomplete candidates while reusing the completer."""
        self._suggestions = list(tags)
        self._refresh_completer()

    def _refresh_completer(self) -> None:
        selected = set(self._model.tags())
        self._completer_model.setStringList(
            [tag for tag in self._suggestions if tag not in selected]
        )

    def _candidate(self) -> str:
        return self.tag_input.text().strip()

    @Slot()
    def _update_add_button(self, *_args: object) -> None:
        candidate = self._candidate()
        self.btn_add.setEnabled(
            self.isEnabled()
            and bool(candidate)
            and candidate not in self._model.tags()
        )

    @Slot(str)
    def _on_completion_activated(self, tag: str) -> None:
        self.tag_input.setText(tag)
        self._on_add()

    @Slot()
    def _on_add(self) -> None:
        """Append a valid tag and keep keyboard focus in the input."""
        tag = self._candidate()
        if not tag:
            return
        if tag in self._model.tags():
            self.tag_input.clear()
            self.tag_input.setFocus()
            return

        self._model.add_tag(tag)
        self.tag_input.clear()
        self._refresh_completer()
        self.tag_input.setFocus()
        self.tags_changed.emit()

    @Slot(int)
    def _remove_row(self, row: int) -> None:
        """Remove one tag by model row."""
        if not self.isEnabled() or self._model.remove_tag(row) is None:
            return
        self._refresh_completer()
        self._update_add_button()
        self.tags_changed.emit()

    @Slot(dict)
    def _on_theme_changed(self, theme: dict) -> None:
        """Refresh shared controls and repaint all chips once."""
        self.tag_input.setStyleSheet(StyleHelper.get_input_field_style())
        self.tag_view.setStyleSheet(
            "QListView { background: transparent; border: none; outline: none; }"
        )
        self._delegate.set_theme(theme)
        self._delegate.set_base_color(self._base_color)
        self.tag_view.viewport().update()
        self.tag_view.schedule_height_refresh()
