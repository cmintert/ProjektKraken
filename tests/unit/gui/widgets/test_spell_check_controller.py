"""Behavior and QObject lifetime regressions for the extracted spelling owner."""

import threading

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
from PySide6.QtWidgets import QMenu, QTextEdit, QWidget

from src.core.theme_manager import ThemeManager
from src.gui.dialogs.spell_check_settings_dialog import SpellCheckSettingsDialog
from src.gui.widgets.spell_check_controller import SpellCheckController
from src.gui.widgets.wiki_text_edit import WikiTextEdit
from src.services.language_tool_service import LanguageToolWorker, LTMatch

TEXT = "Hello wrld in this sentence."
pytestmark = [
    pytest.mark.ci_fast,
    pytest.mark.usefixtures("isolated_theme_manager"),
]


@pytest.fixture
def spelling(qtbot, monkeypatch):
    QSettings().setValue("SpellCheck/enabled", True)
    monkeypatch.setattr(LanguageToolWorker, "check", lambda *a, **kw: None)
    view = QTextEdit()
    qtbot.addWidget(view)
    controller = SpellCheckController(view)
    view.setPlainText(TEXT)
    requests = []
    controller.check_requested.connect(lambda *a: requests.append(a))
    yield view, controller, requests
    if shiboken6.isValid(controller):
        controller.shutdown()


def match():
    return LTMatch(6, 4, "Spelling", ["world", "word"], "SPELL", "misspelling")


def complete(controller, request, matches=None):
    controller._on_results(
        request[0], request[1], [match()] if matches is None else matches
    )


def test_debounce_restarts_and_checks_latest_text(spelling, qtbot):
    view, controller, requests = spelling
    controller._timer.setInterval(50)
    view.insertPlainText("First ")
    qtbot.wait(30)
    view.insertPlainText("Second ")
    qtbot.wait(30)
    assert not requests
    qtbot.waitUntil(lambda: len(requests) == 1)
    assert requests[0][2] == view.toPlainText()


def test_reordered_results_do_not_replace_current_matches(spelling):
    view, controller, requests = spelling
    controller.check_now()
    first = requests[-1]
    controller.check_now()
    second = requests[-1]
    complete(controller, second)
    complete(controller, first, [])
    assert view.extraSelections()[0].cursor.selectedText() == "wrld"


def test_blocked_widget_signals_still_invalidate_changed_document(spelling):
    view, controller, requests = spelling
    controller.check_now()
    old = requests[-1]
    complete(controller, old)
    view.blockSignals(True)
    try:
        view.insertPlainText("New ")
    finally:
        view.blockSignals(False)
    assert not view.extraSelections()
    complete(controller, old)
    assert not view.extraSelections()
    assert controller._timer.isActive()


@pytest.mark.parametrize(
    "change", ["edit", "disable", "language", "credentials", "close"]
)
def test_pending_results_invalidated_by_context_change(spelling, change):
    view, controller, requests = spelling
    controller.check_now()
    request = requests[-1]
    if change == "edit":
        view.insertPlainText("New ")
    elif change == "close":
        controller.shutdown()
    else:
        key, value = {
            "disable": ("enabled", False),
            "language": ("language", "de-DE"),
            "credentials": ("api_key", "changed-test-key"),
        }[change]
        QSettings().setValue(f"SpellCheck/{key}", value)
        controller.refresh_settings()
    complete(controller, request)
    assert not view.extraSelections()


def test_disabled_result_rejected_even_without_explicit_refresh(spelling):
    view, controller, requests = spelling
    controller.check_now()
    QSettings().setValue("SpellCheck/enabled", False)
    complete(controller, requests[-1])
    assert not view.extraSelections()


def test_disable_clears_and_reenable_requires_fresh_result(spelling):
    view, controller, requests = spelling
    controller.check_now()
    old = requests[-1]
    complete(controller, old)
    QSettings().setValue("SpellCheck/enabled", False)
    controller.refresh_settings()
    assert not controller._timer.isActive()
    assert not view.extraSelections()
    QSettings().setValue("SpellCheck/enabled", True)
    controller.refresh_settings()
    complete(controller, old)
    assert not view.extraSelections()
    complete(controller, requests[-1])
    assert view.extraSelections()


def test_queued_worker_delivery_after_shutdown_is_inert(spelling, qapp):
    view, controller, requests = spelling
    controller.check_now()
    request = requests[-1]
    worker = controller._worker
    worker.revision_results_ready.emit(request[0], request[1], [match()])
    controller.shutdown()
    qapp.processEvents()
    assert not view.extraSelections()
    assert not controller._timer.isActive()


