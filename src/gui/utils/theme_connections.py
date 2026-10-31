"""Visibility-aware delivery of presentation-only theme subscriptions."""

import weakref
from collections.abc import Callable
from typing import Any

import shiboken6
from PySide6.QtCore import QEvent, QObject, Signal, Slot
from PySide6.QtWidgets import QGraphicsScene, QWidget

from src.core.theme_manager import ThemeManager

_subscriptions: weakref.WeakSet["_ThemeSubscription"] = weakref.WeakSet()


def _widget_for(owner: QObject) -> QWidget | None:
    current: QObject | None = owner
    while current is not None:
        if isinstance(current, QWidget):
            return current
        # QAbstractItemModel.parent(index) shadows QObject.parent().
        current = QObject.parent(current)
    scene_method = getattr(owner, "scene", None)
    scene = owner if isinstance(owner, QGraphicsScene) else None
    if scene is None and callable(scene_method):
        scene = scene_method()
    if scene is not None and scene.views():
        return scene.views()[0]
    return None


class _ThemeSubscription(QObject):
    """Retain only the latest hidden-view snapshot until its next Show event."""

    ready = Signal(dict)

    def __init__(self, owner: QObject, callback: Callable[..., Any]) -> None:
        super().__init__(owner)
        self.callback = callback
        self._owner = weakref.ref(owner)
        self._watched: weakref.ReferenceType[QWidget] | None = None
        self._pending: dict[str, Any] | None = None
        self.ready.connect(callback)
        _subscriptions.add(self)
        ThemeManager().theme_changed.connect(self._changed)
        self._watch(_widget_for(owner))

    def _watch(self, widget: QWidget | None) -> None:
        previous = self._watched() if self._watched is not None else None
        if previous is widget:
            return
        if previous is not None and shiboken6.isValid(previous):
            previous.removeEventFilter(self)
        self._watched = weakref.ref(widget) if widget is not None else None
        if widget is not None:
            widget.installEventFilter(self)

    @Slot(dict)
    def _changed(self, snapshot: dict[str, Any]) -> None:
        owner = self._owner()
        if owner is None or not shiboken6.isValid(owner):
            return
        widget = _widget_for(owner)
        self._watch(widget)
        if (
            ThemeManager().has_scoped_presentation
            and widget is not None
            and (not widget.isVisible() or ThemeManager().defers_theme_delivery)
        ):
            self._pending = snapshot
        else:
            self._pending = None
            self.ready.emit(snapshot)

    def flush(self) -> None:
        """Deliver the latest coalesced snapshot inside its presentation scope."""
        if self._pending is not None:
            snapshot, self._pending = self._pending, None
            self.ready.emit(snapshot)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Show and self._pending is not None:
            snapshot, self._pending = self._pending, None
            self.ready.emit(snapshot)
            if isinstance(watched, QWidget):
                from src.gui.utils.theme_presentation import refresh_theme_scope

                refresh_theme_scope(watched)
        return False

    def stop(self) -> None:
        """Stop delivery while the owning view survives (e.g. WebEngine shutdown)."""
        ThemeManager().theme_changed.disconnect(self._changed)
        self._pending = None
        self._watch(None)
        _subscriptions.discard(self)
        self.deleteLater()


def connect_theme(owner: object, callback: Callable[..., Any]) -> None:
    """Connect presentation refresh without doing hidden-view work on Apply."""
    if not isinstance(owner, QObject):
        raise TypeError("Theme subscriptions require a QObject owner")
    _ThemeSubscription(owner, callback)


def disconnect_theme(owner: QObject, callback: Callable[..., Any]) -> None:
    """Disconnect subscriptions created for one owner and bound callback."""
    for child in owner.children():
        if isinstance(child, _ThemeSubscription) and child.callback == callback:
            child.stop()


def flush_theme_subscriptions(owns: Callable[[QWidget], bool]) -> None:
    """Flush visible consumers belonging to one scope, including scene objects."""
    for subscription in list(_subscriptions):
        if not shiboken6.isValid(subscription) or subscription._pending is None:
            continue
        owner = subscription._owner()
        if owner is None or not shiboken6.isValid(owner):
            continue
        widget = _widget_for(owner)
        if widget is not None and widget.isVisible() and owns(widget):
            subscription.flush()
