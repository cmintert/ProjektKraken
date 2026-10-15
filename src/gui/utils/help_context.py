"""GUI-local semantic Help registrations and keyboard ownership."""

from __future__ import annotations

import weakref
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TypeVar

import shiboken6
from PySide6.QtCore import QObject, QPoint
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QWhatsThis, QWidget

_Object = TypeVar("_Object", bound=QObject)


def declare_inspection(obj: _Object, declaration: str) -> _Object:
    """Attach an explicit semantic identity while retaining the original object."""
    obj.setProperty("krakenHelpBinding", declaration)
    return obj


def ancestors(widget: QObject | None) -> Iterator[QObject]:
    """Walk only live QObject ancestry."""
    while widget is not None and shiboken6.isValid(widget):
        yield widget
        widget = widget.parent()


def owns_help_input(widget: QObject | None) -> bool:
    """Identify the companion independently of its current modal parent."""
    return any(bool(item.property("krakenHelpWindow")) for item in ancestors(widget))


def owns_assistance_input(widget: QObject | None) -> bool:
    """Include native inspection mode and its tracked explanation popup."""
    app = QApplication.instance()
    return (
        owns_help_input(widget)
        or any(
            bool(item.property("krakenHelpInspectionPopup"))
            for item in ancestors(widget)
        )
        or QWhatsThis.inWhatsThisMode()
        or bool(app and app.property("krakenInspectionPopup"))
    )


@dataclass(frozen=True)
class ControlHelpRegistration:
    """A reviewed control meaning, independent of ordinary F1 context."""

    meaning: str
    topic_id: str
    excerpt_target: str | None = None


def help_is_activating() -> bool:
    """Whether focus is transferring to Help rather than accepting an input."""
    app = QApplication.instance()
    return bool(app and app.property("krakenHelpFocusTransfer"))


def help_suspends_input(widget: QWidget) -> bool:
    """Include queued focus loss from the current Help origin."""
    return help_is_activating() or any(
        bool(item.property("krakenHelpSuspendedOrigin")) for item in ancestors(widget)
    )


@contextmanager
def help_focus_transfer() -> Iterator[None]:
    """Keep focus-loss validation from applying an unfinished authoring input."""
    app = QApplication.instance()
    previous = app.property("krakenHelpFocusTransfer") if app else None
    if app:
        app.setProperty("krakenHelpFocusTransfer", True)
    try:
        yield
    finally:
        if app:
            app.setProperty("krakenHelpFocusTransfer", previous)


