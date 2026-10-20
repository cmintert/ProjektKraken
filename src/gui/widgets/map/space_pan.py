"""Temporary view-level navigation that cannot dispatch scene editing events."""

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtWidgets import QGraphicsView, QWidget


@dataclass(frozen=True)
class _InteractionState:
    interactive: bool
    drag_mode: QGraphicsView.DragMode
    cursor: QCursor
    viewport_cursor: QCursor
    explicit_cursor: bool
    explicit_viewport_cursor: bool


class SpacePan:
    """Own one temporary navigation override and its interrupted mouse release."""

    def __init__(self, view: QGraphicsView) -> None:
        """Keep the view's tool state separate from the temporary pan state."""
        self.view = view
        self.held = False
        self.dragging = False
        self.suppress_release = False
        self._state: _InteractionState | None = None
        self._position = QPointF()

    def begin(self) -> None:
        """Capture interaction once and prevent scene items from taking the press."""
        if self.held:
            return
        view = self.view
        viewport = view.viewport()
        self._state = _InteractionState(
            view.isInteractive(),
            view.dragMode(),
            QCursor(view.cursor()),
            QCursor(viewport.cursor()),
            view.testAttribute(Qt.WidgetAttribute.WA_SetCursor),
            viewport.testAttribute(Qt.WidgetAttribute.WA_SetCursor),
        )
        self.held = True
        view.setInteractive(False)
        QGraphicsView.setDragMode(view, QGraphicsView.DragMode.ScrollHandDrag)
        viewport.setCursor(Qt.CursorShape.OpenHandCursor)

    @staticmethod
    def _restore_cursor(widget: QWidget, cursor: QCursor, explicit: bool) -> None:
        if explicit:
            widget.setCursor(cursor)
        else:
            widget.unsetCursor()

    def end(self) -> None:
        """Finish Qt's drag before restoring tools; swallow any late physical up."""
        state = self._state
        if state is None:
            return
        view = self.view
        if self.dragging:
            self.dragging = False
            release = QMouseEvent(
                QEvent.Type.MouseButtonRelease,
                self._position,
                QPointF(view.viewport().mapToGlobal(self._position.toPoint())),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
            QGraphicsView.mouseReleaseEvent(view, release)
            self.suppress_release = True
        self.dragging = False
        self.held = False
        self._state = None
        QGraphicsView.setDragMode(view, state.drag_mode)
        view.setInteractive(state.interactive)
        self._restore_cursor(view, state.cursor, state.explicit_cursor)
        self._restore_cursor(
            view.viewport(), state.viewport_cursor, state.explicit_viewport_cursor
        )

    def press(self, event: QMouseEvent) -> bool:
        """Deliver pan presses only to Qt's non-interactive hand-scrolling path."""
        if event.button() == Qt.MouseButton.LeftButton:
            # A new press also recovers from a physical release lost with focus.
            self.suppress_release = False
        if not self.held:
            return False
        self._position = event.position()
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            QGraphicsView.mousePressEvent(self.view, event)
        event.accept()
        return True

    def move(self, event: QMouseEvent) -> bool:
        """Keep pan movement and abandoned drags away from all edit tools."""
        if self.suppress_release:
            if not event.buttons() & Qt.MouseButton.LeftButton:
                self.suppress_release = False
            event.accept()
            return True
        if not self.held:
            return False
        if self.dragging and not event.buttons() & Qt.MouseButton.LeftButton:
            self.end()
            event.accept()
            return True
        self._position = event.position()
        QGraphicsView.mouseMoveEvent(self.view, event)
        return True

    def release(self, event: QMouseEvent) -> bool:
        """End the pan without turning its release into a click or edit commit."""
        if self.suppress_release:
            if event.button() == Qt.MouseButton.LeftButton:
                self.suppress_release = False
            event.accept()
            return True
        if not self.held:
            return False
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            QGraphicsView.mouseReleaseEvent(self.view, event)
        event.accept()
        return True
