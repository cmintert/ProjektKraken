"""Map Calibration Mixin.

Provides map-scale configuration and distance-calibration workflow
for the MapWidget.
"""

import logging
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import SignalInstance, Slot
from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QWidget

from src.gui.widgets.map.calibration_distance_dialog import CalibrationDistanceDialog
from src.gui.widgets.map.map_scale_dialog import MapScaleDialog

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView

logger = logging.getLogger(__name__)


class MapCalibrationMixin:
    """Mixin providing map-scale configuration and calibration.

    Requires the host class to have:
        - self.view: MapGraphicsView
        - self.map_selector: QComboBox
        - self.overlay_banner: QLabel
        - self.map_scale_changed: Signal(float)
        - self.get_selected_map_id(): method
    """

    if TYPE_CHECKING:
        view: MapGraphicsView
        map_selector: QComboBox
        overlay_banner: QLabel
        map_scale_changed: SignalInstance

        def get_selected_map_id(self) -> str | None:
            """Return the active map identifier."""
            ...

    @Slot()
    def _configure_map_width(self) -> None:
        """Opens dialog to configure the map's total real-world width."""
        current_map_id = self.get_selected_map_id()
        if not current_map_id:
            logger.warning("No map selected, cannot configure scale")
            return

        map_name = self.map_selector.currentText()
        current_width = self.view.map_width_meters

        dialog = MapScaleDialog(current_width, cast(QWidget, self), map_name)

        # Determine behavior on result
        dialog.calibrate_requested.connect(self._handle_calibration_request)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_width = dialog.get_width()
            if new_width != current_width:
                self.view.set_map_width_meters(new_width)
                self.map_scale_changed.emit(new_width)
                logger.info(f"Updated map width to {new_width:.2f} m")

    @Slot()
    def _handle_calibration_request(self) -> None:
        """Starts the map calibration workflow from the dialog."""
        logger.info("Starting map calibration via measurement")

        # Disconnect any old connections to avoid duplicates
        try:
            self.view.calibration_completed.disconnect()
        except Exception:
            pass  # No slots connected

        self.view.calibration_completed.connect(
            self._on_calibration_measurement_finished
        )

        self.view.start_calibration()

        # Show hint
        self.overlay_banner.setText(
            "Click two points on the map to measure a known distance."
        )
        self.overlay_banner.show()

    @Slot(float)
    def _on_calibration_measurement_finished(self, px_distance: float) -> None:
        """Handle completion of the calibration measurement step."""
        # 1. Hide overlay
        self.overlay_banner.hide()

        # 2. Ask for real world distance
        if px_distance < 1.0:
            logger.warning("Measured distance too small, ignoring.")
            return

        dialog = CalibrationDistanceDialog(cast(QWidget, self))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            segment_meters = dialog.get_distance_meters()

            if segment_meters <= 0:
                return

            # Calculate new total width
            # Total Width / Image Width = Segment Real / Segment px
            # Total Width = (Image Width * Segment Real) / Segment px

            pixmap_item = getattr(self.view, "pixmap_item", None)
            if not pixmap_item:
                return

            image_width_px = pixmap_item.boundingRect().width()

            new_total_width = (image_width_px * segment_meters) / px_distance

            self.view.set_map_width_meters(new_total_width)
            self.map_scale_changed.emit(new_total_width)

            # Show confirmation details
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(
                cast(QWidget, self),
                "Calibration Complete",
                f"Map scale updated.\n\n"
                f"Segment: {segment_meters:.1f} m ({px_distance:.1f} px)\n"
                f"New Total Width: {new_total_width:.2f} m",
            )

        # Cleanup
        try:
            self.view.calibration_completed.disconnect(
                self._on_calibration_measurement_finished
            )
        except Exception:
            pass
