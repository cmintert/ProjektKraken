"""Shared, presentation-only Entity World Context mode control."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.core.entity_context_mode import ENTITY_CONTEXT_LABELS
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.wrapping_combo_box import WrappingComboBox


class EntityContextModeSelector(QWidget):
    """Emit explicit mode intent without owning session state or temporal logic."""

    mode_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Expose complete mode labels in a vertically reflowable control."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel("Context mode")
        self.combo = declare_inspection(
            WrappingComboBox(),
            "entity-world-context-mode|writing.ai|help-entity-world-context-mode",
        )
        self.combo.setAccessibleName("Entity World Context mode")
        self.label.setBuddy(self.combo)
        for mode, label in ENTITY_CONTEXT_LABELS.items():
            self.combo.addItem(label, mode.value)
        self.combo.currentIndexChanged.connect(self._changed)
        layout.addWidget(self.label)
        layout.addWidget(self.combo)
        connect_theme(self, self._apply_theme)
        self._apply_theme()

    def _apply_theme(self, _theme: dict | None = None) -> None:
        self.combo.setStyleSheet(StyleHelper.get_input_field_style())

    def _changed(self, _index: int) -> None:
        self.mode_changed.emit(self.mode)

    @property
    def mode(self) -> str:
        """Return the explicitly selected mode identifier."""
        return str(self.combo.currentData())

    def set_mode(self, mode: str) -> None:
        """Reflect coordinator state without emitting another intent."""
        self.combo.blockSignals(True)
        self.combo.setCurrentIndex(self.combo.findData(mode))
        self.combo.blockSignals(False)
