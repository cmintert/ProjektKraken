"""Explorer Filter Proxy Model Module.

Provides sorting and filtering for the Explorer model.
"""

import logging
from typing import Optional, Union

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt
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

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the filter proxy model.

        Args:
            parent: Parent QObject.
        """
        super().__init__(parent)
        self._search_term = ""
        self._filter_mode = "All Items"  # "All Items", "Events Only", "Entities Only"
        self._advanced_filter_config: dict = {}

        # Enable dynamic sorting
        self.setDynamicSortFilter(True)

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

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
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

        item_type, obj = item

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

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
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
