"""Apply theme colors to visible presentation scopes without global repolishing."""

import weakref
from typing import Any

import shiboken6
from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QMenuBar, QTabBar, QWidget

from src.core.theme_manager import ThemeManager
from src.gui.utils.theme_connections import flush_theme_subscriptions
from src.gui.utils.theme_stylesheet import ThemeStylePack, compile_theme_stylesheet

_BEGIN = "/* Kraken scoped theme begin */"
_END = "/* Kraken scoped theme end */"
_FRAME_INTERVAL_MS = 16
_OCCLUDED_FALLBACK_MS = 250


class _ThemeScope(QObject):
    """One presentation subtree, stamped before its next visible frame."""

    def __init__(
        self,
        widget: QWidget,
        *,
        shell: bool = False,
        prefixes: tuple[str, ...] = (),
    ) -> None:
        super().__init__(widget)
        self.shell = shell
        self.prefixes = prefixes
        self.generation = -1
        self.priority = False

    def apply(
        self, pack: ThemeStylePack, theme: dict[str, str], generation: int
    ) -> None:
        widget = self.parent()
        if not isinstance(widget, QWidget) or not shiboken6.isValid(widget):
            return
        if self.shell:
            # MainWindow's native palette owns its background/text. Assigning a
            # sheet even for shell-only selectors repolishes every panel below it.
            self.generation = generation
            return
        local = widget.styleSheet()
        start = local.find(_BEGIN)
        if start >= 0:
            end = local.find(_END, start)
            if end >= 0:
                local = local[:start] + local[end + len(_END) :]
        colors = pack.render(theme, shell=self.shell, prefixes=self.prefixes)
        if local.strip() and "{" not in local:
            # Qt accepts declaration-only local sheets. Normalize their local
            # override before concatenating explicit application color rules.
            local = "QWidget { " + local.strip() + " }"
        combined = _BEGIN + "\n" + colors + "\n" + _END + local.strip()
        if widget.styleSheet() != combined:
            widget.setStyleSheet(combined)
        self.generation = generation