class HelpContextRegistry:
    """Keep control, surface and dialog meanings separate from presentation."""

    def __init__(self) -> None:
        """Use weak keys so widget teardown removes registrations."""
        self.controls: weakref.WeakKeyDictionary[QWidget, str] = (
            weakref.WeakKeyDictionary()
        )
        self.panels: weakref.WeakKeyDictionary[QWidget, str] = (
            weakref.WeakKeyDictionary()
        )
        self.dialogs: weakref.WeakKeyDictionary[QWidget, str] = (
            weakref.WeakKeyDictionary()
        )
        self.owners: weakref.WeakKeyDictionary[
            QWidget, weakref.ReferenceType[QWidget]
        ] = weakref.WeakKeyDictionary()
        self.operations: weakref.WeakKeyDictionary[
            QWidget, Callable[[], str | None]
        ] = weakref.WeakKeyDictionary()
        self._watched: weakref.WeakSet[QWidget] = weakref.WeakSet()
        self.inspection: weakref.WeakKeyDictionary[QWidget, ControlHelpRegistration] = (
            weakref.WeakKeyDictionary()
        )
        self.inspection_regions: weakref.WeakKeyDictionary[
            QWidget, Callable[[QPoint | None], ControlHelpRegistration | None]
        ] = weakref.WeakKeyDictionary()
        self.inspection_actions: weakref.WeakKeyDictionary[
            QAction, tuple[ControlHelpRegistration, weakref.ReferenceType[QWidget]]
        ] = weakref.WeakKeyDictionary()
        # Qt owns menu actions. Keep their Python wrappers stable until native
        # destruction; collecting a transient menuAction wrapper can tear down
        # its menu on PySide. Semantic owners and origin references remain weak.
        self._action_handles: dict[int, QAction] = {}
        self._menu_handles: dict[int, QWidget] = {}

    def retain_inspection_action(self, action: QAction) -> None:
        """Keep Qt-owned action wrappers stable even for an exempt menu item."""
        token = id(action)
        if token not in self._action_handles:
            self._action_handles[token] = action
            action.destroyed.connect(lambda: self._action_handles.pop(token, None))

    def retain_inspection_menu(self, menu: QWidget) -> None:
        """Keep transient menu wrappers until their native owner disposes them."""
        token = id(menu)
        if token not in self._menu_handles:
            self._menu_handles[token] = menu
            menu.destroyed.connect(lambda: self._menu_handles.pop(token, None))

    def _watch(self, widget: QWidget) -> None:
        if widget not in self._watched:
            self._watched.add(widget)
            reference = weakref.ref(widget)
            widget.destroyed.connect(lambda: self._remove(reference))

    def _remove(self, reference: weakref.ReferenceType[QWidget]) -> None:
        widget = reference()
        if widget is not None:
            for mapping in (
                self.controls,
                self.panels,
                self.dialogs,
                self.owners,
                self.operations,
                self.inspection,
                self.inspection_regions,
            ):
                mapping.pop(widget, None)

    def clear(self) -> None:
        """Release all registrations and operation dependencies on shutdown."""
        for widget in QApplication.allWidgets():
            if widget.property("krakenInspectionRegistry") == id(self):
                for key in (
                    "krakenInspectionMeaning",
                    "krakenInspectionTopic",
                    "krakenInspectionRegion",
                    "krakenInspectionRegistry",
                    "krakenInspectionExcerpt",
                ):
                    widget.setProperty(key, None)
                widget.setWhatsThis("")
        self.controls.clear()
        self.panels.clear()
        self.dialogs.clear()
        self.owners.clear()
        self.operations.clear()
        self.inspection.clear()
        self.inspection_regions.clear()
        self.inspection_actions.clear()
        for action in self._action_handles.values():
            if shiboken6.isValid(action):
                action.setWhatsThis("")
        self._action_handles.clear()
        self._menu_handles.clear()

    def register_inspection(
        self,
        widget: QWidget,
        meaning: str,
        topic: str,
        excerpt_target: str | None = None,
    ) -> None:
        """Register only reviewed control instances or their scoped composites."""
        self.inspection[widget] = ControlHelpRegistration(
            meaning, topic, excerpt_target
        )
        widget.setProperty("krakenInspectionRegistry", id(self))
        widget.setProperty("krakenInspectionMeaning", meaning)
        widget.setProperty("krakenInspectionTopic", topic)
        widget.setProperty("krakenInspectionExcerpt", excerpt_target)
        # Native Shift+F1 eligibility; the controller supplies validated text.
        widget.setWhatsThis(" ")
        self._watch(widget)

    def register_inspection_action(
        self,
        action: QAction,
        meaning: str,
        topic: str,
        owner: QWidget,
        excerpt_target: str | None = None,
    ) -> None:
        """Associate a menu action with its semantic surviving surface."""
        self.inspection_actions[action] = (
            ControlHelpRegistration(meaning, topic, excerpt_target),
            weakref.ref(owner),
        )
        self.retain_inspection_action(action)
        action.setWhatsThis(" ")

    def inspection_action(
        self,
        action: QAction,
    ) -> tuple[QWidget, ControlHelpRegistration] | None:
        """Resolve a live action without triggering it or reading its label."""
        if not shiboken6.isValid(action):
            return None
        value = self.inspection_actions.get(action)
        if value is None:
            return None
        registration, reference = value
        owner = reference()
        if owner is None or not shiboken6.isValid(owner):
            return None
        return owner, registration

    def register_inspection_region(
        self,
        widget: QWidget,
        provider: Callable[[QPoint | None], ControlHelpRegistration | None],
    ) -> None:
        """Resolve painted/item regions without changing authoring selection."""
        self.inspection_regions[widget] = provider
        widget.setProperty("krakenInspectionRegistry", id(self))
        widget.setProperty("krakenInspectionRegion", provider)
        widget.setWhatsThis(" ")
        self._watch(widget)

    def inspection_for(
        self, origin: QWidget, position: QPoint | None = None
    ) -> tuple[QWidget, ControlHelpRegistration] | None:
        """Resolve reviewed nested controls, stopping at a surface boundary."""
        for item in ancestors(origin):
            if not isinstance(item, QWidget):
                continue
            provider = self.inspection_regions.get(item) or item.property(
                "krakenInspectionRegion"
            )
            if callable(provider):
                point = item.mapFrom(origin, position) if position is not None else None
                registration = provider(point)
                return (item, registration) if registration else None
            registration = self.inspection.get(item)
            if registration is None:
                meaning = item.property("krakenInspectionMeaning")
                topic = item.property("krakenInspectionTopic")
                if isinstance(meaning, str) and isinstance(topic, str):
                    registration = ControlHelpRegistration(
                        meaning, topic, item.property("krakenInspectionExcerpt")
                    )
            if registration is not None:
                return item, registration
            if item in self.panels or item in self.dialogs:
                break
        return None

    def register_control(
        self, widget: QWidget, topic: str, owner: QWidget | None = None
    ) -> None:
        """Register a control/group and optional persistent semantic owner."""
        self.controls[widget] = topic
        self._watch(widget)
        if owner is not None:
            self.owners[widget] = weakref.ref(owner)

    def register_panel(self, widget: QWidget, topic: str) -> None:
        """Register a panel fallback, distinct from a control topic."""
        self.panels[widget] = topic
        self._watch(widget)

    def register_dialog(self, widget: QWidget, topic: str) -> None:
        """Register a dialog boundary and fallback."""
        self.dialogs[widget] = topic
        self._watch(widget)

    def register_operation(
        self, surface: QWidget, provider: Callable[[], str | None]
    ) -> None:
        """Register a read-only callback scoped to one surface."""
        self.operations[surface] = provider
        self._watch(surface)

    def candidates(self, origin: QWidget | None) -> tuple[list[str], QWidget | None]:
        """Return ordered candidates without consulting application data."""
        from PySide6.QtWidgets import QDialog

        controls: list[str] = []
        boundary: QWidget | None = None
        semantic: QWidget | None = None
        for item in ancestors(origin):
            if not isinstance(item, QWidget):
                continue
            if item in self.controls:
                controls.append(self.controls[item])
            if item in self.owners:
                semantic = self.owners[item]()
            if isinstance(item, QDialog) or item in self.panels:
                boundary = item
                break
        surface = semantic if semantic is not None else boundary
        if surface is not None and shiboken6.isValid(surface):
            provider = self.operations.get(surface)
            operation = provider() if provider else None
            if operation:
                controls.append(operation)
        if boundary is not None and boundary in self.dialogs:
            controls.append(self.dialogs[boundary])
        if surface is not None and surface in self.panels:
            controls.append(self.panels[surface])
        controls.append("manual.home")
        return controls, boundary or surface
