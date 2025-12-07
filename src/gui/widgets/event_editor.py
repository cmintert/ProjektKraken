from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QDoubleSpinBox,
    QComboBox,
    QPushButton,
    QLabel,
    QHBoxLayout,
    QGroupBox,
    QListWidget,
    QInputDialog,
    QMessageBox,
)
from PySide6.QtCore import Signal
from src.core.events import Event


class EventEditorWidget(QWidget):
    """
    A form to edit the details of an Event.
    Emits 'save_requested' signal with the modified Event object.
    Emits 'add_relation_requested' signal (source, target, type).
    """

    save_requested = Signal(Event)
    add_relation_requested = Signal(str, str, str)  # source_id, target_id, type

    def __init__(self, parent=None):
        """
        Initializes the editor widget with form fields.

        Args:
            parent: The parent widget, if any.
        """
        super().__init__(parent)
        self.layout = QVBoxLayout(self)

        # Form Layout
        self.form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.date_edit = QDoubleSpinBox()
        self.date_edit.setRange(-1e12, 1e12)  # Cosmic scale
        self.date_edit.setDecimals(2)

        self.type_edit = QComboBox()
        self.type_edit.addItems(
            ["generic", "cosmic", "historical", "personal", "session", "combat"]
        )
        self.type_edit.setEditable(True)  # Allow custom types

        self.desc_edit = QTextEdit()

        self.form_layout.addRow("Name:", self.name_edit)
        self.form_layout.addRow("Lore Date:", self.date_edit)
        self.form_layout.addRow("Type:", self.type_edit)
        self.form_layout.addRow("Description:", self.desc_edit)

        self.layout.addLayout(self.form_layout)

        # Relations Group
        self.rel_group = QGroupBox("Relationships")
        self.rel_layout = QVBoxLayout()

        self.rel_list = QListWidget()
        self.rel_layout.addWidget(self.rel_list)

        rel_btn_layout = QHBoxLayout()
        self.btn_add_rel = QPushButton("Add Relation")
        self.btn_add_rel.clicked.connect(self._on_add_relation)
        rel_btn_layout.addWidget(self.btn_add_rel)
        self.rel_layout.addLayout(rel_btn_layout)

        self.rel_group.setLayout(self.rel_layout)
        self.layout.addWidget(self.rel_group)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save Changes")
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)

        self.layout.addLayout(btn_layout)

        # Internal State
        self._current_event_id = None
        self._current_created_at = 0.0

        # Start disabled until specific event loaded
        self.setEnabled(False)

    def load_event(self, event: Event, relations: list = None):
        """
        Populates the form with event data.

        Args:
            event (Event): The event to edit.
            relations (list): List of relation dicts [Optional].
        """
        self._current_event_id = event.id
        self._current_created_at = event.created_at  # Preserve validation data

        self.name_edit.setText(event.name)
        self.date_edit.setValue(event.lore_date)
        self.type_edit.setCurrentText(event.type)
        self.desc_edit.setPlainText(event.description)

        # Load relations
        self.rel_list.clear()
        if relations:
            for rel in relations:
                # Format: -> TargetID [Type]
                # In real app, we'd look up Target Name.
                label = f"-> {rel['target_id']} [{rel['rel_type']}]"
                self.rel_list.addItem(label)

        self.setEnabled(True)

    def _on_save(self):
        """
        Collects data from form fields and emits the `save_requested` signal.

        Constructs a new Event object with the updated properties.
        """
        if not self._current_event_id:
            return

        updated_event = Event(
            id=self._current_event_id,
            name=self.name_edit.text(),
            lore_date=self.date_edit.value(),
            type=self.type_edit.currentText(),
            description=self.desc_edit.toPlainText(),
            created_at=self._current_created_at,
        )

        self.save_requested.emit(updated_event)

    def _on_add_relation(self):
        """
        Prompts user for relation details and emits signal.

        Shows input dialogs for 'Target ID' and 'Relation Type'.
        If valid input is received, emits `add_relation_requested`.
        """
        if not self._current_event_id:
            return

        target_id, ok = QInputDialog.getText(self, "Add Relation", "Target ID:")
        if not ok or not target_id:
            return

        rel_type, ok = QInputDialog.getItem(
            self,
            "Relation Type",
            "Type:",
            ["caused", "involved", "located_at", "parent_of"],
            0,
            True,
        )
        if not ok:
            return

        self.add_relation_requested.emit(self._current_event_id, target_id, rel_type)
