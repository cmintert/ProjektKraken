"""Readable, detached review of an Event timing cascade."""

from collections import Counter
from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.dialogs.help_aware_dialog import HelpAwareDialog
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.responsive_dialog_buttons import ResponsiveDialogButtonBox
from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton


class EventTimingReviewDialog(HelpAwareDialog):
    """Show every changed item before applying one reversible operation."""

    def __init__(
        self, consequences: list[dict[str, Any]], parent: QWidget | None = None
    ) -> None:
        """Render completed review snapshots without performing any calculation."""
        super().__init__(parent)
        self.setWindowTitle("Review date changes")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumSize(320, 300)
        self.resize(680, 560)
        layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(layout)
        counts = Counter(str(item["kind"]) for item in consequences)
        summary = ", ".join(
            f"{count} {kind.title() if count == 1 else kind.title() + 's'}"
            for kind, count in counts.items()
        )
        layout.addWidget(self._label(summary, heading=True))
        layout.addWidget(
            self._label(
                "Check the dates and affected uses below. Apply changes saves them "
                "together with one Undo. Cancel keeps your draft."
            )
        )
        self.changes = QScrollArea(self)
        self.changes.setWidgetResizable(True)
        self.changes.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.changes.setStyleSheet(StyleHelper.get_scroll_area_style())
        content = QWidget()
        rows = QVBoxLayout(content)
        StyleHelper.apply_compact_spacing(rows)
        rows.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._cards: list[QFrame] = []
        for item in consequences:
            card = QFrame(content)
            card.setObjectName("temporal_card")
            card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            row = QVBoxLayout(card)
            StyleHelper.apply_standard_list_spacing(row)
            row.addWidget(
                self._label(
                    f"{str(item['kind']).title()} · {item['name']}", heading=True
                )
            )
            for title, key in (("Before", "before_text"), ("After", "after_text")):
                row.addWidget(self._label(title, heading=True))
                row.addWidget(self._label(str(item[key])))
            if item["before_text"] == item["after_text"]:
                row.addWidget(
                    self._label(
                        "Timing details changed; the displayed dates are unchanged."
                    )
                )
            rows.addWidget(card)
            self._cards.append(card)
        self.changes.setWidget(content)
        layout.addWidget(self.changes, 1)
        self.button_box = declare_inspection(
            ResponsiveDialogButtonBox(self),
            "event-timing-review-actions|event.timing|help-inspect-event-timing-review-actions",
        )
        self.apply_button = PrimaryButton("Apply changes", self)
        self.cancel_button = StandardButton("Cancel", self)
        self.button_box.addButton(
            self.apply_button, ResponsiveDialogButtonBox.ButtonRole.AcceptRole
        )
        self.button_box.addButton(
            self.cancel_button, ResponsiveDialogButtonBox.ButtonRole.RejectRole
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.cancel_button.setDefault(True)
        self.cancel_button.setFocus()
        layout.addWidget(self.button_box)
        self._apply_theme()
        connect_theme(self, self._apply_theme)

    @staticmethod
    def _label(text: str, *, heading: bool = False) -> QLabel:
        """Keep names and date explanations selectable, wrapped plain text."""
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if heading:
            font = label.font()
            font.setBold(True)
            label.setFont(font)
        return label

    @Slot()
    def _apply_theme(self) -> None:
        """Reuse shared dialog, temporal-card and action presentation roles."""
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        StyleHelper.apply_read_only_palette(self)
        for card in self._cards:
            card.setStyleSheet(StyleHelper.get_temporal_card_style())
