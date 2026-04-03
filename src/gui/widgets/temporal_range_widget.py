"""Temporal Range Widget Module.

Provides a unified card widget that groups the Start date, Span (duration),
and End date fields for an event into a single cohesive section with an
anchor-lock mechanic.

Lock behaviour:
- LOCK_DURATION (default): when start changes, end follows (duration held).
- LOCK_END: when start changes, duration adjusts (end held fixed).
"""

import logging
from typing import Any, Optional

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.compact_date_widget import CompactDateWidget
from src.gui.widgets.compact_duration_widget import CompactDurationWidget

logger = logging.getLogger(__name__)


class TemporalRangeWidget(QWidget):
    """A card widget grouping start date, duration, and end date for an event.

    The three interdependent fields are displayed together with a visual
    connector and an anchor-lock toggle that controls which value is held
    fixed when the start date is changed.

    Lock modes:
        LOCK_DURATION: End date follows start (default, preserves duration).
        LOCK_END: Duration adjusts when start changes (preserves end date).

    Signals:
        start_changed: Emitted when the start date value changes (float days).
        duration_changed: Emitted when the duration value changes (float days).
        end_changed: Emitted when the derived end date value changes (float days).
    """

    LOCK_DURATION = "duration"
    LOCK_END = "end"

    start_changed = Signal(float)
    duration_changed = Signal(float)
    end_changed = Signal(float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialises the temporal range widget.

        Args:
            parent: Parent widget.

        """
        super().__init__(parent)
        self._lock_mode = self.LOCK_DURATION
        self._updating = False

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._setup_ui()
        self._connect_signals()

    # ── UI construction ────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        """Builds the card layout."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Outer card frame
        self._card = QFrame()
        self._card.setObjectName("temporal_card")
        outer.addWidget(self._card)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(4)

        # ── START row ─────────────────────────────────────────────────────
        start_row = QHBoxLayout()
        start_row.setSpacing(6)
        lbl_start = QLabel("Start")
        lbl_start.setFixedWidth(36)
        start_row.addWidget(lbl_start)
        self.date_start = CompactDateWidget()
        start_row.addWidget(self.date_start)
        card_layout.addLayout(start_row)

        # ── Lock connector row ────────────────────────────────────────────
        lock_row = QHBoxLayout()
        lock_row.setSpacing(4)

        line_left = QFrame()
        line_left.setFrameShape(QFrame.Shape.HLine)
        line_left.setFrameShadow(QFrame.Shadow.Plain)
        line_left.setLineWidth(1)
        lock_row.addWidget(line_left, stretch=1)

        # Segmented control: Duration | End Date
        self.btn_lock_duration = QPushButton("Duration")
        self.btn_lock_duration.setCheckable(True)
        self.btn_lock_duration.setChecked(True)
        self.btn_lock_duration.setToolTip("Start changes move the end date (span stays fixed)")

        self.btn_lock_end = QPushButton("End Date")
        self.btn_lock_end.setCheckable(True)
        self.btn_lock_end.setChecked(False)
        self.btn_lock_end.setToolTip("Start changes adjust the span (end date stays fixed)")

        self._lock_group = QButtonGroup(self)
        self._lock_group.setExclusive(True)
        self._lock_group.addButton(self.btn_lock_duration, 0)
        self._lock_group.addButton(self.btn_lock_end, 1)

        lock_row.addWidget(self.btn_lock_duration, stretch=0)
        lock_row.addWidget(self.btn_lock_end, stretch=0)

        line_right = QFrame()
        line_right.setFrameShape(QFrame.Shape.HLine)
        line_right.setFrameShadow(QFrame.Shadow.Plain)
        line_right.setLineWidth(1)
        lock_row.addWidget(line_right, stretch=1)

        card_layout.addLayout(lock_row)

        # ── SPAN row ──────────────────────────────────────────────────────
        span_row = QHBoxLayout()
        span_row.setSpacing(6)
        lbl_span = QLabel("Span")
        lbl_span.setFixedWidth(36)
        span_row.addWidget(lbl_span)
        self.duration_widget = CompactDurationWidget()
        span_row.addWidget(self.duration_widget)
        card_layout.addLayout(span_row)

        # ── Thin divider ──────────────────────────────────────────────────
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Plain)
        divider.setLineWidth(1)
        card_layout.addWidget(divider)

        # ── END row ───────────────────────────────────────────────────────
        end_row = QHBoxLayout()
        end_row.setSpacing(6)
        lbl_end = QLabel("End")
        lbl_end.setFixedWidth(36)
        end_row.addWidget(lbl_end)
        self.date_end = CompactDateWidget()
        end_row.addWidget(self.date_end)
        card_layout.addLayout(end_row)

        self._apply_styles()

    def _apply_styles(self) -> None:
        """Applies theme-aware styles to the card and labels."""
        self._card.setStyleSheet(StyleHelper.get_temporal_card_style())

        label_style = StyleHelper.get_temporal_label_style()
        for lbl in self._card.findChildren(QLabel):
            lbl.setStyleSheet(label_style)

        sep_style = StyleHelper.get_temporal_separator_style()
        for frame in self._card.findChildren(QFrame):
            if frame.frameShape() in (
                QFrame.Shape.HLine,
                QFrame.Shape.VLine,
            ):
                frame.setStyleSheet(sep_style)

        self._update_segment_styles()

    def _update_segment_styles(self) -> None:
        """Updates the segmented control button styles to reflect the current lock mode."""
        is_locked_end = self._lock_mode == self.LOCK_END
        self.btn_lock_duration.setStyleSheet(
            StyleHelper.get_temporal_segment_style(active=not is_locked_end, position="left")
        )
        self.btn_lock_end.setStyleSheet(
            StyleHelper.get_temporal_segment_style(active=is_locked_end, position="right")
        )

    # ── Signal wiring ──────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        """Wires up internal signals."""
        self.date_start.value_changed.connect(self._on_start_changed)
        self.duration_widget.value_changed.connect(self._on_duration_changed)
        self.date_end.value_changed.connect(self._on_end_changed)
        self.btn_lock_end.toggled.connect(self._on_lock_toggled)
        ThemeManager().theme_changed.connect(self._on_theme_changed)

    # ── Internal slot handlers ─────────────────────────────────────────────

    @Slot(float)
    def _on_start_changed(self, new_start: float) -> None:
        """Handles start date change.

        In LOCK_DURATION mode the end date is recalculated.
        In LOCK_END mode the duration is recalculated instead.

        Args:
            new_start: New start date as absolute day float.

        """
        if self._updating:
            return
        self._updating = True
        try:
            self.duration_widget.set_start_date(new_start)
            if self._lock_mode == self.LOCK_DURATION:
                current_duration = self.duration_widget.get_value()
                self.date_end.blockSignals(True)
                self.date_end.set_value(new_start + current_duration)
                self.date_end.blockSignals(False)
            else:
                end_date = self.date_end.get_value()
                duration = max(0.0, end_date - new_start)
                self.duration_widget.blockSignals(True)
                self.duration_widget.set_value(duration)
                self.duration_widget.blockSignals(False)
            self.start_changed.emit(new_start)
        finally:
            self._updating = False

    @Slot(float)
    def _on_duration_changed(self, duration: float) -> None:
        """Handles span change — always updates end date.

        Args:
            duration: New duration in days.

        """
        if self._updating:
            return
        self._updating = True
        try:
            start = self.date_start.get_value()
            self.date_end.blockSignals(True)
            self.date_end.set_value(start + duration)
            self.date_end.blockSignals(False)
            self.duration_changed.emit(duration)
        finally:
            self._updating = False

    @Slot(float)
    def _on_end_changed(self, end_date: float) -> None:
        """Handles end date change — always recalculates duration.

        Args:
            end_date: New end date as absolute day float.

        """
        if self._updating:
            return
        self._updating = True
        try:
            start = self.date_start.get_value()
            duration = max(0.0, end_date - start)
            self.duration_widget.blockSignals(True)
            self.duration_widget.set_value(duration)
            self.duration_widget.blockSignals(False)
            self.end_changed.emit(end_date)
        finally:
            self._updating = False

    @Slot(bool)
    def _on_lock_toggled(self, checked: bool) -> None:
        """Switches the anchor lock mode.

        Args:
            checked: True activates LOCK_END mode; False restores LOCK_DURATION.

        """
        self._lock_mode = self.LOCK_END if checked else self.LOCK_DURATION
        self._update_segment_styles()

    @Slot(dict)
    def _on_theme_changed(self, theme: dict) -> None:
        """Re-applies all theme-dependent styles on theme change."""
        self._apply_styles()

    # ── Public API ─────────────────────────────────────────────────────────

    def set_calendar_converter(self, converter: Any) -> None:
        """Sets the calendar converter on all sub-widgets.

        Args:
            converter: CalendarConverter instance, or None.

        """
        self.date_start.set_calendar_converter(converter)
        self.duration_widget.set_calendar_converter(converter)
        self.date_end.set_calendar_converter(converter)
        if converter:
            self.duration_widget.set_start_date(self.date_start.get_value())

    def set_values(self, start: float, duration: float) -> None:
        """Sets start date and duration, updating end date display accordingly.

        This is the primary data-load entry point.  It suppresses internal
        signal cascades so that only the final state is committed.

        Args:
            start: Start date as absolute day float.
            duration: Duration in days.

        """
        old_updating = self._updating
        self._updating = True
        try:
            self.date_start.set_value(start)
            self.duration_widget.set_start_date(start)
            self.duration_widget.set_value(duration)
            self.date_end.set_value(start + duration)
        finally:
            self._updating = old_updating

    def get_start(self) -> float:
        """Returns the current start date as an absolute day float."""
        return self.date_start.get_value()

    def get_duration(self) -> float:
        """Returns the current duration in days."""
        return self.duration_widget.get_value()

    def get_end(self) -> float:
        """Returns the derived end date as an absolute day float."""
        return self.date_end.get_value()

    def set_duration(self, value: float) -> None:
        """Sets the duration directly (for external callers and tests).

        Args:
            value: Duration in days.

        """
        self.duration_widget.set_value(value)

    def get_formatted_start_text(self) -> str:
        """Returns the typed/formatted start date string from the text field."""
        return self.date_start.txt_date.text()