def test_application_exit_stops_worker_and_pending_debounce(spelling, qapp):
    view, controller, requests = spelling
    controller.check_now()
    worker = controller._worker
    thread = controller._thread
    view.insertPlainText("New ")
    assert controller._timer.isActive()
    qapp.aboutToQuit.emit()
    assert not controller._timer.isActive()
    assert controller._thread is None
    assert not thread.isRunning()
    assert not shiboken6.isValid(worker)
    previous_count = len(requests)
    controller.check_now()
    assert len(requests) == previous_count


def test_suggestion_is_one_undoable_edit_and_stale_action_is_inert(spelling):
    view, controller, requests = spelling
    controller.check_now()
    complete(controller, requests[-1])
    suggestion = controller._matches[0]
    controller.apply_suggestion("world", suggestion)
    assert view.toPlainText() == TEXT.replace("wrld", "world")
    view.undo()
    assert view.toPlainText() == TEXT
    assert not view.document().isUndoAvailable()
    controller.apply_suggestion("word", suggestion)
    assert view.toPlainText() == TEXT


def test_ignore_and_theme_refresh_preserve_authoring_context(
    spelling, qapp, monkeypatch
):
    view, controller, requests = spelling
    monkeypatch.setattr(qapp, "setStyleSheet", view.setStyleSheet)
    monkeypatch.setattr(qapp, "setPalette", view.setPalette)
    controller.check_now()
    complete(controller, requests[-1])
    cursor = view.textCursor()
    cursor.setPosition(2)
    cursor.setPosition(8, cursor.MoveMode.KeepAnchor)
    view.setTextCursor(cursor)
    before = (view.toHtml(), view.document().revision(), view.document().isModified())
    manager = ThemeManager()
    names = manager.get_available_themes()
    original = manager.current_theme_name
    try:
        for name in names:
            manager.set_theme(name, qapp)
            selection = view.extraSelections()[0]
            assert (
                selection.format.underlineColor().name()
                == manager.get_theme()["error"].lower()
            )
            assert (
                view.toHtml(),
                view.document().revision(),
                view.document().isModified(),
            ) == before
            assert (view.textCursor().anchor(), view.textCursor().position()) == (2, 8)
            assert not view.document().isUndoAvailable()
    finally:
        manager.set_theme(original, qapp)
    controller.ignore_match(controller._matches[0])
    assert not view.extraSelections()
    assert (
        view.toHtml(),
        view.document().revision(),
        view.document().isModified(),
    ) == before


def test_readonly_suggestion_is_disabled_and_cannot_mutate(spelling):
    view, controller, requests = spelling
    controller.check_now()
    complete(controller, requests[-1])
    view.setReadOnly(True)
    menu = QMenu(view)
    controller.add_menu_actions(menu, controller._matches[0])
    assert not menu.actions()[0].isEnabled()
    controller.apply_suggestion("world", controller._matches[0])
    assert view.toPlainText() == TEXT


def test_old_menu_action_cannot_apply_to_equal_fresh_match(spelling):
    view, controller, requests = spelling
    controller.check_now()
    complete(controller, requests[-1])
    menu = QMenu(view)
    controller.add_menu_actions(menu, controller._matches[0])
    controller.clear()
    controller.check_now()
    complete(controller, requests[-1])
    menu.actions()[0].trigger()
    assert view.toPlainText() == TEXT


@pytest.mark.parametrize("source", [False, True])
def test_real_wiki_theme_switch_preserves_matches_and_undo(
    qtbot, monkeypatch, qapp, source
):
    monkeypatch.setattr(LanguageToolWorker, "check", lambda *a, **kw: None)
    QSettings().setValue("SpellCheck/enabled", True)
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    monkeypatch.setattr(qapp, "setStyleSheet", widget.setStyleSheet)
    monkeypatch.setattr(qapp, "setPalette", widget.setPalette)
    widget.set_wiki_text(TEXT + " See [[Harbor]].")
    if source:
        widget.toggle_view_mode()
    view = widget.editor
    controller = view.spell_check
    requests = []
    controller.check_requested.connect(lambda *a: requests.append(a))
    controller.check_now()
    complete(controller, requests[-1])
    before = (
        widget.get_wiki_text(),
        view.document().isModified(),
        view.document().availableUndoSteps(),
        view.textCursor().position(),
        view.verticalScrollBar().value(),
    )
    manager = ThemeManager()
    original = manager.current_theme_name
    try:
        for theme in manager.get_available_themes():
            manager.set_theme(theme, qapp)
            assert view.extraSelections()[0].cursor.selectedText() == "wrld"
            assert view.extraSelections()[0].format.underlineColor().name() == (
                manager.get_theme()["error"].lower()
            )
            assert (
                widget.get_wiki_text(),
                view.document().isModified(),
                view.document().availableUndoSteps(),
                view.textCursor().position(),
                view.verticalScrollBar().value(),
            ) == before
        controller.apply_suggestion("world", controller._matches[0])
        assert "Hello world" in view.toPlainText()
        view.undo()
        assert widget.get_wiki_text() == before[0]
    finally:
        manager.set_theme(original, qapp)


