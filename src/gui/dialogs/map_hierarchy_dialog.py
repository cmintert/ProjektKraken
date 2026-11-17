"""Bounded, nonpermanent map hierarchy browser and intent picker."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QDialog,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.map import Map
from src.core.map_hierarchy import HierarchyError, MapHierarchy
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.wrapping_buttons import WrappingPushButton as StandardButton


class MapHierarchyDialog(QDialog):
    """Show roots and descendants without persisting or moving data."""

    def __init__(
        self, maps: list[Map], active_id: str | None, parent: QWidget | None = None
    ) -> None:
        """Build a hierarchy tree and explicit actions from detached maps."""
        super().__init__(parent)
        declare_inspection(
            self, "map.hierarchy.dialog|map.hierarchy|help-inspect-map-hierarchy-tree"
        )
        self.setWindowTitle("Manage Map Hierarchy")
        self.resize(520, 560)
        self.intent: tuple[str, str] | None = None
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Independent maps can contain detail maps. Moving a map also moves "
            "its descendants; their content and local coordinates stay unchanged."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.tree = declare_inspection(
            QTreeWidget(),
            "map.hierarchy.tree|map.settings|help-inspect-map-hierarchy-tree",
        )
        self.tree.setHeaderLabels(["Map", "Relationship"])
        self.tree.setAccessibleName("Map hierarchy")
        layout.addWidget(self.tree)
        hierarchy = MapHierarchy(maps)
        diagnostics = hierarchy.diagnostics()
        items = {}
        for record in maps:
            parent_id = (record.attributes or {}).get("parent_map_id")
            item = QTreeWidgetItem(
                [record.name, "Detail map" if parent_id else "Independent"]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, record.id)
            item.setToolTip(
                0, "\n".join((record.name, *diagnostics.get(record.id, ())))
            )
            items[record.id] = item
        for record in maps:
            parent_id = (record.attributes or {}).get("parent_map_id")
            # Invalid chains stay visible at the top and can be explicitly repaired.
            try:
                hierarchy.ancestors(record.id)
                valid_chain = True
            except HierarchyError:
                valid_chain = False
            if isinstance(parent_id, str) and parent_id in items and valid_chain:
                items[parent_id].addChild(items[record.id])
            else:
                self.tree.addTopLevelItem(items[record.id])
        self.tree.expandAll()
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._buttons = {}
        for intent, label in (
            ("attach", "Attach or change parent…"),
            ("detach", "Make independent"),
            ("placement", "Edit placement"),
            ("navigate", "Navigate to map"),
        ):
            button = StandardButton(label)
            button.setStyleSheet(StyleHelper.get_secondary_button_style())
            button.setAutoDefault(False)
            button.clicked.connect(
                lambda checked=False, action=intent: self._choose(action)
            )
            layout.addWidget(button)
            self._buttons[intent] = button
        close = StandardButton("Close")
        close.setAutoDefault(False)
        self._close_button = close
        close.clicked.connect(self.reject)
        layout.addWidget(close)
        self._maps = {record.id: record for record in maps}
        self.tree.currentItemChanged.connect(self._refresh_actions)
        if active_id in items:
            self.tree.setCurrentItem(items[active_id])
        self._refresh_actions()
        connect_theme(self, self._apply_theme)

    def _apply_theme(self, _theme: dict) -> None:
        for button in (*self._buttons.values(), self._close_button):
            button.setStyleSheet(StyleHelper.get_secondary_button_style())

    def _refresh_actions(self) -> None:
        item = self.tree.currentItem()
        record = (
            self._maps.get(item.data(0, Qt.ItemDataRole.UserRole)) if item else None
        )
        for button in self._buttons.values():
            button.setEnabled(record is not None)
        has_parent = bool(record and (record.attributes or {}).get("parent_map_id"))
        self._buttons["detach"].setEnabled(has_parent)
        self._buttons["placement"].setEnabled(has_parent)

    def _choose(self, action: str) -> None:
        item = self.tree.currentItem()
        if item is not None:
            self.intent = (action, item.data(0, Qt.ItemDataRole.UserRole))
            self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Enter activates the focused action; Escape closes without an intent."""
        focused = self.focusWidget()
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if isinstance(focused, QAbstractButton) and focused.isEnabled():
                focused.click()
                event.accept()
                return
        super().keyPressEvent(event)
