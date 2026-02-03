"""Explorer Model Module.

Provides a virtualized QAbstractListModel for the project explorer list view.
"""

import logging
from typing import Any, List, Optional, Union

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor

from src.core.calendar import CalendarConverter
from src.core.entities import Entity
from src.core.events import Event

logger = logging.getLogger(__name__)


class ExplorerModel(QAbstractListModel):
    """A virtualized list model for displaying Events and Entities.

    This model supports efficient rendering of large datasets by only creating
    visual representations for visible items. Uses Qt's Model/View architecture
    for automatic virtualization.
    """

    # Custom roles for storing item metadata
    ItemIdRole = Qt.ItemDataRole.UserRole + 1
    ItemTypeRole = Qt.ItemDataRole.UserRole + 2
    ItemNameRole = Qt.ItemDataRole.UserRole + 3
    ItemObjectRole = Qt.ItemDataRole.UserRole + 4

    def __init__(self, parent: Optional[Any] = None) -> None:
        """Initialize the explorer model.

        Args:
            parent: Parent QObject.
        """
        super().__init__(parent)
        self._items: List[tuple[str, Union[Event, Entity]]] = []
        self._calendar_converter: Optional[CalendarConverter] = None
        
        # Theme colors
        from src.core.theme_manager import ThemeManager
        theme = ThemeManager().get_theme()
        self.color_event = QColor(theme.get("accent_secondary", "#0078D4"))
        self.color_entity = QColor(theme.get("primary", "#FF9900"))
        
        # Connect to theme changes
        ThemeManager().theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, theme: dict) -> None:
        """Handle theme changes.

        Args:
            theme: New theme dictionary.
        """
        self.color_event = QColor(theme.get("accent_secondary", "#0078D4"))
        self.color_entity = QColor(theme.get("primary", "#FF9900"))
        # Notify view to repaint all items
        if self._items:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._items) - 1, 0)
            self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.ForegroundRole])

    def set_calendar_converter(self, converter: Optional[CalendarConverter]) -> None:
        """Set the calendar converter for date formatting.

        Args:
            converter: CalendarConverter instance or None.
        """
        self._calendar_converter = converter
        # Trigger repaint of event items (those with dates)
        if self._items:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._items) - 1, 0)
            self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.DisplayRole])

    def set_items(self, items: List[tuple[str, Union[Event, Entity]]]) -> None:
        """Set the items to display in the model.

        Args:
            items: List of (item_type, object) tuples.
        """
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of items in the model.

        Args:
            parent: Parent index (unused for list models).

        Returns:
            Number of items.
        """
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return data for the given index and role.

        Args:
            index: Model index.
            role: Data role.

        Returns:
            Data for the requested role, or None.
        """
        if not index.isValid() or index.row() >= len(self._items):
            return None

        item_type, obj = self._items[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            # Return display text
            if item_type == "entity":
                return f"{obj.name} ({obj.type})"
            else:
                # Format lore date
                if self._calendar_converter and obj.lore_date is not None:
                    date_str = self._format_compact_date(obj.lore_date)
                else:
                    date_str = str(obj.lore_date)
                return f"[{date_str}] {obj.name}"

        elif role == Qt.ItemDataRole.ForegroundRole:
            # Return color
            if item_type == "entity":
                return QBrush(self.color_entity)
            else:
                return QBrush(self.color_event)

        elif role == Qt.ItemDataRole.CheckStateRole:
            # Support checkboxes
            return Qt.CheckState.Unchecked

        elif role == self.ItemIdRole:
            return obj.id

        elif role == self.ItemTypeRole:
            return item_type

        elif role == self.ItemNameRole:
            return obj.name

        elif role == self.ItemObjectRole:
            return obj

        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        """Set data for the given index and role.

        Args:
            index: Model index.
            value: New value.
            role: Data role.

        Returns:
            True if data was set successfully.
        """
        if not index.isValid() or index.row() >= len(self._items):
            return False

        if role == Qt.ItemDataRole.CheckStateRole:
            # Checkbox state changed - emit signal
            self.dataChanged.emit(index, index, [role])
            return True

        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Return item flags for the given index.

        Args:
            index: Model index.

        Returns:
            Item flags.
        """
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )

    def _format_compact_date(self, lore_date: float) -> str:
        """Format a lore date as dd.mm.yyyy - hh:mm.

        Args:
            lore_date: The float lore date value.

        Returns:
            Formatted date string in dd.mm.yyyy - hh:mm format.
        """
        if not self._calendar_converter:
            return str(lore_date)

        cal_date = self._calendar_converter.from_float(lore_date)

        # Format as dd.mm.yyyy
        day_str = str(cal_date.day).zfill(2)
        month_str = str(cal_date.month).zfill(2)
        year_str = str(cal_date.year)
        date_part = f"{day_str}.{month_str}.{year_str}"

        # Format time from time_fraction (0.0 = midnight, 0.5 = noon)
        if cal_date.time_fraction > 0:
            total_minutes = int(cal_date.time_fraction * 24 * 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            time_part = f"{str(hours).zfill(2)}:{str(minutes).zfill(2)}"
            return f"{date_part} - {time_part}"

        return date_part

    def get_item(self, index: QModelIndex) -> Optional[tuple[str, Union[Event, Entity]]]:
        """Get the item at the given index.

        Args:
            index: Model index.

        Returns:
            Tuple of (item_type, object) or None.
        """
        if not index.isValid() or index.row() >= len(self._items):
            return None
        return self._items[index.row()]

    def find_item_index(self, item_type: str, item_id: str) -> Optional[QModelIndex]:
        """Find the index of an item by type and ID.

        Args:
            item_type: "event" or "entity".
            item_id: Item ID.

        Returns:
            Model index or None if not found.
        """
        for row, (itype, obj) in enumerate(self._items):
            if itype == item_type and obj.id == item_id:
                return self.index(row, 0)
        return None
