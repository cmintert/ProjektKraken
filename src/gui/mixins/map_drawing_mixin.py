"""Map Drawing Tools Mixin.

Provides path/region drawing mode management for the MapWidget.
"""

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class MapDrawingMixin:
    """Mixin providing drawing-tool toggling and completion.

    Requires the host class to have:
        - self.view: MapGraphicsView
        - self.btn_draw_path: QPushButton
        - self.btn_draw_region: QPushButton
        - self.feature_created: Signal
        - self._update_mode_indicator(): method
        - self.get_selected_map_id(): method
        - self._select_or_create_object(): method
    """

    @Slot()
    def _on_draw_path_clicked(self) -> None:
        """Toggles path drawing mode."""
        if self.view.is_drawing:
            self.view.cancel_drawing()
            return
        self.btn_draw_region.setChecked(False)
        self.view.start_drawing("path")
        self._update_mode_indicator()

    @Slot()
    def _on_draw_region_clicked(self) -> None:
        """Toggles region drawing mode."""
        if self.view.is_drawing:
            self.view.cancel_drawing()
            return
        self.btn_draw_path.setChecked(False)
        self.view.start_drawing("region")
        self._update_mode_indicator()

    @Slot(str, list)
    def _on_drawing_finished(self, feature_type: str, geometry: list) -> None:
        """Handles drawing completion — shows object picker then emits feature_created.

        Args:
            feature_type: 'path' or 'region'.
            geometry: List of normalized coordinate dicts.

        """
        self.btn_draw_path.setChecked(False)
        self.btn_draw_region.setChecked(False)
        self._update_mode_indicator()

        map_id = self.get_selected_map_id()
        if not map_id:
            QMessageBox.warning(self, "No Map", "Please create or select a map first.")
            return

        result = self._select_or_create_object(
            f"Link {feature_type.title()}",
            f"Select object for this {feature_type}:",
        )
        if not result:
            return

        obj_id, obj_type, name = result
        self.feature_created.emit(
            map_id, obj_id, obj_type, name, feature_type, geometry
        )
        logger.info(
            f"Feature drawing complete: {feature_type}, {len(geometry)} vertices"
        )

    @Slot()
    def _on_drawing_cancelled(self) -> None:
        """Handles drawing cancellation — resets UI state."""
        self.btn_draw_path.setChecked(False)
        self.btn_draw_region.setChecked(False)
        self._update_mode_indicator()
