"""GUI-local semantic Help registrations and keyboard ownership."""

from __future__ import annotations

import weakref
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import shiboken6
from PySide6.QtCore import QObject, QPoint
from PySide6.QtWidgets import QApplication, QWhatsThis, QWidget


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

    def register_inspection(self, widget: QWidget, meaning: str, topic: str) -> None:
        """Register only reviewed control instances or their scoped composites."""
        self.inspection[widget] = ControlHelpRegistration(meaning, topic)
        widget.setProperty("krakenInspectionRegistry", id(self))
        widget.setProperty("krakenInspectionMeaning", meaning)
        widget.setProperty("krakenInspectionTopic", topic)
        # Native Shift+F1 eligibility; the controller supplies validated text.
        widget.setWhatsThis(" ")
        self._watch(widget)

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
                    registration = ControlHelpRegistration(meaning, topic)
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
