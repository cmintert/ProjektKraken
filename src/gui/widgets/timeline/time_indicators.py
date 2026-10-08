"""Time identity and accepted navigation context, independent of application data."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.core.calendar import CalendarConverter
from src.core.temporal_presentation import event_navigation_context
from src.core.theme_manager import ThemeManager

if TYPE_CHECKING:
    from src.gui.widgets.timeline.timeline_view import TimelineView

STATUS_STACK_WIDTH = 650


class TimelineTimeStatus(QWidget):
    """Pinned wrapping date identities and uncertain-navigation disclosure."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a compact strip that also fits narrow docks."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(2)
        self.dates = QLabel()
        self.notice = QLabel()
        for label in (self.dates, self.notice):
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(label)
        self.notice.hide()

    def display(self, viewing: str, current: str, notice: str) -> None:
        """Update presentation without changing keyboard or authoring context."""
        separator = "\n" if self.width() < STATUS_STACK_WIDTH else "    ·    "
        self.dates.setText(
            f"Viewing: {viewing}{separator}World current time: {current}"
        )
        self.notice.setText(notice)
        self.notice.setVisible(bool(notice))
        theme = ThemeManager().get_theme()
        for label, role in (
            (self.dates, "supporting_text"),
            (self.notice, "supporting_caption"),
        ):
            style = f"color: {theme[role]};"
            if label.styleSheet() != style:
                label.setStyleSheet(style)


class TimelineTimeIndicators(QObject):
    """Own accepted target disclosure and viewport time marks."""

    def __init__(self, view: "TimelineView") -> None:
        """Depend only on a timeline view and optional acceptance predicate."""
        super().__init__(view)
        self.view = view
        self.converter: CalendarConverter | None = None
        self.status: TimelineTimeStatus | None = None
        self.context: dict[str, Any] = {}
        self._published_context: dict[str, Any] = {}
        self.pending: dict[str, Any] | None = None
        self.accepts: Callable[[float], bool] = lambda time: True
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.settle)
        view.playhead_time_changed.connect(self.request_settle)
        view.current_time_changed.connect(self.refresh)
        view.graphics_scene.changed.connect(self._scene_changed)
        ThemeManager().theme_changed.connect(self._theme_changed)

    def _theme_changed(self, theme: dict[str, str]) -> None:
        self.refresh()

    def _scene_changed(self, regions: object) -> None:
        self.request_settle()

    def request_settle(self, time: float | None = None) -> None:
        """Wait until the synchronous navigation guard has completed."""
        if not self.timer.isActive():
            self.timer.start(0)

    def queue(self, context: dict[str, Any], time: float) -> None:
        """Keep a candidate separate from accepted disclosure."""
        if (
            not context
            and self.pending is not None
            and self.context.get("time") == time
        ):
            context = self.context
        self.pending = {**context, "time": time}

    def settle(self) -> None:
        """Attach only accepted context, preserving it through rejected navigation."""
        time = self.view.get_playhead_time()
        if self.pending is not None:
            target = float(self.pending["time"])
            if target != time:
                self.pending = None
            elif self.accepts(time):
                self.context = self.pending if self.pending.get("event_id") else {}
                self.pending = None
        elif self.context and float(self.context["time"]) != time:
            self.context = {}
        self._refresh_target()
        if self.context != self._published_context:
            self._published_context = dict(self.context)
            self.view.navigation_context_changed.emit(dict(self.context))
        self.refresh()

    def _refresh_target(self) -> None:
        """Refresh identity/qualification, and discard deleted targets."""
        if not self.context:
            return
        owner = next(
            (e for e in self.view.events if e.id == self.context.get("event_id")), None
        )
        if owner is None:
            self.context = {}
            return
        if owner.lore_date != self.context["time"]:
            self.context = {}
            return
        updated = event_navigation_context(owner, self.converter)
        self.context = {**updated, "time": self.context["time"]}

    def format_time(self, time: float) -> str:
        """Format the actual coordinate using the active calendar."""
        if self.converter is None:
            return f"{time:g} days"
        return self.converter.format_datetime(time)

    def refresh(self, time: float | None = None) -> None:
        """Refresh pinned dates; offscreen marks never hide time identity."""
        if self.status is None:
            return
        notice = ""
        if (
            self.context.get("uncertain")
            and self.context.get("time") == self.view.get_playhead_time()
        ):
            notice = (
                f"Viewing a position within {self.context['name']}'s uncertain "
                "date; its occurrence date is not exact. "
                f"({self.context['caption']})"
            )
            if self.context.get("unresolved"):
                notice = (
                    f"Viewing a layout position for {self.context['name']}; "
                    f"timing is unresolved. ({self.context['caption']})"
                )
        self.status.display(
            self.format_time(self.view.get_playhead_time()),
            self.format_time(self.view.get_current_time()),
            notice,
        )

    def paint(self, painter: QPainter) -> None:
        """Paint labeled time identities in device space, including dashed now."""
        view = self.view
        theme = ThemeManager().get_theme()
        width = view.viewport().width()
        height = view.viewport().height()
        viewed = view.mapFromScene(view._playhead.x(), 0).x()
        current = view.mapFromScene(view._current_time_line.x(), 0).x()
        coincident = view._current_time_line.isVisible() and abs(viewed - current) <= 1
        painter.save()
        painter.resetTransform()
        if view._current_time_line.isVisible() and 0 <= current <= width:
            pen = QPen(QColor(theme["timeline_world_time"]), 2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(current, view.RULER_HEIGHT, current, height)
        if view._playhead.isVisible() and 0 <= viewed <= width:
            painter.setPen(QPen(QColor(theme["timeline_viewed_time"]), 1))
            painter.drawLine(viewed, view.RULER_HEIGHT, viewed, height)
            self._label(
                painter,
                viewed,
                "Viewing + World current time" if coincident else "Viewing",
                theme,
                61,
            )
        if (
            not coincident
            and view._current_time_line.isVisible()
            and 0 <= current <= width
        ):
            self._label(painter, current, "World current time", theme, 76)
        painter.restore()

    def _label(
        self, painter: QPainter, x: float, text: str, theme: dict[str, str], y: float
    ) -> None:
        width = painter.fontMetrics().horizontalAdvance(text) + 8
        left = max(0.0, min(x + 5, self.view.viewport().width() - width))
        painter.fillRect(QRectF(left, y - 12, width, 15), QColor(theme["surface"]))
        painter.setPen(QColor(theme["supporting_text"]))
        painter.drawText(QPointF(left + 4, y), text)
