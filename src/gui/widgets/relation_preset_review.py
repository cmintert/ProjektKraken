"""Keyboard-accessible selection and review for one portable preset."""

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.help_context import declare_inspection
from src.gui.widgets.action_flow_layout import ActionFlowLayout
from src.gui.widgets.responsive_form import scrollable_form_page
from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton

_OPTIONS = {
    "export": (("Export", "export"), ("Skip", "keep")),
    "addition": (("Import", "import"), ("Skip", "keep")),
    "conflict": (
        ("Choose an action", ""),
        ("Keep existing", "keep"),
        ("Replace", "replace"),
    ),
}
_CAPTIONS = {
    "addition": "Addition",
    "match": "Already present",
    "conflict": "Conflict",
    "unavailable": "Unavailable",
}


class RelationPresetReview(QWidget):
    """Present a detached list of keys and the author’s choices."""

    def __init__(self) -> None:
        """Build a stacked layout suitable for narrow dialog widths."""
        super().__init__()
        self.rows: dict[str, tuple[str, str]] = {}
        self.choices: dict[str, str] = {}
        layout = QVBoxLayout(self)
        self.keys = declare_inspection(
            QListWidget(),
            "settings.dictionary.preset-keys|settings.relation-dictionary|help-inspect-relation-preset-review",
        )
        self.keys.setAccessibleName("Preset definitions")
        self.keys.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        layout.addWidget(self.keys, 1)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        self.details = QLabel()
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setWordWrap(True)
        self.details.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        content_layout.addWidget(self.details)
        content_layout.addStretch()
        self.details_scroll = scrollable_form_page(content)
        layout.addWidget(self.details_scroll, 2)
        self.decision = declare_inspection(
            QComboBox(),
            "settings.dictionary.preset-decision|settings.relation-dictionary|help-inspect-relation-preset-review",
        )
        self.decision.setAccessibleName("Decision for selected definition")
        layout.addWidget(self.decision)
        actions = ActionFlowLayout()
        self.cancel = StandardButton("Cancel")
        self.confirm = PrimaryButton("Import definitions")
        for button in (self.cancel, self.confirm):
            button.setAutoDefault(False)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.keys.currentItemChanged.connect(self._select)
        self.decision.currentIndexChanged.connect(self._choose)

    def show_rows(self, rows: dict[str, tuple[str, str]], *, exporting: bool) -> None:
        """Reset the choices for a fresh review."""
        self.rows = rows
        self.choices = {
            key: _OPTIONS[status][0][1]
            for key, (status, _) in rows.items()
            if status in _OPTIONS
        }
        self.confirm.setText("Save preset…" if exporting else "Import definitions")
        with QSignalBlocker(self.keys):
            self.keys.clear()
            for key in rows:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, key)
                item.setToolTip(key)
                self.keys.addItem(item)
                self._caption(item)
        self.keys.setCurrentRow(0)
        self._select(self.keys.currentItem())
        self.keys.setFocus()
        self._sync_confirm()

    def _caption(self, item: QListWidgetItem) -> None:
        key = item.data(Qt.ItemDataRole.UserRole)
        status = self.rows[key][0]
        choice = self.choices.get(key, "")
        label = dict((value, name) for name, value in _OPTIONS.get(status, ())).get(
            choice
        )
        parts = [key, _CAPTIONS.get(status), label]
        item.setText(" · ".join(part for part in parts if part))

    def _select(self, item: QListWidgetItem | None) -> None:
        if item is None:
            self.details.clear()
            self.decision.hide()
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        status, details = self.rows[key]
        self.details.setText(details)
        self.details_scroll.verticalScrollBar().setValue(0)
        options = _OPTIONS.get(status, ())
        with QSignalBlocker(self.decision):
            self.decision.clear()
            for caption, value in options:
                self.decision.addItem(caption, value)
            self.decision.setCurrentIndex(self.decision.findData(self.choices.get(key)))
        self.decision.setVisible(bool(options))

    def _choose(self) -> None:
        item = self.keys.currentItem()
        if item is not None:
            self.choices[item.data(Qt.ItemDataRole.UserRole)] = (
                self.decision.currentData()
            )
            self._caption(item)
            self._sync_confirm()

    def _sync_confirm(self) -> None:
        choices = self.choices.values()
        self.confirm.setEnabled(
            all(choices)
            and any(choice in {"export", "import", "replace"} for choice in choices)
        )