@pytest.mark.parametrize("destroy_parent", [False, True])
def test_actual_destruction_joins_inflight_worker(
    qtbot, monkeypatch, destroy_parent, qapp
):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    def slow_check(worker, text, language, username, api_key, **kw):
        entered.set()
        assert release.wait(3)
        worker._emit_results([match()], kw["request_id"], kw["document_revision"])
        finished.set()

    monkeypatch.setattr(LanguageToolWorker, "check", slow_check)
    QSettings().setValue("SpellCheck/enabled", True)
    parent = QWidget()
    view = QTextEdit(parent)
    controller = SpellCheckController(view)
    view.setPlainText(TEXT)
    controller.check_now()
    qtbot.waitUntil(entered.is_set)
    timer = threading.Timer(0.03, release.set)
    timer.start()
    try:
        (parent if destroy_parent else view).deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qapp.processEvents()
        assert finished.is_set()
        assert not shiboken6.isValid(view)
        assert not shiboken6.isValid(controller)
    finally:
        release.set()
        timer.join()
        if shiboken6.isValid(parent):
            parent.deleteLater()


def test_close_and_reopen_wrapper_reactivates_spelling(qtbot, monkeypatch):
    monkeypatch.setattr(LanguageToolWorker, "check", lambda *a, **kw: None)
    QSettings().setValue("SpellCheck/enabled", True)
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.show()
    widget.editor.setPlainText(TEXT)
    controller = widget.editor.spell_check
    controller.check_now()
    widget.close()
    assert not controller._active
    widget.show()
    assert controller._active
    assert controller._timer.isActive()
    controller.check_now()
    assert controller._thread.isRunning()


def test_document_replacement_invalidates_pending_same_text(qtbot, monkeypatch):
    monkeypatch.setattr(LanguageToolWorker, "check", lambda *a, **kw: None)
    QSettings().setValue("SpellCheck/enabled", True)
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.set_wiki_text(TEXT)
    controller = widget.editor.spell_check
    requests = []
    controller.check_requested.connect(lambda *a: requests.append(a))
    controller.check_now()
    widget.editor.set_wiki_text(TEXT, force=True)
    complete(controller, requests[-1])
    assert not widget.editor.extraSelections()


@pytest.mark.parametrize("save", [False, True])
def test_settings_dialog_save_cancel_and_compatibility_export(qtbot, save):
    from src.gui.widgets.wiki_text_edit import SpellCheckSettingsDialog as Export

    assert Export is SpellCheckSettingsDialog
    settings = QSettings()
    settings.setValue("SpellCheck/enabled", False)
    settings.setValue("SpellCheck/language", "en-US")
    dialog = SpellCheckSettingsDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog._enabled_cb.setChecked(True)
    dialog._language_combo.setCurrentText("de-DE")
    dialog._username_edit.setText("test@example.invalid")
    dialog._apikey_edit.setText("test-key")
    if save:
        dialog._save()
    else:
        qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert settings.value("SpellCheck/enabled", type=bool) == save
    assert settings.value("SpellCheck/language") == ("de-DE" if save else "en-US")
    if save:
        assert settings.value("SpellCheck/username") == "test@example.invalid"
        assert settings.value("SpellCheck/api_key") == "test-key"


@pytest.mark.parametrize("save", [False, True])
def test_visible_settings_action_synchronizes_controller_and_check_state(
    qtbot, monkeypatch, save
):
    monkeypatch.setattr(LanguageToolWorker, "check", lambda *a, **kw: None)
    QSettings().setValue("SpellCheck/enabled", False)
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.editor.setPlainText(TEXT)
    widget.action_spell_check.trigger()
    dialog = widget.findChild(SpellCheckSettingsDialog)
    assert dialog is not None
    assert not widget.action_spell_check.isChecked()
    dialog._enabled_cb.setChecked(True)
    if save:
        dialog._save()
    else:
        dialog.reject()
    assert widget.action_spell_check.isChecked() == save
    assert widget.editor.spell_check._settings.enabled == save
    assert (widget.editor.spell_check._pending is not None) == save
