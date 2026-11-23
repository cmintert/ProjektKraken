"""A nonmodal draft for one connection in the Relations graph."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.action_flow_layout import ActionFlowLayout
from src.gui.widgets.choice_inputs import ScrollSafeComboBox
from src.gui.widgets.relation_type_picker import relation_type_combo
from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton


class GraphConnectionDialog(QDialog):
    """Render and validate the fields of a graph relationship draft."""

    target_requested = Signal(str)
    save_requested = Signal(str, str, bool)
    edit_requested = Signal(dict)

    def __init__(self, source: str, types: list[str], parent: QWidget) -> None:
        """Expose direct manipulation and keyboard workflows through one draft."""
        super().__init__(parent)
        self.setWindowTitle("Connect Entries")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._has_target = False
        self._awaiting_relations = False
        self._pending = False
        layout = QVBoxLayout(self)
        self.source_caption = self._caption(source)
        self.target_caption = self._caption("")
        form = QFormLayout()
        form.addRow("From", self.source_caption)
        form.addRow("To", self.target_caption)
        layout.addLayout(form)

        choices = ActionFlowLayout()
        self.target_choices = QWidget(self)
        self.target_choices.setLayout(choices)
        for kind, label in (
            ("entity", "Create Entity"),
            ("event", "Create Event"),
            ("existing", "Connect Existing"),
        ):
            button = StandardButton(label)
            button.clicked.connect(
                lambda _checked=False, target=kind: self.target_requested.emit(target)
            )
            choices.addWidget(button)
        layout.addWidget(self.target_choices)

        self.fields = QWidget(self)
        fields = QFormLayout(self.fields)
        self.existing = ScrollSafeComboBox()
        self.existing.setAccessibleName("Existing relationships")
        self.existing.currentIndexChanged.connect(self._update_actions)
        fields.addRow("Existing relationships", self.existing)
        self.edit_button = StandardButton("Edit Existing")
        self.edit_button.clicked.connect(self._edit_existing)
        fields.addRow(self.edit_button)
        self.type_field = relation_type_combo()
        self.type_field.setAccessibleName("Relation type")
        self.type_field.addItems(
            sorted(
                {"related", *(kind for kind in types if kind.casefold() != "mentions")}
            )
        )
        self.type_field.setCurrentIndex(-1)
        self.type_field.setPlaceholderText("Choose a relation type")
        self.type_field.currentTextChanged.connect(self._update_actions)
        fields.addRow("Relation type", self.type_field)
        self.direction = ScrollSafeComboBox()
        for label, value in (
            ("From → To", "forward"),
            ("To → From", "reverse"),
            ("Both directions", "reciprocal"),
        ):
            self.direction.addItem(label, value)
        fields.addRow("Direction", self.direction)
        self.undated = QLabel("Undated")
        self.start_at_playhead = declare_inspection(
            QCheckBox("Start at Playhead"),
            "graph-start-at-playhead|graph.exploring|help-inspect-graph-start-at-playhead",
        )
        self.start_at_playhead.toggled.connect(self.undated.setHidden)
        fields.addRow("Timing", self.undated)
        fields.addRow(self.start_at_playhead)
        layout.addWidget(self.fields)

        self.error = self._caption("")
        self.error.setAccessibleName("Graph draft status")
        layout.addWidget(self.error)
        actions = ActionFlowLayout()
        self.cancel_button = StandardButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.save = declare_inspection(
            PrimaryButton("Create Relationship"),
            "graph-save-relationship|graph.exploring|help-inspect-graph-save-relationship",
        )
        self.save.clicked.connect(self._submit)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.save)
        layout.addLayout(actions)
        for action_button in self.findChildren(QPushButton):
            action_button.setAutoDefault(False)
        connect_theme(self, self._apply_style)
        self._apply_style()
        self.set_target("")

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        return label

    def _apply_style(self, *_args: object) -> None:
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        self.error.setStyleSheet(StyleHelper.get_error_label_style())

    def set_target(self, target: str, *, awaiting_relations: bool = False) -> None:
        """Present the target and whether its canonical relations are loading."""
        self._has_target = bool(target)
        self._awaiting_relations = awaiting_relations
        self.target_caption.setText(target or "Choose an existing or new entry")
        self.fields.setVisible(self._has_target)
        self.target_choices.setVisible(not self._has_target)
        self.save.setVisible(self._has_target)
        self.set_relations([])

    def set_relations(self, rows: list[tuple[str, dict]]) -> None:
        """Show authored and protected existing rows distinctly."""
        self.existing.clear()
        caption = "Checking relationships…" if self._awaiting_relations else "None"
        self.existing.addItem("Choose an existing relationship" if rows else caption)
        for label, row in rows:
            self.existing.addItem(label, row)
        self._update_actions()

    def pair_ready(self, rows: list[tuple[str, dict]]) -> None:
        """Allow saving after canonical relationship inspection has completed."""
        self._awaiting_relations = False
        self.set_relations(rows)
        self.type_field.setFocus()

    def set_pending(self, pending: bool, message: str = "") -> None:
        """Lock submitted controls while retaining recoverable input."""
        self._pending = pending
        self.fields.setEnabled(not pending)
        self.target_choices.setEnabled(not pending)
        self.error.setText(message)
        self._update_actions()

    def _update_actions(self, *_args: object) -> None:
        if not hasattr(self, "save"):
            return
        kind = self.type_field.currentText().strip()
        self.save.setEnabled(
            self._has_target
            and not self._pending
            and not self._awaiting_relations
            and bool(kind)
            and kind.casefold() != "mentions"
        )
        row = self.existing.currentData()
        self.edit_button.setEnabled(
            not self._pending
            and isinstance(row, dict)
            and row.get("rel_type", "").casefold() != "mentions"
        )

    def _edit_existing(self) -> None:
        row = self.existing.currentData()
        if isinstance(row, dict):
            self.edit_requested.emit(row)

    def _submit(self) -> None:
        self.save_requested.emit(
            self.type_field.currentText().strip(),
            self.direction.currentData(),
            self.start_at_playhead.isChecked(),
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Let Enter act on a focused button without saving from text fields."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            target = self.focusWidget()
            if isinstance(target, QPushButton) and target.isEnabled():
                target.click()
            event.accept()
            return
        super().keyPressEvent(event)
