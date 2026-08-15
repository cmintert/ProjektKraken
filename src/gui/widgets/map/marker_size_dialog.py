"""Per-marker size and zoom behavior dialog."""

from __future__ import annotations

from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.core.marker_sizing import (
    DEFAULT_MAP_WIDTH_PERCENT,
    MarkerMapSizeUnit,
    MarkerSizingMode,
    MarkerSizingSettings,
)
from src.core.style_constants import MAX_SCALE, MIN_SCALE
from src.gui.utils.style_helper import StyleHelper

_KM = 1000.0
_PERCENT = "% map width"


class MarkerSizeDialog(QDialog):
    """Edit one marker's geographic footprint and style multiplier."""

    def __init__(
        self,
        settings: MarkerSizingSettings,
        scale_multiplier: float,
        map_width_meters: float,
        image_width: float,
        view_scale: float,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the controls from one marker's stored settings."""
        super().__init__(parent)
        self._map_width = max(0.0, map_width_meters)
        self._image_width = max(0.0, image_width)
        self._view_scale = max(0.0, view_scale)
        self._relative_unit = settings.map_unit
        self._relative_value = settings.map_value
        self._screen_px = settings.screen_px
        self._mode = settings.mode
        self._display_unit = self._relative_display_unit()
        self._updating = False

        self.setWindowTitle("Marker Size & Zoom")
        self.setModal(True)
        self.setMinimumWidth(440)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Choose whether this marker represents a footprint on the map or "
            "stays readable at a fixed screen size."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.mode_selector = QComboBox()
        self.mode_selector.addItem("Scale with map", "map_relative")
        self.mode_selector.addItem("Fixed on screen", "screen_fixed")
        self.mode_selector.setCurrentIndex(
            self.mode_selector.findData(settings.mode.value)
        )
        self.mode_selector.currentIndexChanged.connect(self._mode_changed)
        form.addRow("Behavior:", self.mode_selector)

        size_row = QHBoxLayout()
        self.size_input = QDoubleSpinBox()
        self.size_input.valueChanged.connect(self._value_changed)
        self.unit_selector = QComboBox()
        self.unit_selector.currentTextChanged.connect(self._unit_changed)
        size_row.addWidget(self.size_input, 1)
        size_row.addWidget(self.unit_selector)
        form.addRow("Base diameter:", size_row)

        self.scale_input = QDoubleSpinBox()
        self.scale_input.setRange(MIN_SCALE, MAX_SCALE)
        self.scale_input.setDecimals(2)
        self.scale_input.setSingleStep(0.1)
        self.scale_input.setValue(scale_multiplier)
        self.scale_input.setToolTip(
            "Multiplies the base diameter for creature size or emphasis."
        )
        self.scale_input.valueChanged.connect(self._update_summary)
        form.addRow("Scale multiplier:", self.scale_input)
        layout.addLayout(form)

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._sync_controls()

    def _mode_changed(self, _index: int) -> None:
        if self._updating:
            return
        self._stash_value()
        self._mode = MarkerSizingMode(self.mode_selector.currentData())
        self._display_unit = (
            self._relative_display_unit()
            if self._mode is MarkerSizingMode.MAP_RELATIVE
            else "px"
        )
        self._sync_controls()

    def _value_changed(self, value: float) -> None:
        if self._updating:
            return
        if self._mode is MarkerSizingMode.SCREEN_FIXED:
            self._screen_px = value
        else:
            self._relative_value = self._canonical(value, self._display_unit)
        self._update_summary()

    def _unit_changed(self, unit: str) -> None:
        if self._updating or not unit or unit == self._display_unit:
            return
        old_value = self.size_input.value()
        if unit == _PERCENT:
            meters = self._canonical(old_value, self._display_unit)
            self._relative_value = (
                meters / self._map_width * 100.0
                if self._map_width > 0
                else DEFAULT_MAP_WIDTH_PERCENT
            )
            self._relative_unit = MarkerMapSizeUnit.MAP_WIDTH_PERCENT
        else:
            if self._map_width <= 0:
                self._sync_controls()
                return
            self._relative_value = (
                old_value / 100.0 * self._map_width
                if self._display_unit == _PERCENT
                else self._canonical(old_value, self._display_unit)
            )
            self._relative_unit = MarkerMapSizeUnit.METERS
        self._display_unit = unit
        self._sync_controls()

    def _stash_value(self) -> None:
        if self._mode is MarkerSizingMode.SCREEN_FIXED:
            self._screen_px = self.size_input.value()
        else:
            self._relative_value = self._canonical(
                self.size_input.value(), self._display_unit
            )

    def _sync_controls(self) -> None:
        self._updating = True
        try:
            self.unit_selector.clear()
            if self._mode is MarkerSizingMode.SCREEN_FIXED:
                self.unit_selector.addItem("px")
                self.size_input.setRange(8.0, 256.0)
                self.size_input.setDecimals(0)
                self.size_input.setValue(self._screen_px)
                self.hint.setText("The icon remains the same size while zooming.")
            else:
                self.unit_selector.addItems([_PERCENT, "m", "km"])
                model = self.unit_selector.model()
                if isinstance(model, QStandardItemModel):
                    for index in (1, 2):
                        item = model.item(index)
                        if item is not None:
                            item.setEnabled(self._map_width > 0)
                if self._map_width <= 0 and self._display_unit in ("m", "km"):
                    self._display_unit = _PERCENT
                    self._relative_unit = MarkerMapSizeUnit.MAP_WIDTH_PERCENT
                    self._relative_value = DEFAULT_MAP_WIDTH_PERCENT
                self.unit_selector.setCurrentText(self._display_unit)
                if self._display_unit == _PERCENT:
                    self.size_input.setRange(0.1, 100.0)
                    self.size_input.setDecimals(2)
                    value = self._relative_value
                else:
                    divisor = _KM if self._display_unit == "km" else 1.0
                    self.size_input.setRange(0.01 / divisor, self._map_width / divisor)
                    self.size_input.setDecimals(3 if divisor > 1 else 2)
                    value = self._relative_value / divisor
                self.size_input.setValue(value)
                self.hint.setText(
                    "The icon keeps a stable footprint on the map and grows as "
                    "you zoom in. Calibrate the map to use metres."
                )
        finally:
            self._updating = False
        self._update_summary()

    def _update_summary(self, _value: float = 0.0) -> None:
        settings = self.get_settings()
        multiplier = self.scale_input.value()
        if settings.mode is MarkerSizingMode.SCREEN_FIXED:
            self.summary.setText(
                f"Rendered diameter: {settings.screen_px * multiplier:.0f} px"
            )
            return
        meters: float | None
        if settings.map_unit is MarkerMapSizeUnit.METERS and self._map_width > 0:
            meters = settings.map_value
            percent = meters / self._map_width * 100.0
        else:
            percent = settings.map_value
            meters = self._map_width * percent / 100.0 if self._map_width else None
        percent *= multiplier
        parts = [f"{percent:.2f}% of map width"]
        if meters is not None:
            parts.append(f"{meters * multiplier:,.2f} m")
        screen_px = self._image_width * percent / 100.0 * self._view_scale
        if screen_px > 0:
            parts.append(f"~{screen_px:.0f} px at current zoom")
        self.summary.setText(" · ".join(parts))

    def get_settings(self) -> MarkerSizingSettings:
        """Return settings represented by the controls."""
        if not self._updating:
            self._stash_value()
        return MarkerSizingSettings(
            mode=self._mode,
            map_unit=self._relative_unit,
            map_value=self._relative_value,
            screen_px=self._screen_px,
        )

    def get_scale_multiplier(self) -> float:
        """Return the marker's additional style multiplier."""
        return self.scale_input.value()

    def _relative_display_unit(self) -> str:
        if self._relative_unit is MarkerMapSizeUnit.MAP_WIDTH_PERCENT:
            return _PERCENT
        return "km" if self._relative_value >= _KM else "m"

    @staticmethod
    def _canonical(value: float, unit: str) -> float:
        return value * _KM if unit == "km" else value
