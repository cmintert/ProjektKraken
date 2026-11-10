"""Explorer Filter Proxy Model Module.

Provides sorting and filtering for the Explorer model.
"""

import logging
from typing import Any, Optional, Union

from PySide6.QtCore import (
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtWidgets import QWidget

from src.core.entities import Entity
from src.core.events import Event
from src.core.search_utils import SearchUtils
from src.gui.models.explorer_model import ExplorerModel

logger = logging.getLogger(__name__)


class ExplorerFilterProxyModel(QSortFilterProxyModel):
    """A filter proxy model for the Explorer model.

    Supports filtering by search term, item type, and tags.
    """

    PinnedRole = int(Qt.ItemDataRole.UserRole) + 30
    SourceOrderRole = int(Qt.ItemDataRole.UserRole) + 31

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the filter proxy model.

        Args:
            parent: Parent QObject.
        """
        super().__init__(parent)
        self._search_term = ""
        self._filter_mode = "All Items"  # "All Items", "Events Only", "Entities Only"
        self._advanced_filter_config: dict = {}
        self._active_item: tuple[str, str] | None = None
        self._pinned_source_row: int | None = None

        # The source Explorer model already maintains the requested order.
        # Dynamic proxy sorting re-evaluates the full large-world model for a
        # single changed row; active filters are invalidated explicitly.
        self.setDynamicSortFilter(False)

    def set_active_item(self, identity: tuple[str, str] | None) -> None:
        """Keep an accepted active object available through restrictive filters."""
        self._active_item = identity
        self.invalidate()

    def _is_pinned(self, index: QModelIndex | QPersistentModelIndex) -> bool:
        """Read the pin decision cached once for this source/filter snapshot."""
        return index.isValid() and index.row() == self._pinned_source_row

    def invalidate(self) -> None:
        """Evaluate the active filter exception once, outside sorting callbacks."""
        self._pinned_source_row = None
        source = self.sourceModel()
        if isinstance(source, ExplorerModel) and self._active_item is not None:
            index = source.find_item_index(*self._active_item)
            if index is not None:
                item = source.get_item(index)
                if item is not None and not self._matches_filters(*item):
                    self._pinned_source_row = index.row()
        if self.sortRole() == self.SourceOrderRole:
            # Native source order needs no Python comparator when nothing is pinned.
            super().sort(
                0 if self._pinned_source_row is not None else -1,
                Qt.SortOrder.AscendingOrder,
            )
        super().invalidate()

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Expose pin status without duplicating or changing the source record."""
        if role not in {
            self.PinnedRole,
            Qt.ItemDataRole.AccessibleTextRole,
            Qt.ItemDataRole.ToolTipRole,
        }:
            return super().data(index, role)
        pinned = index.isValid() and self._is_pinned(self.mapToSource(index))
        if role == self.PinnedRole:
            return pinned
        value = super().data(index, role)
        if pinned and role in {
            Qt.ItemDataRole.AccessibleTextRole,
            Qt.ItemDataRole.ToolTipRole,
        }:
            title = super().data(index, Qt.ItemDataRole.DisplayRole)
            return f"{title}\nActive item · Hidden by filters"
        return value

    def set_search_term(self, term: str) -> None:
        """Set the search term for filtering.

        Args:
            term: Search term.
        """
        self._search_term = term.lower().strip()
        self.invalidate()  # Use invalidate() instead of deprecated invalidateFilter()

    def set_filter_mode(self, mode: str) -> None:
        """Set the filter mode (All/Events/Entities).

        Args:
            mode: Filter mode string.
        """
        self._filter_mode = mode
        self.invalidate()  # Use invalidate() instead of deprecated invalidateFilter()

    def set_advanced_filter(self, config: dict) -> None:
        """Set advanced filter configuration (tags).

        Args:
            config: Filter configuration dictionary.
        """
        self._advanced_filter_config = config or {}
        self.invalidate()  # Use invalidate() instead of deprecated invalidateFilter()

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        """Determine if a row passes the current filters.

        Args:
            source_row: Row in source model.
            source_parent: Parent index in source model.

        Returns:
            True if row should be visible.
        """
        source_model = self.sourceModel()
        if not isinstance(source_model, ExplorerModel):
            return True

        index = source_model.index(source_row, 0, source_parent)
        item = source_model.get_item(index)

        if not item:
            return False

        return (item[0], item[1].id) == self._active_item or self._matches_filters(
            *item
        )

    def _matches_filters(self, item_type: str, obj: Entity | Event) -> bool:
        """Test ordinary results independently of the active-object exception."""

        # Apply type filter
        if self._filter_mode == "Events Only" and item_type != "event":
            return False
        if self._filter_mode == "Entities Only" and item_type != "entity":
            return False

        # Apply search filter
        if self._search_term and not self._matches_search(obj):
            return False

        # Apply advanced tag filters
        if self._advanced_filter_config and not self._passes_advanced_filters(obj):
            return False

        return True

    def lessThan(
        self,
        left: QModelIndex | QPersistentModelIndex,
        right: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        """Compare two items for sorting.

        Args:
            left: Left index.
            right: Right index.

        Returns:
            True if left < right.
        """
        source_model = self.sourceModel()
        if not isinstance(source_model, ExplorerModel):
            return False

        left_pinned = self._is_pinned(left)
        right_pinned = self._is_pinned(right)
        if left_pinned != right_pinned:
            return left_pinned
        if self.sortRole() == self.SourceOrderRole:
            return left.row() < right.row()

        left_item = source_model.get_item(left)
        right_item = source_model.get_item(right)

        if not left_item or not right_item:
            return False

        left_type, left_obj = left_item
        right_type, right_obj = right_item

        # Get sort column (we'll use custom sorting logic)
        # The column is set externally via setSortRole
        role = self.sortRole()

        # Sort by name (default)
        if role == Qt.ItemDataRole.DisplayRole:
            return left_obj.name.lower() < right_obj.name.lower()

        # Sort by created timestamp
        elif role == Qt.ItemDataRole.UserRole + 10:  # Custom "created" role
            left_created = getattr(left_obj, "created_at", 0) or 0
            right_created = getattr(right_obj, "created_at", 0) or 0
            return left_created < right_created

        # Sort by lore date
        elif role == Qt.ItemDataRole.UserRole + 11:  # Custom "lore_date" role
            if left_type == "event" and right_type == "event":
                left_date = getattr(left_obj, "lore_date", float("inf")) or float("inf")
                right_date = getattr(right_obj, "lore_date", float("inf")) or float(
                    "inf"
                )
                return left_date < right_date
            # Events before entities when sorting by date
            elif left_type == "event":
                return True
            elif right_type == "event":
                return False
            # Both entities - sort by name
            else:
                return left_obj.name.lower() < right_obj.name.lower()

        return False

    def _matches_search(self, obj: Union[Event, Entity]) -> bool:
        """Check if an object matches the search term.

        Args:
            obj: Event or Entity object.

        Returns:
            True if matches search.
        """
        return SearchUtils.matches_search(obj, self._search_term)

    def _passes_advanced_filters(self, obj: Union[Event, Entity]) -> bool:
        """Check if an object passes advanced tag filters.

        Args:
            obj: Event or Entity object.

        Returns:
            True if passes filters.
        """
        if not self._advanced_filter_config:
            return True

        include_tags = self._advanced_filter_config.get("include", [])
        include_mode = self._advanced_filter_config.get("include_mode", "any")
        exclude_tags = self._advanced_filter_config.get("exclude", [])
        exclude_mode = self._advanced_filter_config.get("exclude_mode", "any")

        if not include_tags and not exclude_tags:
            return True

        item_tags = set(getattr(obj, "tags", []))

        # Exclude check
        if exclude_tags:
            if exclude_mode == "all":
                if all(tag in item_tags for tag in exclude_tags):
                    return False
            else:
                if any(tag in item_tags for tag in exclude_tags):
                    return False

        # Include check
        if include_tags:
            if include_mode == "all":
                if not all(tag in item_tags for tag in include_tags):
                    return False
            else:
                if not any(tag in item_tags for tag in include_tags):
                    return False

        return True
