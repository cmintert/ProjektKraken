"""GUI-local ownership of LanguageTool scheduling and transient presentation."""

from __future__ import annotations

import weakref
from dataclasses import dataclass
from typing import cast

import shiboken6
from PySide6.QtCore import QObject, QSettings, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QApplication, QMenu, QTextEdit

from src.core.theme_manager import ThemeManager
from src.gui.utils.help_context import declare_inspection
from src.services.language_tool_service import LanguageToolWorker, LTMatch

_MINIMUM_TEXT_LENGTH = 15


@dataclass(frozen=True)
class _Settings:
    enabled: bool
    language: str
    username: str
    api_key: str


def _settings() -> _Settings:
    from src.services.language_tool_service import language_tool_credentials

    settings = QSettings()
    username, api_key = language_tool_credentials(settings)
    return _Settings(
        cast(bool, settings.value("SpellCheck/enabled", False, type=bool)),
        cast(str, settings.value("SpellCheck/language", "auto")),
        username,
        api_key,
    )


class SpellCheckController(QObject):
    """Own one editor's checks; only detached request/result data crosses threads."""

    check_requested = Signal(int, int, str, str, str, str)

    def __init__(self, editor: QTextEdit) -> None:
        """Attach scheduling and cleanup to the lifetime of a standard text edit."""
        super().__init__(editor)
        self._editor = weakref.ref(editor)
        self._observed_text = editor.toPlainText()
        self._active = True
        self._settings = _settings()
        self._generation = 0
        self._request_id = 0
        self._pending: tuple[int, int, str] | None = None
        self._matches: list[LTMatch] = []
        self._matches_revision: int | None = None
        self._checked_text = ""
        self._thread: QThread | None = None
        self._worker: LanguageToolWorker | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(800)
        self._timer.timeout.connect(self.check_now)
        editor.textChanged.connect(self._text_changed)
        editor.document().contentsChanged.connect(self._document_changed)
        editor.destroyed.connect(self.shutdown)
        ThemeManager().theme_changed.connect(self._theme_changed)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    def _view(self) -> QTextEdit | None:
        editor = self._editor()
        return editor if editor is not None and shiboken6.isValid(editor) else None

    @Slot()
    def _text_changed(self) -> None:
        editor = self._view()
        if editor is not None:
            self._observed_text = editor.toPlainText()
        self.clear()
        if self._active:
            self._timer.start()

    @Slot()
    def _document_changed(self) -> None:
        # Programmatic updates may block widget signals. Observe actual text
        # changes independently, without clearing matches for rehighlight alone.
        editor = self._view()
        if editor is not None and editor.toPlainText() != self._observed_text:
            self._text_changed()

    def _sync_settings(self) -> None:
        settings = _settings()
        if settings != self._settings:
            self._settings = settings
            self._generation += 1
            self.clear()

    def refresh_settings(self) -> None:
        """Invalidate old settings and check immediately when enabled."""
        self._sync_settings()
        self._timer.stop()
        if self._settings.enabled:
            self.check_now()
        else:
            self.clear()

    def resume(self) -> None:
        """Reactivate a surviving editor after it has been closed and shown again."""
        if not self._active:
            self._active = True
            self.clear()
            self._timer.start()

    def _ensure_worker(self) -> None:
        if self._thread is not None:
            return
        thread = QThread(self)
        worker = LanguageToolWorker()
        worker.moveToThread(thread)
        worker.revision_results_ready.connect(
            self._on_results, Qt.ConnectionType.QueuedConnection
        )
        self.check_requested.connect(
            worker.check_revision, Qt.ConnectionType.QueuedConnection
        )
        thread.finished.connect(worker.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot()
    def check_now(self) -> None:
        """Check rendered plain text, retaining the existing minimum length of 15."""
        self._timer.stop()
        editor = self._view()
        if not self._active or editor is None:
            return
        self._sync_settings()
        if not self._settings.enabled:
            return
        text = editor.toPlainText()
        if len(text.strip()) < _MINIMUM_TEXT_LENGTH:
            self.clear()
            return
        self._ensure_worker()
        self._request_id += 1
        revision = editor.document().revision()
        self._pending = (self._generation, revision, text)
        self.check_requested.emit(
            self._request_id,
            revision,
            text,
            self._settings.language,
            self._settings.username,
            self._settings.api_key,
        )

    @Slot(int, int, list)
    def _on_results(
        self, request_id: int, document_revision: int, matches: list[LTMatch]
    ) -> None:
        editor = self._view()
        if not self._active or editor is None:
            return
        self._sync_settings()
        expected = (self._generation, document_revision, editor.toPlainText())
        if (
            not self._settings.enabled
            or request_id != self._request_id
            or self._pending != expected
            or document_revision != editor.document().revision()
        ):
            return
        self._apply_results(matches)

    def _apply_results(self, matches: list[LTMatch]) -> None:
        editor = self._view()
        if editor is None or not self._active:
            return
        self._matches = list(matches)
        self._matches_revision = editor.document().revision()
        self._checked_text = editor.toPlainText()
        self._render()

    def _render(self) -> None:
        editor = self._view()
        if editor is None:
            return
        fmt = QTextCharFormat()
        fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        fmt.setUnderlineColor(QColor(ThemeManager().get_theme()["error"]))
        selections = []
        for match in self._matches:
            cursor = QTextCursor(editor.document())
            cursor.setPosition(match.offset)
            cursor.setPosition(
                match.offset + match.length, QTextCursor.MoveMode.KeepAnchor
            )
            selection = QTextEdit.ExtraSelection()
            setattr(selection, "cursor", cursor)
            setattr(selection, "format", fmt)
            selections.append(selection)
        editor.setExtraSelections(selections)

    @Slot(dict)
    def _theme_changed(self, _theme: dict) -> None:
        editor = self._view()
        if not self._active or editor is None:
            return
        # QSyntaxHighlighter.rehighlight() can advance Qt's document revision
        # without changing text or undo. The view's theme slot runs before ours.
        if self._matches and self._checked_text != editor.toPlainText():
            self.clear()
            return
        if self._matches:
            self._matches_revision = editor.document().revision()
        if self._pending and self._pending[1] != editor.document().revision():
            self._request_id += 1
            self._pending = None
            self._timer.start()
        self._render()

    def clear(self) -> None:
        """Invalidate pending work and remove transient spelling presentation."""
        self._request_id += 1
        self._pending = None
        self._matches = []
        self._matches_revision = None
        self._checked_text = ""
        editor = self._view()
        if editor is not None:
            editor.setExtraSelections([])

    def match_at(self, position: int) -> LTMatch | None:
        """Return the current spelling match under a document position."""
        return next(
            (m for m in self._matches if m.offset <= position < m.offset + m.length),
            None,
        )

    def add_menu_actions(self, menu: QMenu, match: LTMatch) -> None:
        """Append spelling actions without taking ownership of the context menu."""
        for suggestion in match.replacements[:5]:
            action = menu.addAction(suggestion)
            editor = self._view()
            action.setEnabled(editor is not None and not editor.isReadOnly())
            action.triggered.connect(
                lambda _checked=False, s=suggestion, m=match: self.apply_suggestion(
                    s, m
                )
            )
        if match.replacements:
            menu.addSeparator()
        ignore_action = declare_inspection(
            menu.addAction(f"Ignore ({match.rule_id})"),
            "src-gui-widgets-wiki-text-edit-wikitexteditview-contextmenuevent-ignore-action|writing.edit|help-inspect-src-gui-widgets-wiki-text-edit-wikitexteditview-contextmenuevent-ignore-action",
        )
        ignore_action.triggered.connect(lambda _checked=False: self.ignore_match(match))
        menu.addSeparator()

    def apply_suggestion(self, replacement: str, match: LTMatch) -> None:
        """Replace only a still-current match using the document's ordinary undo."""
        editor = self._view()
        if (
            not self._active
            or editor is None
            or editor.isReadOnly()
            or not any(current is match for current in self._matches)
            or self._matches_revision != editor.document().revision()
            or self._checked_text != editor.toPlainText()
        ):
            return
        cursor = QTextCursor(editor.document())
        cursor.setPosition(match.offset)
        cursor.setPosition(match.offset + match.length, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(replacement)

    def ignore_match(self, match: LTMatch) -> None:
        """Ignore this occurrence without changing text or undo history."""
        if self._active and any(current is match for current in self._matches):
            self._matches = [m for m in self._matches if m is not match]
            self._render()

    @Slot()
    def shutdown(self) -> None:
        """Stop and join work without accessing the possibly dying editor."""
        self._active = False
        self._timer.stop()
        self._request_id += 1
        self._pending = None
        self._matches = []
        thread, worker = self._thread, self._worker
        if thread is None:
            return
        if worker is not None and shiboken6.isValid(worker):
            self.check_requested.disconnect(worker.check_revision)
        thread.quit()
        thread.wait()
        thread.deleteLater()
        self._thread = None
        self._worker = None
