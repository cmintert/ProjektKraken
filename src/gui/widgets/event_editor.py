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
)
from PySide6.QtCore import Signal
from src.core.events import Event


class EventEditorWidget(QWidget):
    """
    A form to edit the details of an Event.
    Emits 'save_requested' signal with the modified Event object.
    """

    save_requested = Signal(Event)

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

    def load_event(self, event: Event):
        """
        Populates the form with event data.

        Args:
            event (Event): The event to edit.
        """
        self._current_event_id = event.id
        self._current_created_at = event.created_at  # Preserve validation data

        self.name_edit.setText(event.name)
        self.date_edit.setValue(event.lore_date)
        self.type_edit.setCurrentText(event.type)
        self.desc_edit.setPlainText(event.description)

        self.setEnabled(True)

    def _on_save(self):
        """
        Collects data from form fields and emits the `save_requested` signal.

        Constructs a new Event object with the updated properties.
        """
        if not self._current_event_id:
            return

        # reconstruct event
        # Note: In a real app we might want to preserve other attributes not shown here
        # For now, we assume this editor owns the full state of these fields.
        updated_event = Event(
            id=self._current_event_id,
            name=self.name_edit.text(),
            lore_date=self.date_edit.value(),
            type=self.type_edit.currentText(),
            description=self.desc_edit.toPlainText(),
            created_at=self._current_created_at,
            # modified_at will normally be updated by the DB trigger or Command,
            # but our dataclass defaults to 'now', so we let the command handle it or use default.
        )

        self.save_requested.emit(updated_event)
