"""Contextual offline Help orchestration without authoring mutations."""

from __future__ import annotations

import weakref
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import shiboken6
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QImage, QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QWidget

from src.gui.dialogs.help_aware_dialog import HelpAwareDialog
from src.gui.utils.help_context import (
    HelpContextRegistry,
    ancestors,
    help_focus_transfer,
    owns_help_input,
)
from src.gui.widgets.help_viewer import HelpViewer
from src.services.help_bundle_service import HelpBundleError, HelpBundleService
from src.services.help_search_service import HelpSearchResult, HelpSearchService


@dataclass
class HelpLocation:
    """A Help-only navigation entry, including its reading position."""

    uri: str
    title: str
    related: tuple[str, ...] = ()
    scroll: int = 0


class HelpCoordinator(QObject):
    """Own context, validated navigation, focus and modal companion lifecycle."""

    stopped = Signal()

    def __init__(
        self,
        owner: QWidget,
        registry: HelpContextRegistry,
        service: HelpBundleService,
        viewer_factory: Callable[[QWidget], HelpViewer] = HelpViewer,
    ) -> None:
        """Install one application-local dispatcher with narrow dependencies."""
        super().__init__(owner)
        self.owner = owner
        self.registry = registry
        self.service = service
        self.viewer = viewer_factory(owner)
        self.origin: weakref.ReferenceType[QWidget] | None = None
        self.fallback: weakref.ReferenceType[QWidget] | None = None
        self.history: list[HelpLocation] = []
        self.index = -1
        self._stopping = False
        self._suspended: weakref.ReferenceType[QWidget] | None = None
        self._dialogs: weakref.WeakSet[QDialog] = weakref.WeakSet()
        self.search_results: tuple[HelpSearchResult, ...] = ()
        self._search_query: str | None = None
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(200)
        self.search_timer.timeout.connect(self.search)
        self.viewer.search_requested.connect(self.show_search)
        self.viewer.query_changed.connect(lambda _query: self.search_timer.start())
        self.viewer.search_activate_requested.connect(self.activate_search)
        self.viewer.result_requested.connect(self.open_search_result)
        self.viewer.back_requested.connect(lambda: self.move(-1))
        self.viewer.forward_requested.connect(lambda: self.move(1))
        self.viewer.manual_requested.connect(lambda: self.open_topic("manual.home"))
        self.viewer.refresh_requested.connect(self.refresh)
        self.viewer.return_requested.connect(self.return_to_work)
        self.viewer.link_requested.connect(self.follow_link)
        self.viewer.browser.resource_requested.connect(self.load_resource)
        from src.app.help_inspection_controller import HelpInspectionController

        self.inspection = HelpInspectionController(registry, service, self)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.installEventFilter(self)
            app.focusChanged.connect(self.track_origin)
            app.aboutToQuit.connect(self.stop)

    def show_search(self) -> None:
        """Open search even when no authoring control currently has focus."""
        if self.index < 0:
            self.open_topic("manual.home")
        else:
            self.show()
        self.viewer.show_search()
        self.search()

    def search(self) -> None:
        """Search fresh validated canonical snapshots without retaining queries."""
        self.search_timer.stop()
        query = self.viewer.query.text()
        selected = self.viewer.results.currentRow()
        previous = (
            self.search_results[selected]
            if query == self._search_query and 0 <= selected < len(self.search_results)
            else None
        )
        try:
            self.service.validate()
            self.search_results = HelpSearchService(
                self.service.search_documents()
            ).search(query)
            selected = next(
                (
                    index
                    for index, result in enumerate(self.search_results)
                    if previous is not None
                    and (result.page, result.fragment)
                    == (previous.page, previous.fragment)
                ),
                0,
            )
            self._search_query = query
            status = (
                f"{len(self.search_results)} results"
                if self.search_results
                else "No matching Help topics. Try fewer words."
            )
            if not query.strip():
                status = "Search tasks or concepts, such as border, uncertain date or relation validity."
            self.viewer.set_search_results(
                [
                    result.title + "\n" + result.snippet
                    for result in self.search_results
                ],
                status,
            )
            if self.search_results:
                self.viewer.results.setCurrentRow(selected)
        except HelpBundleError as exc:
            self.search_results = ()
            self.viewer.set_search_results([], "Help search is unavailable.")
            self.error(exc)

    def activate_search(self) -> None:
        """Flush pending typing before Enter activates the selected destination."""
        row = self.viewer.results.currentRow()
        pending = self.search_timer.isActive()
        if pending:
            self.search()
        self.open_search_result(0 if pending or row < 0 else row)

    def open_search_result(self, row: int) -> None:
        """Use the same confined navigation and history as manual links."""
        if not 0 <= row < len(self.search_results):
            return
        result = self.search_results[row]
        try:
            self.navigate(
                HelpLocation(
                    result.page + "#" + result.fragment, result.title, result.topic_ids
                )
            )
            self.viewer.browser.setFocus()
        except HelpBundleError as exc:
            self.error(exc)

    def belongs(self, widget: QObject | None) -> bool:
        """Limit help handling to this application's widget tree."""
        return any(
            item is self.owner
            or isinstance(item, QWidget)
            and (item in self.registry.panels or item in self.registry.owners)
            for item in ancestors(widget)
        )

    @staticmethod
    def live(reference: weakref.ReferenceType[QWidget] | None) -> QWidget | None:
        """Resolve a weak reference only while its Qt object survives."""
        widget = reference() if reference else None
        return widget if widget is not None and shiboken6.isValid(widget) else None

    def track_origin(self, _old: QWidget | None, now: QWidget | None) -> None:
        """Remember focus without chasing it in the reader."""
        if now is None or owns_help_input(now) or not self.belongs(now):
            return
        if any(isinstance(item, QMenu) for item in ancestors(now)):
            return
        if now.window().windowType() == Qt.WindowType.Popup:
            return
        suspended = self.live(self._suspended)
        if suspended is not None:
            suspended.setProperty("krakenHelpSuspendedOrigin", False)
        self._suspended = None
        self.origin = weakref.ref(now)

    def request(self) -> None:
        """Open the current task, capturing focus before activating the reader."""
        focus = QApplication.focusWidget()
        if owns_help_input(focus):
            self.show()
            return
        self.track_origin(None, focus)
        self.refresh()

    def refresh(self) -> None:
        """Resolve the last authoring origin on explicit user request."""
        try:
            self.service.validate()
            candidates, boundary = self.registry.candidates(self.live(self.origin))
            self.fallback = weakref.ref(boundary) if boundary is not None else None
            for candidate in candidates:
                topic = self.service.find_topic(candidate)
                if topic is not None:
                    self.open_topic(topic.id)
                    return
        except HelpBundleError as exc:
            self.error(exc)
        self.show()

    def open_topic(self, topic_id: str) -> None:
        """Navigate to a semantic topic using the validated bundle metadata."""
        try:
            if not self.viewer.isVisible():
                self.service.validate()
            topic = self.service.resolve_topic(topic_id)
            self.navigate(
                HelpLocation(
                    topic.page + "#" + topic.fragment,
                    topic.title,
                    topic.related_ids,
                )
            )
        except HelpBundleError as exc:
            self.error(exc)
        self.show()

    def save_scroll(self) -> None:
        """Capture the reader position before leaving its entry."""
        if self.index >= 0:
            self.history[
                self.index
            ].scroll = self.viewer.browser.verticalScrollBar().value()

    def navigate(self, location: HelpLocation) -> None:
        """Validate before committing a new Help history entry."""
        self.service.resource_path(location.uri)
        if self.index >= 0 and self.history[self.index].uri == location.uri:
            self.save_scroll()
            self.render(self.history[self.index], restore=True)
            return
        self.save_scroll()
        self.history = self.history[: self.index + 1]
        self.history.append(location)
        self.index += 1
        self.render(location)

    def render(self, location: HelpLocation, *, restore: bool = False) -> None:
        """Render generated HTML and related topics through GUI snapshots."""
        url = QUrl(location.uri)
        browser = self.viewer.browser
        page = self.service.load_page(url.path())
        browser.document().setBaseUrl(QUrl.fromLocalFile(str(self.service.root) + "/"))
        self.viewer.set_content(page)
        browser.scrollToAnchor(url.fragment())
        if restore:
            browser.verticalScrollBar().setValue(location.scroll)
        self.viewer.title.setText(location.title)
        links: list[tuple[str, str]] = []
        for topic_id in location.related:
            topic = self.service.find_topic(topic_id)
            if topic is not None:
                links.append(("topic:" + topic.id, topic.title))
        self.viewer.set_related(links)
        self.viewer.set_history(self.index > 0, self.index + 1 < len(self.history))

    def move(self, delta: int) -> None:
        """Move only within Help history."""
        target = self.index + delta
        if not 0 <= target < len(self.history):
            return
        self.save_scroll()
        try:
            self.render(self.history[target], restore=True)
            self.index = target
            self.viewer.set_history(target > 0, target + 1 < len(self.history))
        except HelpBundleError as exc:
            self.error(exc)

    def local_uri(self, url: QUrl) -> str:
        """Normalize document-relative URLs without permitting external files."""
        if url.hasQuery():
            raise HelpBundleError("path", "Help links cannot contain a query.")
        if url.isLocalFile():
            path = Path(url.toLocalFile()).resolve()
            if not path.is_relative_to(self.service.root):
                raise HelpBundleError("path", "Help link is outside the bundle.")
            uri = path.relative_to(self.service.root).as_posix()
            return uri + ("#" + url.fragment() if url.hasFragment() else "")
        if not url.path() and url.hasFragment() and self.index >= 0:
            return self.history[self.index].uri.split("#")[0] + "#" + url.fragment()
        return url.toString()

    def follow_link(self, url: QUrl) -> None:
        """Follow validated internal links; external references stay local."""
        if url.scheme() == "topic":
            self.open_topic(url.path())
            return
        try:
            uri = self.local_uri(url)
            self.service.resource_path(uri)
            title = next(
                (p.title for p in self.service.pages() if p.path == QUrl(uri).path()),
                "Help",
            )
            self.navigate(HelpLocation(uri, title))
        except HelpBundleError as exc:
            self.error(exc)

    def load_resource(self, _kind: int, url: QUrl) -> None:
        """Supply only hash-checked local images to the renderer."""
        try:
            path = self.service.resource_path(self.local_uri(url))
            self.viewer.browser.resource_result = QImage(str(path))
        except HelpBundleError:
            self.viewer.browser.resource_result = QImage()

    def error(self, exc: HelpBundleError) -> None:
        """Clear stale reference text and show an accessible local recovery route."""
        self.search_results = ()
        self.viewer.set_search_results([], "Help search is unavailable.")
        self.viewer.title.setText("Help unavailable")
        self.viewer.set_error(str(exc))
        self.viewer.set_related([])
        self.viewer.set_history(False, False)

    def transfer(self, parent: QWidget) -> None:
        """Reparent before owner teardown without losing reading state."""
        if self.viewer.parentWidget() is parent:
            return
        visible = self.viewer.isVisible()
        geometry = self.viewer.geometry()
        self.viewer.setParent(parent, Qt.WindowType.Window)
        self.viewer.setGeometry(geometry)
        if visible:
            self.viewer.show()

    def prepare_dialog_close(self, dialog: QDialog) -> None:
        """Detach the companion before a modal owner tears down its children."""
        self.inspection.owner_closing(dialog)
        if not shiboken6.isValid(self.viewer):
            return
        if not any(item is dialog for item in ancestors(self.viewer.parentWidget())):
            return
        parent = next(
            (
                item
                for item in ancestors(dialog.parentWidget())
                if isinstance(item, QDialog)
            ),
            self.owner,
        )
        self.transfer(parent)

    def show(self) -> None:
        """Activate the one companion with the correct current modal owner."""
        self.suspend_origin()
        modal = QApplication.activeModalWidget()
        parent = (
            modal if isinstance(modal, QDialog) and self.belongs(modal) else self.owner
        )
        with help_focus_transfer():
            self.transfer(parent)
            self.viewer.show()
            self.viewer.raise_()
            self.viewer.activateWindow()
            self.viewer.browser.setFocus(Qt.FocusReason.OtherFocusReason)

    def suspend_origin(self) -> None:
        """Protect unfinished input before the Help menu or window takes focus."""
        origin = self.live(self.origin)
        if origin is not None:
            origin.setProperty("krakenHelpSuspendedOrigin", True)
            self._suspended = weakref.ref(origin)

    def return_to_work(self) -> None:
        """Hide Help and restore only a surviving visible origin."""
        if shiboken6.isValid(self.viewer):
            self.viewer.hide()
        for reference in (self.origin, self.fallback):
            widget = self.live(reference)
            if widget is not None and widget.isVisible():
                widget.window().activateWindow()
                widget.setFocus(Qt.FocusReason.OtherFocusReason)
                break

    def stop(self) -> None:
        """Disconnect application callbacks without restoring authoring focus."""
        if self._stopping:
            return
        self._stopping = True
        self.search_timer.stop()
        self.inspection.stop()
        self.stopped.emit()
        suspended = self.live(self._suspended)
        if suspended is not None:
            suspended.setProperty("krakenHelpSuspendedOrigin", False)
        self.registry.clear()
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.removeEventFilter(self)
            app.focusChanged.disconnect(self.track_origin)
        if shiboken6.isValid(self.viewer):
            self.viewer.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Dispatch Help and detach modal companions before deferred deletion."""
        # Theme/polish/paint events need no context lookup. Dialogs still receive
        # lifecycle registration before their first input or deferred deletion.
        if not isinstance(watched, QDialog) and event.type() not in {
            QEvent.Type.KeyPress,
            QEvent.Type.ShortcutOverride,
        }:
            return False
        if self._stopping or not self.belongs(watched):
            return False
        if isinstance(watched, QDialog):
            if watched not in self._dialogs:
                self._dialogs.add(watched)
                watched.finished.connect(
                    lambda _result, d=watched: self.prepare_dialog_close(d)
                )
                if isinstance(watched, HelpAwareDialog):
                    watched.preparing_to_close.connect(
                        lambda d=watched: self.prepare_dialog_close(d)
                    )
            if event.type() in {QEvent.Type.Close, QEvent.Type.DeferredDelete}:
                self.prepare_dialog_close(watched)
        if event.type() not in {QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride}:
            return False
        if not isinstance(event, QKeyEvent):
            return False
        sequence = QKeySequence(event.keyCombination())
        is_help = sequence in QKeySequence.keyBindings(
            QKeySequence.StandardKey.HelpContents
        )
        is_help = is_help or (
            event.key() == Qt.Key.Key_F1
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
        )
        local = owns_help_input(watched)
        is_find = local and event.matches(QKeySequence.StandardKey.Find)
        handled = (
            is_help
            or (local and event.key() in {Qt.Key.Key_Escape, Qt.Key.Key_F11})
            or is_find
        )
        if handled:
            event.accept()
            if event.type() == QEvent.Type.KeyPress:
                if is_find:
                    self.show_search()
                elif is_help:
                    self.request()
                elif event.key() == Qt.Key.Key_Escape:
                    if self.viewer.search_panel.isVisible():
                        self.viewer.hide_search()
                    else:
                        self.return_to_work()
            return True
        return False
