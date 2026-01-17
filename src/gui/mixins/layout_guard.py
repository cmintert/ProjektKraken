"""
Layout Guard Mixin.

Provides hardening logic for QMainWindow layout restoration.
Protects against:
1. Zero-size docks (collapsed splitters).
2. Off-screen windows.
3. Corrupted state data.
"""

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QDockWidget, QMainWindow

from src.core.logging_config import get_logger
from src.gui.utils.geometry_utils import GeometryUtils

logger = get_logger(__name__)


class LayoutGuardMixin:
    """
    Mixin for QMainWindow to harden layout save/restore operations.
    Expected usage: Inherit from this in MainWindow.
    """

    def guard_restore_geometry(self, geometry_data: bytes) -> bool:
        """
        Safely restores window geometry with off-screen protection.

        Args:
            geometry_data: The hex-encoded or raw QByteArray geometry data.

        Returns:
            bool: True if restored and validated, False otherwise.
        """
        if not geometry_data:
            return False

        # Attempt standard restore first to get the rect into the object
        # Note: restoreGeometry calls move/resize internally
        if not self.restoreGeometry(geometry_data):
            logger.warning("Standard restoreGeometry failed")
            return False

        # Now validate the resulting geometry
        current_geo = self.geometry()
        safe_geo = GeometryUtils.ensure_on_screen(current_geo)

        if current_geo != safe_geo:
            logger.warning(
                f"Geometry restored to unsafe position {current_geo}. "
                f"Forcing safe position {safe_geo}."
            )
            self.setGeometry(safe_geo)

        return True

    def guard_validate_dock_sizes(self) -> None:
        """
        Checks for collapsed (zero-size) docks and forces them open.
        Should be called AFTER restoreState() and processing events.
        """
        if not isinstance(self, QMainWindow):
            logger.error("LayoutGuardMixin must be used on a QMainWindow")
            return

        affected_docks = []

        # Iterate over all dock widgets
        for dock in self.findChildren(QDockWidget):
            if not dock.isVisible():
                continue

            if dock.isFloating():
                # Floating docks need geometry checks
                self._guard_floating_dock(dock)
                continue

            # Check docked size
            width = dock.width()
            height = dock.height()
            min_width = dock.minimumWidth()
            min_height = dock.minimumHeight()

            # Detection threshold: strict < min, or essentially zero
            # We use a safety buffer (e.g., 50px) to catch "technically visible but useless"
            SAFE_MIN = 50

            is_collapsed = width < SAFE_MIN or height < SAFE_MIN

            if is_collapsed:
                logger.warning(
                    f"Dock '{dock.objectName()}' collapsed ({width}x{height}). "
                    f"Min ({min_width}x{min_height}). Expanding."
                )
                affected_docks.append(dock)
                self._force_expand_dock(dock)

        if affected_docks:
            logger.info(f"LayoutGuard restored {len(affected_docks)} collapsed docks.")

    def _guard_floating_dock(self, dock: QDockWidget) -> None:
        """Ensures floating docks are on-screen."""
        geo = dock.geometry()
        safe_geo = GeometryUtils.ensure_on_screen(geo)
        if geo != safe_geo:
            dock.setGeometry(safe_geo)
            logger.info(f"Moved floating dock '{dock.objectName()}' on-screen.")

    def _force_expand_dock(self, dock: QDockWidget) -> None:
        """
        Forces a dock to expand by setting a temporary minimum size constraint
        that overrides the QSplitter's collapsed state, then resets it.
        """
        original_min_w = dock.minimumWidth()
        original_min_h = dock.minimumHeight()

        # 1. Force a reasonable minimum size
        TEMP_MIN = 200
        dock.setMinimumWidth(max(original_min_w, TEMP_MIN))
        dock.setMinimumHeight(max(original_min_h, TEMP_MIN))

        # 2. Trigger layout update
        dock.updateGeometry()
        if dock.parentWidget():
            dock.parentWidget().updateGeometry()

        # 3. Schedule reset of constraints (allow user to resize later)
        # We need the event loop to process the layout change first
        def reset_constraints() -> None:
            dock.setMinimumWidth(original_min_w)
            dock.setMinimumHeight(original_min_h)
            logger.debug(f"Reset constraints for {dock.objectName()}")

        QTimer.singleShot(100, reset_constraints)

    def guard_check_crash_flag(self) -> bool:
        """
        Checks if the application crashed on the last run.
        Expected usage: Call at start of __init__.

        Returns:
            bool: True if crash detected (Unclean exit).
        """
        settings = QSettings()
        # "app_running" flag: Set to true on start, false on clean exit.
        was_running = settings.value("app_running", False, type=bool)

        if was_running:
            logger.warning("Detected unclean exit (Crash Flag active).")
            return True

        # Set flag for this session
        settings.setValue("app_running", True)
        return False

    def guard_clear_crash_flag(self) -> None:
        """Clears the running flag on clean exit."""
        settings = QSettings()
        settings.setValue("app_running", False)
