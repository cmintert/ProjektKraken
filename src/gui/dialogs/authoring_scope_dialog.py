"""Choose visible tags and the creation defaults for the current world."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QWidget,
)

from src.core.authoring_scope import AuthoringScope
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.action_flow_layout import ActionFlowLayout
from src.gui.widgets.choice_inputs import ScrollSafeComboBox
from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton


class AuthoringScopeDialog(QDialog):
    """Configure scoped visibility without changing saved content."""

    def __init__(self, scope: AuthoringScope, tags: list[str], parent: QWidget) -> None:
        """Present the world tag catalog and the saved scope."""
        super().__init__(parent)
        self.setWindowTitle("Authoring Scope")
        self.scope = scope
        self.mode = ScrollSafeComboBox()
        self.mode.addItems(["ANY selected tag", "ALL selected tags"])
        self.mode.setCurrentIndex(int(scope.mode == "all"))
        self.visible_tags = declare_inspection(
            QListWidget(),
            "scope-visible-tags|explorer.browsing|help-inspect-scope-visible-tags",
        )
        self.creation_tags = declare_inspection(
            QListWidget(),
            "scope-creation-tags|explorer.browsing|help-inspect-scope-creation-tags",
        )
        self.visible_tags.setAccessibleName("Visible tags")
        self.creation_tags.setAccessibleName("Creation tags")
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.defaults_caption = QLabel()
        self.defaults_caption.setWordWrap(True)
        connect_theme(self, self._apply_style)
        self._apply_style()
        for name in sorted(set(tags) | set(scope.tags), key=str.casefold):
            self._add_tag(self.visible_tags, name, name in scope.tags, name in tags)
            self._add_tag(
                self.creation_tags, name, name in scope.creation_tags, name in tags
            )
        self.visible_tags.itemChanged.connect(self._refresh_defaults)
        self.mode.currentIndexChanged.connect(self._refresh_defaults)
        layout = QFormLayout(self)
        layout.addRow("Match", self.mode)
        layout.addRow("Visible tags", self.visible_tags)
        layout.addRow("Follow Scope", self.defaults_caption)
        layout.addRow(self.creation_tags)
        layout.addRow(self.error)
        actions = ActionFlowLayout()
        for button, slot in (
            (StandardButton("Show All Content"), self._clear_scope),
            (StandardButton("Cancel"), self.reject),
            (PrimaryButton("Apply Scope"), self.accept),
        ):
            button.clicked.connect(slot)
            actions.addWidget(button)
        layout.addRow(actions)
        self._refresh_defaults()

    def _apply_style(self, *_args: object) -> None:
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        self.error.setStyleSheet(StyleHelper.get_error_label_style())
        self.defaults_caption.setStyleSheet(StyleHelper.get_supporting_caption_style())

    @staticmethod
    def _add_tag(
        widget: QListWidget, name: str, checked: bool, available: bool
    ) -> None:
        item = QListWidgetItem(name if available else f"{name} (missing)", widget)
        item.setData(Qt.ItemDataRole.UserRole, name)
        item.setCheckState(
            Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        )

    @staticmethod
    def _checked(widget: QListWidget) -> tuple[str, ...]:
        return tuple(
            item.data(Qt.ItemDataRole.UserRole)
            for index in range(widget.count())
            if (item := widget.item(index)).checkState() == Qt.CheckState.Checked
        )

    def _refresh_defaults(self) -> None:
        tags = self._checked(self.visible_tags)
        choose = self.mode.currentIndex() == 0 and len(tags) > 1
        self.creation_tags.setVisible(choose)
        if choose:
            self.defaults_caption.setText("Choose the tags to add to new entries.")
        elif tags:
            self.defaults_caption.setText("New entries receive all selected tags.")
        else:
            self.defaults_caption.setText("All Content adds no creation tags.")
        for index in range(self.creation_tags.count()):
            item = self.creation_tags.item(index)
            item.setHidden(item.data(Qt.ItemDataRole.UserRole) not in tags)

    def _clear_scope(self) -> None:
        self.scope = AuthoringScope()
        super().accept()

    def accept(self) -> None:
        """Validate ambiguous creation defaults before applying the expression."""
        tags = self._checked(self.visible_tags)
        defaults = tuple(
            tag for tag in self._checked(self.creation_tags) if tag in tags
        )
        try:
            self.scope = AuthoringScope(
                tags, "all" if self.mode.currentIndex() else "any", defaults
            )
        except ValueError as error:
            self.error.setText(str(error))
            return
        super().accept()
