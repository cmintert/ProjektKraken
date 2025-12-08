from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QPushButton,
    QHBoxLayout,
)
from PySide6.QtCore import Signal, Qt
from src.core.entities import Entity


class EntityEditorWidget(QWidget):
    """
    A form to edit the details of an Entity.
    Emits 'save_requested' signal with the modified Entity object.
    """

    save_requested = Signal(Entity)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)
        self.layout.setContentsMargins(16, 16, 16, 16)

        # Form Layout
        self.form_layout = QFormLayout()

        self.name_edit = QLineEdit()

        self.type_edit = QComboBox()
        self.type_edit.addItems(["Character", "Location", "Faction", "Item", "Concept"])
        self.type_edit.setEditable(True)

        self.desc_edit = QTextEdit()

        self.form_layout.addRow("Name:", self.name_edit)
        self.form_layout.addRow("Type:", self.type_edit)
        self.form_layout.addRow("Description:", self.desc_edit)

        self.layout.addLayout(self.form_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save Changes")
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)

        self.layout.addLayout(btn_layout)

        # Internal State
        self._current_entity_id = None
        self._current_created_at = 0.0

        # Start disabled
        self.setEnabled(False)

    def load_entity(self, entity: Entity):
        """
        Populates the form with entity data.
        """
        self._current_entity_id = entity.id
        self._current_created_at = entity.created_at

        self.name_edit.setText(entity.name)
        self.type_edit.setCurrentText(entity.type)
        self.desc_edit.setPlainText(entity.description)

        self.setEnabled(True)

    def _on_save(self):
        """
        Collects data and emits save signal.
        """
        if not self._current_entity_id:
            return

        updated_entity = Entity(
            id=self._current_entity_id,
            name=self.name_edit.text(),
            type=self.type_edit.currentText(),
            description=self.desc_edit.toPlainText(),
            created_at=self._current_created_at,
        )

        self.save_requested.emit(updated_entity)

    def clear(self):
        """Clears the editor."""
        self._current_entity_id = None
        self.name_edit.clear()
        self.desc_edit.clear()
        self.setEnabled(False)
