"""Shared presentation controls for saved and provisional footprint edits."""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QSlider, QWidget

from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.wrapping_buttons import WrappingPushButton as StandardButton
from src.gui.widgets.wrapping_choices import WrappingCheckBox as QCheckBox

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView


class FootprintControls(QFrame):
    """Expose alignment helpers while the existing map session owns Apply/Cancel."""

    def __init__(self, view: "MapGraphicsView", parent: QWidget | None = None) -> None:
        """Create alignment controls using shared action presentation."""
        super().__init__(parent)
        declare_inspection(
            self,
            "map.placement.controls|map.hierarchy|help-inspect-map-placement-controls",
        )
        self.setObjectName("MapPlacementControls")
        self._view = view
        layout = QGridLayout(self)
        self._controls_layout = layout
        self.status = QLabel("Placement preview — Apply to save; Cancel to discard")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status, 0, 0, 1, 2)
        self.opacity_label = QLabel("Image opacity: 65%")
        self.opacity = declare_inspection(
            QSlider(Qt.Orientation.Horizontal),
            "map.placement.opacity|map.features|help-inspect-map-placement-opacity",
        )
        self.opacity.setRange(0, 100)
        self.opacity.setValue(65)
        self.opacity.setAccessibleName("Footprint image opacity")
        self.opacity.valueChanged.connect(self._opacity_changed)
        layout.addWidget(self.opacity_label, 1, 0)
        layout.addWidget(self.opacity, 1, 1)
        self.reset = StandardButton("Reset rotation")
        self.zoom = StandardButton("Zoom to footprint")
        for column, button in enumerate((self.reset, self.zoom)):
            button.setStyleSheet(StyleHelper.get_secondary_button_style())
            layout.addWidget(button, 2 + column, 0, 1, 2)
        self.reset.clicked.connect(view.reset_footprint_rotation)
        self.zoom.clicked.connect(view.zoom_to_footprint)
        self.lock = declare_inspection(
            QCheckBox("Lock placement while comparing"),
            "map.placement.lock|map.features|help-inspect-map-placement-lock",
        )
        self.lock.toggled.connect(self._lock_changed)
        layout.addWidget(self.lock, 4, 0, 1, 2)
        connect_theme(self, self._apply_theme)
        self._apply_theme({})
        self.hide()

    def _apply_theme(self, _theme: dict) -> None:
        self.setStyleSheet(StyleHelper.get_mode_panel_style(self.objectName()))
        for button in (self.reset, self.zoom):
            button.setStyleSheet(StyleHelper.get_secondary_button_style())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Reserve complete wrapped instructions as the map allocation narrows."""
        super().resizeEvent(event)
        self._reflow(event.size().width())

    def set_status(self, text: str) -> None:
        """Show complete preview or recovery wording at the current allocation."""
        self.status.setText(text)
        self._reflow(self.width())

    def _reflow(self, available_width: int) -> None:
        layout = self._controls_layout
        margins = layout.contentsMargins()
        width = max(1, available_width - margins.left() - margins.right() - 2)
        height = self.status.heightForWidth(width)
        self.status.setMinimumHeight(height)
        layout.setRowMinimumHeight(0, height)
        layout.invalidate()
        required = layout.totalHeightForWidth(available_width)
        if required > 0 and self.minimumHeight() != required:
            self.setMinimumHeight(required)
            self.updateGeometry()

    def reset_for_edit(self, provisional: bool) -> None:
        """Start every editor with predictable, session-local comparison controls."""
        self.lock.setChecked(False)
        self.opacity.setValue(65)
        self._opacity_changed(65)
        self.set_status(
            "Unsaved attachment preview — Apply to attach; Cancel to discard"
            if provisional
            else "Placement preview — Apply to save; Cancel to discard"
        )

    def _opacity_changed(self, value: int) -> None:
        self.opacity_label.setText(f"Image opacity: {value}%")
        self._view.set_footprint_image_opacity(value / 100)

    def _lock_changed(self, locked: bool) -> None:
        self._view.set_footprint_locked(locked)
        self.reset.setEnabled(not locked)
