"""A fixed-height, keyboard-accessible strip of calculated Event occurrences."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QMenu, QWidget

from src.core.events import Event
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.timeline.event_item import EventItem
from src.gui.widgets.timeline.occurrence_marker import OccurrenceMarker, marker_bounds
from src.services.recurrence_presentation_service import (
    RecurrenceProjection,
    format_occurrence,
    project_recurrence,
)

if TYPE_CHECKING:
    from src.gui.widgets.timeline.timeline_view import TimelineView


class RecurrenceStrip(QWidget):
    """Render prepared viewport pages; marker interaction never changes dates."""

    event_selected = Signal(str)
    HEIGHT = 40

    def __init__(self, view: TimelineView) -> None:
        """Observe viewport changes and coalesce projection outside paint calls."""
        super().__init__(view.viewport())
        self.setObjectName("RecurrenceStrip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.view = view
        self.events: tuple[Event, ...] = ()
        self.projections: tuple[RecurrenceProjection, ...] = ()
        self._buttons: list[OccurrenceMarker] = []
        self._selected_id: str | None = None
        self._generation = 0
        self._menus: list[QMenu] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self.refresh)
        self.view.viewport().installEventFilter(self)
        self.view.horizontalScrollBar().valueChanged.connect(self.schedule)
        self.setAccessibleName("Recurring Events")
        declare_inspection(
            self, "timeline-repeats|event.recurrence|help-timeline-repeats"
        )
        connect_theme(self, self._theme_changed)
        self._theme_changed()
        self.hide()

    def _theme_changed(self, *_args: object) -> None:
        self.setStyleSheet(StyleHelper.get_recurrence_strip_style())
        self.schedule()

    def set_events(self, events: tuple[Event, ...]) -> None:
        """Replace the filtered source snapshot, including unresolved schedules."""
        self.events = events
        self._generation += 1
        for menu in tuple(self._menus):
            menu.close()
        self._menus.clear()
        self.schedule()

    def set_selected_event(self, event_id: str | None) -> None:
        """Reflect accepted selection without moving time or opening the editor."""
        self._selected_id = event_id
        for button in self._buttons:
            button.setChecked(
                event_id is not None and button.property("sourceEventId") == event_id
            )

    def schedule(self, *_args: object) -> None:
        """Coalesce pan/zoom/data invalidation; no evaluation runs during paint."""
        if self.events and not self._timer.isActive():
            self._timer.start()
        elif not self.events:
            self.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Observe viewport geometry and wheel changes without consuming input."""
        if event.type() in {QEvent.Type.Resize, QEvent.Type.Wheel, QEvent.Type.Show}:
            self.schedule()
        return False

    def refresh(self) -> None:
        """Prepare and cluster the current filtered viewport with bounded queries."""
        focus_index = next(
            (i for i, button in enumerate(self._buttons) if button.hasFocus()), None
        )
        width = self.view.viewport().width()
        self.setGeometry(0, self.view.RULER_HEIGHT, width, self.HEIGHT)
        start = self.view.mapToScene(0, 0).x() / self.view.scale_factor
        end = self.view.mapToScene(width, 0).x() / self.view.scale_factor
        major, _minor, _opacity = self.view._ruler.calculate_active_levels(
            end - start, width
        )
        step = self.view._ruler.NUMERIC_LEVEL_STEPS[major]
        converter = EventItem._calendar_converter
        self.projections = tuple(
            project_recurrence(e, converter, start, end, step) for e in self.events
        )
        for button in self._buttons:
            button.hide()
            button.deleteLater()
        self._buttons = []
        rows = []
        for projection in self.projections:
            for occurrence in projection.occurrences:
                pixel_x = self.view.mapFromScene(
                    occurrence.start * self.view.scale_factor, 0
                ).x()
                rows.append(
                    (
                        float(pixel_x),
                        projection,
                        format_occurrence(occurrence.start, converter),
                    )
                )
            if projection.error:
                rows.append((80.0, projection, projection.error))
            if projection.next_index is not None:
                rows.append(
                    (float(max(80, width - 180)), projection, "More occurrences…")
                )
        clusters = self._cluster_rows(rows, width)
        for x, cluster in clusters:
            self._add_cluster(x, cluster, start, end, step)
        if focus_index is not None and self._buttons:
            self._buttons[min(focus_index, len(self._buttons) - 1)].setFocus()
        self.setGeometry(0, self.view.RULER_HEIGHT, width, self.HEIGHT)
        self.setVisible(bool(clusters))
        self.raise_()

    def _cluster_rows(
        self, rows: list[tuple[float, RecurrenceProjection, str]], width: int
    ) -> list[tuple[float, list[tuple[RecurrenceProjection, str]]]]:
        """Cluster overlapping label extents without moving their original date pins."""
        measured = [
            (
                marker_bounds(x, width, p.event.name, caption, self.font())[0],
                x,
                p,
                caption,
            )
            for x, p, caption in rows
        ]
        clusters: list[tuple[float, list[tuple[RecurrenceProjection, str]]]] = []
        right = -1.0
        for bounds, x, projection, caption in sorted(
            measured, key=lambda row: (row[0].left(), row[1], row[2].event.id)
        ):
            if clusters and bounds.left() < right + 6:
                clusters[-1][1].append((projection, caption))
                right = max(right, bounds.right())
            else:
                clusters.append((x, [(projection, caption)]))
                right = bounds.right()
        return clusters

    def _add_cluster(
        self,
        x: float,
        rows: list[tuple[RecurrenceProjection, str]],
        start: float,
        end: float,
        step: float,
    ) -> None:
        projection, caption = rows[0]
        event = projection.event
        label = event.name if len(rows) == 1 else f"{len(rows)} occurrences"
        button = OccurrenceMarker(
            label,
            caption,
            self,
            pinned=not projection.error and caption != "More occurrences…",
        )
        button.setProperty("sourceEventId", event.id if len(rows) == 1 else None)
        button.setChecked(len(rows) == 1 and event.id == self._selected_id)
        excerpt = re.sub(r"<[^>]*>", "", event.description).strip()[:240]
        button.setToolTip(f"{event.name}\n{caption}\n{excerpt}")
        button.setAccessibleName(f"{label}: {caption}")
        button.place_at(x, self.width())
        button.clicked.connect(
            lambda: self._open_cluster(button, rows, start, end, step)
        )
        button.show()
        self._buttons.append(button)

    def _open_cluster(
        self,
        button: OccurrenceMarker,
        rows: list[tuple[RecurrenceProjection, str]],
        start: float,
        end: float,
        step: float,
    ) -> None:
        menu = QMenu(self)
        self._menus.append(menu)
        menu.aboutToHide.connect(lambda m=menu: self._forget_menu(m))
        menu.aboutToHide.connect(menu.deleteLater)
        generation = self._generation
        if len(rows) == 1 and rows[0][1] != "More occurrences…":
            self._select(rows[0][0].event.id, generation)
        for projection, caption in rows:
            action = menu.addAction(f"{projection.event.name} · {caption}")
            if caption == "More occurrences…":
                action.triggered.connect(
                    lambda _checked=False, p=projection: self._more(
                        menu, p, start, end, step
                    )
                )
            else:
                action.triggered.connect(
                    lambda _checked=False, identity=projection.event.id: self._select(
                        identity, generation
                    )
                )
        if len(rows) == 1:
            excerpt = re.sub(r"<[^>]*>", "", rows[0][0].event.description).strip()[:240]
            if excerpt:
                description = menu.addAction(excerpt)
                description.setEnabled(False)
        menu.popup(button.mapToGlobal(button.rect().bottomLeft()))

    def _more(
        self,
        menu: QMenu,
        projection: RecurrenceProjection,
        start: float,
        end: float,
        step: float,
    ) -> None:
        page = project_recurrence(
            projection.event,
            EventItem._calendar_converter,
            start,
            end,
            step,
            projection.next_index,
        )
        rows = [
            (page, format_occurrence(o.start, EventItem._calendar_converter))
            for o in page.occurrences
        ]
        if page.next_index is not None:
            rows.append((page, "More occurrences…"))
        menu.close()
        if self._buttons and rows:
            self._open_cluster(self._buttons[-1], rows, start, end, step)

    def _select(self, identity: str, generation: int) -> None:
        if generation == self._generation:
            self.event_selected.emit(identity)

    def _forget_menu(self, menu: QMenu) -> None:
        """Release closed transient menus rather than retaining every inspection."""
        if menu in self._menus:
            self._menus.remove(menu)