class ThemePresentation(QObject):
    """Own style scopes; callers supply snapshots rather than application facades."""

    def __init__(self, app: QApplication) -> None:
        """Install a small Show-event filter and retain no application facade."""
        super().__init__(app)
        self._app = app
        self._pack: ThemeStylePack | None = None
        self._template = ""
        self._theme: dict[str, str] = {}
        self._generation = 0
        self._scopes: dict[int, _ThemeScope] = {}
        self._active = True
        self._queued: list[_ThemeScope] = []
        self._waiting: QWidget | None = None
        self._continuation = QTimer(self)
        self._continuation.setSingleShot(True)
        self._continuation.timeout.connect(self._continue)
        app.aboutToQuit.connect(self.close)
        app.installEventFilter(self)

    def register(
        self, widget: QWidget, prefixes: tuple[str, ...] = (), *, priority: bool = False
    ) -> None:
        """Register a panel/window; hidden roots retain their last visible theme."""
        pointer = shiboken6.getCppPointer(widget)[0]
        if pointer in self._scopes:
            self._scopes[pointer].priority |= priority
            return
        scope = _ThemeScope(
            widget, shell=isinstance(widget, QMainWindow), prefixes=prefixes
        )
        self._scopes[pointer] = scope
        scope.priority = priority
        reference = weakref.ref(self)

        def removed() -> None:
            runtime = reference()
            if runtime is not None:
                runtime._scopes.pop(pointer, None)

        scope.destroyed.connect(removed)
        if widget.isVisible() and self._pack is not None:
            scope.apply(self._pack, self._theme, self._generation)

    def present(self, app: QApplication, template: str, theme: dict[str, Any]) -> None:
        """Apply only fixed metrics globally; refresh visible color scopes last."""
        if template != self._template or self._pack is None:
            self._pack = compile_theme_stylesheet(template)
            self._template = template
            app.setStyleSheet(self._pack.metrics)
        self._theme = dict(theme)
        self._generation += 1
        self._continuation.stop()
        self._waiting = None
        self._queued = []
        for widget in app.topLevelWidgets():
            self.register(widget)
        visible = []
        for scope in list(self._scopes.values()):
            parent = scope.parent()
            if isinstance(parent, QWidget) and parent.isVisible():
                visible.append(scope)
        priorities = [scope for scope in visible if scope.priority]
        if priorities:
            first = priorities[0]
            self._queued = [scope for scope in visible if scope is not first]
            # Panels precede shell-only bookkeeping when OK hides Settings.
            self._queued.sort(key=lambda scope: (scope.shell, bool(scope.prefixes)))
            self._apply(first)
            self._wait_for_paint(first)
        else:
            for scope in visible:
                self._apply(scope)

    @property
    def is_pending(self) -> bool:
        """Whether additional visible scopes still need their current colors."""
        return bool(self._queued or self._waiting is not None)

    def _scope_for(self, widget: QWidget) -> _ThemeScope | None:
        current: QWidget | None = widget
        while current is not None:
            scope = self._scopes.get(shiboken6.getCppPointer(current)[0])
            if scope is not None:
                return scope
            current = current.parentWidget()
        return None

    def _apply(self, scope: _ThemeScope) -> None:
        if not shiboken6.isValid(scope) or self._pack is None:
            return
        generation = self._generation
        flush_theme_subscriptions(lambda widget: self._scope_for(widget) is scope)
        if generation != self._generation or not shiboken6.isValid(scope):
            return
        scope.apply(self._pack, self._theme, generation)
        parent = scope.parent()
        if scope.shell or scope.prefixes or not isinstance(parent, QWidget):
            return
        # Tab/menu chrome is part of its panel's coherent frame, not a later job.
        for chrome in list(self._scopes.values()):
            child = chrome.parent()
            if (
                chrome.prefixes
                and isinstance(child, QWidget)
                and child.isVisible()
                and parent.isAncestorOf(child)
                and generation == self._generation
            ):
                flush_theme_subscriptions(
                    lambda widget: self._scope_for(widget) is chrome
                )
                if shiboken6.isValid(chrome) and generation == self._generation:
                    chrome.apply(self._pack, self._theme, generation)

    def _wait_for_paint(self, scope: _ThemeScope) -> None:
        if not self._queued:
            self._waiting = None
            return
        parent = scope.parent() if shiboken6.isValid(scope) else None
        if isinstance(parent, QWidget) and parent.isVisible():
            self._waiting = parent
            parent.update()
            # Occluded windows may not paint. Never leave the queue stranded.
            self._continuation.start(_OCCLUDED_FALLBACK_MS)
        else:
            self._continuation.start(0)

    def _continue(self) -> None:
        self._waiting = None
        while self._queued:
            scope = self._queued.pop(0)
            if not shiboken6.isValid(scope):
                continue
            if scope.generation == self._generation:
                continue
            parent = scope.parent()
            if isinstance(parent, QWidget) and parent.isVisible():
                self._apply(scope)
                self._wait_for_paint(scope)
                return

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Bring registered and newly opened scopes current before painting."""
        kind = event.type()
        if kind not in (QEvent.Type.Show, QEvent.Type.Paint, QEvent.Type.Hide):
            return False
        if not isinstance(watched, QWidget):
            return False
        if watched is self._waiting:
            if kind == QEvent.Type.Paint:
                # Leave one compositor frame for the changed Settings window.
                self._waiting = None
                self._continuation.start(_FRAME_INTERVAL_MS)
            elif kind == QEvent.Type.Hide:
                self._continuation.stop()
                self._continue()
        if kind != QEvent.Type.Show:
            return False
        if watched.isWindow():
            self.register(watched)
        elif isinstance(watched, (QTabBar, QMenuBar)):
            self.register(
                watched, ("QTabBar",) if isinstance(watched, QTabBar) else ("QMenuBar",)
            )
        scope = self._scopes.get(shiboken6.getCppPointer(watched)[0])
        if scope is not None and self._pack is not None:
            # A pending local callback can have replaced a root's local sheet.
            self._apply(scope)
        return False

    def close(self) -> None:
        """Release a test/diagnostic runtime without changing current preferences."""
        if self._active:
            self._app.removeEventFilter(self)
            ThemeManager().set_presentation_handler(None)
            self._active = False
            self._queued = []
            self._waiting = None
            self._continuation.stop()


def install_theme_presentation(app: QApplication) -> ThemePresentation:
    """Compose GUI presentation through a narrow core callback, before windows show."""
    existing = getattr(app, "_kraken_theme_presentation", None)
    if isinstance(existing, ThemePresentation) and existing._active:
        return existing
    runtime = ThemePresentation(app)
    setattr(app, "_kraken_theme_presentation", runtime)
    ThemeManager().set_presentation_handler(runtime.present)
    return runtime


def register_theme_scope(widget: QWidget, *, priority: bool = False) -> None:
    """Declare a feature panel boundary without coupling its owner to MainWindow."""
    app = QApplication.instance()
    runtime = getattr(app, "_kraken_theme_presentation", None)
    if isinstance(runtime, ThemePresentation) and runtime._active:
        runtime.register(widget, priority=priority)


def refresh_theme_scope(widget: QWidget) -> None:
    """Restore a root's color layer after a deferred local Show-time refresh."""
    app = QApplication.instance()
    runtime = getattr(app, "_kraken_theme_presentation", None)
    if isinstance(runtime, ThemePresentation) and runtime._active:
        scope = runtime._scopes.get(shiboken6.getCppPointer(widget)[0])
        if scope is not None and runtime._pack is not None:
            scope.apply(runtime._pack, runtime._theme, runtime._generation)
