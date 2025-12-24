"""
Group Band Manager Module.

Manages multiple GroupBandItem widgets for the timeline, handling stacking,
ordering, collapse state, and interaction with the service layer.
"""

import logging
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, QPointF, Signal
from PySide6.QtWidgets import QMenu

from src.gui.widgets.timeline.group_band_item import GroupBandItem

logger = logging.getLogger(__name__)


class GroupBandManager(QObject):
    """
    Manages timeline group bands.

    Responsibilities:
    - Create and position multiple GroupBandItem widgets
    - Track collapse/expand state for each band
    - Handle band reordering
    - Provide interface for updating band metadata
    - Manage band context menus
    """

    # Signals
    band_expanded = Signal(str)  # tag_name
    band_collapsed = Signal(str)  # tag_name
    band_reordered = Signal(list)  # new tag_order
    tag_color_change_requested = Signal(str)  # tag_name
    tag_rename_requested = Signal(str)  # tag_name
    remove_from_grouping_requested = Signal(str)  # tag_name

    def __init__(self, scene, db_service, parent=None):
        """
        Initializes the GroupBandManager.

        Args:
            scene: The QGraphicsScene to add bands to
            db_service: DatabaseService instance for querying metadata
            parent: Parent QObject
        """
        super().__init__(parent)

        self.scene = scene
        self.db_service = db_service
        
        # Track bands by tag name
        self._bands: Dict[str, GroupBandItem] = {}
        
        # Track order and collapse state
        self._tag_order: List[str] = []
        self._collapsed_tags: set = set()
        
        # Track Y position for stacking
        self._bands_start_y = -200  # Start above timeline content

    def set_grouping_config(self, tag_order: List[str], date_range: Optional[tuple] = None):
        """
        Set the grouping configuration and create/update bands.

        Args:
            tag_order: List of tag names to create bands for
            date_range: Optional (start_date, end_date) for filtering
        """
        logger.info(f"Setting grouping config with {len(tag_order)} tags")
        
        # Clear existing bands
        self.clear_bands()
        
        # Store tag order
        self._tag_order = tag_order.copy()
        
        # Load metadata for all tags
        metadata = self.db_service.get_group_metadata(
            tag_order=tag_order,
            date_range=date_range
        )
        
        # Create bands
        current_y = self._bands_start_y
        for meta in metadata:
            tag_name = meta["tag_name"]
            color = meta["color"]
            count = meta["count"]
            earliest = meta["earliest_date"]
            latest = meta["latest_date"]
            
            # Check if this tag should be collapsed
            is_collapsed = tag_name in self._collapsed_tags
            
            # Create band
            band = GroupBandItem(
                tag_name=tag_name,
                color=color,
                count=count,
                earliest_date=earliest,
                latest_date=latest,
                is_collapsed=is_collapsed
            )
            
            # Connect signals
            band.expand_requested.connect(self._on_expand_requested)
            band.collapse_requested.connect(self._on_collapse_requested)
            band.context_menu_requested.connect(self._on_context_menu_requested)
            
            # Position band
            band.setY(current_y)
            
            # Add to scene
            self.scene.addItem(band)
            
            # Track band
            self._bands[tag_name] = band
            
            # Update Y for next band
            current_y += band.get_height() + GroupBandItem.BAND_MARGIN
        
        logger.info(f"Created {len(self._bands)} bands")

    def clear_bands(self):
        """Remove all bands from the scene."""
        for band in self._bands.values():
            self.scene.removeItem(band)
        self._bands.clear()
        logger.debug("Cleared all bands")

    def update_band_metadata(self, date_range: Optional[tuple] = None):
        """
        Update metadata for all bands.

        Args:
            date_range: Optional (start_date, end_date) for filtering
        """
        if not self._tag_order:
            return
        
        # Load fresh metadata
        metadata = self.db_service.get_group_metadata(
            tag_order=self._tag_order,
            date_range=date_range
        )
        
        # Update each band
        for meta in metadata:
            tag_name = meta["tag_name"]
            if tag_name in self._bands:
                band = self._bands[tag_name]
                band.update_metadata(
                    count=meta["count"],
                    earliest_date=meta["earliest_date"],
                    latest_date=meta["latest_date"]
                )

    def _on_expand_requested(self, tag_name: str):
        """Handle band expansion request."""
        logger.debug(f"Expanding band: {tag_name}")
        
        if tag_name in self._bands:
            band = self._bands[tag_name]
            band.set_collapsed(False)
            
            # Remove from collapsed set
            self._collapsed_tags.discard(tag_name)
            
            # Reposition bands below
            self._reposition_bands()
            
            # Emit signal
            self.band_expanded.emit(tag_name)

    def _on_collapse_requested(self, tag_name: str):
        """Handle band collapse request."""
        logger.debug(f"Collapsing band: {tag_name}")
        
        if tag_name in self._bands:
            band = self._bands[tag_name]
            band.set_collapsed(True)
            
            # Add to collapsed set
            self._collapsed_tags.add(tag_name)
            
            # Reposition bands below
            self._reposition_bands()
            
            # Emit signal
            self.band_collapsed.emit(tag_name)

    def _reposition_bands(self):
        """Reposition all bands to account for collapse/expand changes."""
        current_y = self._bands_start_y
        
        for tag_name in self._tag_order:
            if tag_name in self._bands:
                band = self._bands[tag_name]
                band.setY(current_y)
                current_y += band.get_height() + GroupBandItem.BAND_MARGIN

    def _on_context_menu_requested(self, tag_name: str, screen_pos):
        """
        Handle context menu request for a band.

        Args:
            tag_name: The tag name for the band
            screen_pos: Screen position for the menu
        """
        logger.debug(f"Context menu requested for: {tag_name}")
        
        menu = QMenu()
        
        # Add menu actions
        rename_action = menu.addAction(f"Rename '{tag_name}'...")
        color_action = menu.addAction("Change Color...")
        menu.addSeparator()
        remove_action = menu.addAction("Remove from Grouping")
        
        # Show menu and handle action
        action = menu.exec(screen_pos)
        
        if action == rename_action:
            self.tag_rename_requested.emit(tag_name)
        elif action == color_action:
            self.tag_color_change_requested.emit(tag_name)
        elif action == remove_action:
            self.remove_from_grouping_requested.emit(tag_name)

    def get_collapsed_tags(self) -> set:
        """
        Get the set of collapsed tag names.

        Returns:
            Set of collapsed tag names
        """
        return self._collapsed_tags.copy()

    def set_collapsed_tags(self, collapsed_tags: set):
        """
        Set which tags should be collapsed.

        Args:
            collapsed_tags: Set of tag names to collapse
        """
        self._collapsed_tags = collapsed_tags.copy()
        
        # Update existing bands
        for tag_name, band in self._bands.items():
            is_collapsed = tag_name in self._collapsed_tags
            band.set_collapsed(is_collapsed)
        
        # Reposition
        self._reposition_bands()

    def get_total_bands_height(self) -> int:
        """
        Calculate the total height of all bands.

        Returns:
            Total height in pixels
        """
        total = 0
        for tag_name in self._tag_order:
            if tag_name in self._bands:
                band = self._bands[tag_name]
                total += band.get_height() + GroupBandItem.BAND_MARGIN
        
        # Remove last margin
        if total > 0:
            total -= GroupBandItem.BAND_MARGIN
        
        return total

    def get_tag_order(self) -> List[str]:
        """
        Get the current tag order.

        Returns:
            List of tag names in order
        """
        return self._tag_order.copy()
