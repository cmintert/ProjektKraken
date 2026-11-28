"""Review an exact key mapping and its checkpoint before applying it."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget

from src.gui.utils.help_context import declare_inspection
from src.gui.widgets.action_flow_layout import ActionFlowLayout
from src.gui.widgets.responsive_form import scrollable_form_page
from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton


class RelationMigrationReview(QWidget):
    """Present a worker review with a separate confirmation action."""

    def __init__(self) -> None:
        """Build a scrollable preview and persistent action row."""
        super().__init__()
        layout = QVBoxLayout(self)
        self.source = QLabel()
        self.source.setTextFormat(Qt.TextFormat.PlainText)
        self.source.setWordWrap(True)
        layout.addWidget(self.source)
        self.destination = declare_inspection(
            QLineEdit(),
            "settings.dictionary.migration-key|settings.relation-dictionary|help-inspect-relation-migration",
        )
        self.destination.setAccessibleName("New relation key")
        self.destination.setPlaceholderText("New relation key")
        layout.addWidget(self.destination)
        content = QWidget()
        body = QVBoxLayout(content)
        self.details = QLabel()
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setWordWrap(True)
        body.addWidget(self.details)
        body.addStretch()
        layout.addWidget(scrollable_form_page(content), 1)
        actions = ActionFlowLayout()
        self.back = StandardButton("Back")
        self.review = PrimaryButton("Review migration")
        self.apply = PrimaryButton("Back up and migrate")
        for button in (self.back, self.review, self.apply):
            button.setAutoDefault(False)
            actions.addWidget(button)
        layout.addLayout(actions)

    def reset(self, key: str) -> None:
        """Return to key entry with a clean review."""
        self.source.setText(f"Current key: {key}")
        self.destination.clear()
        self.show_preview("")
        self.destination.setFocus()

    def show_preview(self, details: str) -> None:
        """Expose confirmation only for the visible reviewed mapping."""
        self.details.setText(details)
        self.apply.setVisible(bool(details))
        self.review.setVisible(not details)
        self.review.setEnabled(bool(self.destination.text().strip()))
