"""Unit tests for the LanguageTool spell/grammar check integration in WikiTextEdit.

These tests exercise the widget-side glue: settings gating, length-threshold
short-circuit, debounce wiring, underline application, context-menu dispatch,
ignore/apply behaviour, and lifecycle cleanup.

The network call itself is covered by ``tests/unit/services/test_language_tool_service.py``.
"""

from __future__ import annotations

from typing import List

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QContextMenuEvent

from src.gui.widgets.wiki_text_edit import WikiTextEdit
from src.services.language_tool_service import LTMatch


@pytest.fixture
def editor(qtbot, qapp) -> WikiTextEdit:
    """Create a ``WikiTextEdit`` wired up for spell-check tests.

    Uses an in-memory QSettings scope so tests do not bleed into user settings.
    """
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    settings = QSettings("ProjektKrakenTest", "SpellCheckTest")
    settings.clear()
    settings.beginGroup("SpellCheck")
    settings.setValue("enabled", False)
    settings.setValue("language", "en-US")
    settings.endGroup()

    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.set_wiki_text("")
    return widget


def _enable_spellcheck(language: str = "en-US") -> None:
    """Turn spell-check on in the global QSettings for the test."""
    s = QSettings()
    s.beginGroup("SpellCheck")
    s.setValue("enabled", True)
    s.setValue("language", language)
    s.setValue("username", "")
    s.setValue("api_key", "")
    s.endGroup()


def _make_match(offset: int, length: int, **kw) -> LTMatch:
    return LTMatch(
        offset=offset,
        length=length,
        message=kw.get("message", "Possible mistake."),
        replacements=kw.get("replacements", []),
        rule_id=kw.get("rule_id", "TEST_RULE"),
        issue_type=kw.get("issue_type", "misspelling"),
    )


class TestTriggerGating:
    """Tests for when/how ``_trigger_lt_check`` fires (or does not)."""

    def test_disabled_by_default_does_not_emit(self, editor: WikiTextEdit) -> None:
        emissions: List[tuple] = []
        editor.editor._lt_check_requested.connect(lambda *a: emissions.append(a))

        editor.editor.setPlainText("This is a long enough sentence to trigger.")
        editor.editor._trigger_lt_check()

        assert emissions == []

    def test_enabled_with_long_text_emits_check(
        self, editor: WikiTextEdit
    ) -> None:
        _enable_spellcheck()
        emissions: List[tuple] = []
        editor.editor._lt_check_requested.connect(lambda *a: emissions.append(a))

        editor.editor.setPlainText("This is a long enough sentence to trigger.")
        editor.editor._trigger_lt_check()

        assert len(emissions) == 1
        text, language, username, api_key = emissions[0]
        assert "long enough" in text
        assert language == "en-US"
        assert username == ""
        assert api_key == ""

    def test_short_text_skipped_and_clears_existing_underlines(
        self, editor: WikiTextEdit
    ) -> None:
        _enable_spellcheck()
        view = editor.editor
        # Seed an existing match to confirm it gets cleared.
        view._apply_lt_results([_make_match(0, 2)])
        assert len(view.extraSelections()) == 1

        emissions: List[tuple] = []
        view._lt_check_requested.connect(lambda *a: emissions.append(a))
        view.setPlainText("too short")
        view._trigger_lt_check()

        assert emissions == []
        assert view.extraSelections() == []
        assert view._lt_matches == []

    def test_trigger_uses_plaintext_not_raw_wiki_source(
        self, editor: WikiTextEdit
    ) -> None:
        """Regression test: offsets must align with ``document`` positions.

        Earlier the trigger sent ``_current_wiki_text`` (raw markdown with
        ``[[links]]`` preserved). In rich mode that string has different
        offsets than what the rendered document contains, causing underlines
        to land on the wrong span. The fix sends ``toPlainText()`` which is
        guaranteed to match cursor positions in ``document()``.
        """
        _enable_spellcheck()
        view = editor.editor
        view.set_wiki_text("Hello [[Gandalf|the wizard]] travels far.")

        emissions: List[tuple] = []
        view._lt_check_requested.connect(lambda *a: emissions.append(a))
        view._trigger_lt_check()

        assert len(emissions) == 1
        sent_text = emissions[0][0]
        # Raw WikiLink bracket syntax must not reach the service because the
        # offsets it would return could not be mapped back onto the document.
        assert "[[Gandalf" not in sent_text
        assert sent_text == view.toPlainText()


class TestApplyResults:
    """Tests for ``_apply_lt_results`` and extra-selection management."""

    def test_match_produces_extra_selection(self, editor: WikiTextEdit) -> None:
        view = editor.editor
        view.setPlainText("Hello wrld!")
        view._apply_lt_results([_make_match(offset=6, length=4)])

        sels = view.extraSelections()
        assert len(sels) == 1
        cursor = sels[0].cursor
        assert cursor.selectionStart() == 6
        assert cursor.selectionEnd() == 10
        assert cursor.selectedText() == "wrld"

    def test_multiple_matches_produce_multiple_selections(
        self, editor: WikiTextEdit
    ) -> None:
        view = editor.editor
        view.setPlainText("Hello wrld and tset!")
        view._apply_lt_results(
            [_make_match(6, 4), _make_match(15, 4)]
        )
        sels = view.extraSelections()
        assert len(sels) == 2
        assert {s.cursor.selectedText() for s in sels} == {"wrld", "tset"}

    def test_empty_match_list_clears_selections(self, editor: WikiTextEdit) -> None:
        view = editor.editor
        view.setPlainText("Hello wrld!")
        view._apply_lt_results([_make_match(6, 4)])
        assert view.extraSelections()

        view._apply_lt_results([])
        assert view.extraSelections() == []

    def test_clear_spell_check_resets_state(self, editor: WikiTextEdit) -> None:
        view = editor.editor
        view.setPlainText("Hello wrld!")
        view._apply_lt_results([_make_match(6, 4)])
        assert view._lt_matches
        assert view.extraSelections()

        view.clear_spell_check()
        assert view._lt_matches == []
        assert view.extraSelections() == []


class TestIgnoreAndApply:
    """Tests for the suggestion-apply and ignore-match code paths."""

    def test_apply_suggestion_replaces_span(self, editor: WikiTextEdit) -> None:
        view = editor.editor
        view.setPlainText("Hello wrld!")
        match = _make_match(6, 4, replacements=["world"])
        view._lt_matches = [match]

        view._apply_lt_suggestion("world", match)

        assert view.toPlainText() == "Hello world!"
        # After applying, the match should be removed from the active list.
        assert match not in view._lt_matches

    def test_ignore_match_removes_only_that_match(
        self, editor: WikiTextEdit
    ) -> None:
        view = editor.editor
        view.setPlainText("Hello wrld and tset!")
        m1 = _make_match(6, 4, rule_id="R1")
        m2 = _make_match(15, 4, rule_id="R2")
        view._apply_lt_results([m1, m2])

        view._ignore_lt_match(m1)

        assert view._lt_matches == [m2]
        remaining = view.extraSelections()
        assert len(remaining) == 1
        assert remaining[0].cursor.selectedText() == "tset"


class TestContextMenu:
    """Tests for right-click handling over a spell-check match."""

    def _menu_for_offset(
        self, editor: WikiTextEdit, offset: int, monkeypatch: pytest.MonkeyPatch
    ):
        """Invoke ``contextMenuEvent`` at ``offset`` and capture the shown menu."""
        view = editor.editor
        shown = {}

        def fake_exec(self_menu, _global_pos):
            shown["menu"] = self_menu
            shown["actions"] = [a.text() for a in self_menu.actions()]
            return None

        from PySide6.QtWidgets import QMenu

        monkeypatch.setattr(QMenu, "exec", fake_exec)

        # Convert an offset to a viewport point using the cursor rect.
        cursor = view.textCursor()
        cursor.setPosition(offset)
        rect = view.cursorRect(cursor)
        pos = rect.center()

        event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, pos, view.mapToGlobal(pos))
        view.contextMenuEvent(event)
        return shown

    def test_click_inside_match_shows_suggestions(
        self, editor: WikiTextEdit, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        view = editor.editor
        view.setPlainText("Hello wrld!")
        view._apply_lt_results(
            [_make_match(6, 4, replacements=["world", "word", "warld"], rule_id="SPELL")]
        )

        shown = self._menu_for_offset(editor, offset=7, monkeypatch=monkeypatch)

        actions = shown["actions"]
        assert "world" in actions
        assert "word" in actions
        assert any(a.startswith("Ignore") and "SPELL" in a for a in actions)

    def test_click_outside_match_shows_standard_menu_only(
        self, editor: WikiTextEdit, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        view = editor.editor
        view.setPlainText("Hello wrld!")
        view._apply_lt_results([_make_match(6, 4, replacements=["world"])])

        shown = self._menu_for_offset(editor, offset=0, monkeypatch=monkeypatch)

        # Offset 0 is the 'H' of "Hello" — outside the [6,10) match span.
        assert "world" not in shown["actions"]

    def test_match_without_replacements_still_offers_ignore(
        self, editor: WikiTextEdit, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        view = editor.editor
        view.setPlainText("Hello wrld!")
        view._apply_lt_results([_make_match(6, 4, replacements=[], rule_id="NOFIX")])

        shown = self._menu_for_offset(editor, offset=7, monkeypatch=monkeypatch)

        assert any("NOFIX" in a for a in shown["actions"])

    def test_suggestions_limited_to_five(
        self, editor: WikiTextEdit, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        view = editor.editor
        view.setPlainText("Hello wrld!")
        ten = [f"fix{i}" for i in range(10)]
        view._apply_lt_results([_make_match(6, 4, replacements=ten)])

        shown = self._menu_for_offset(editor, offset=7, monkeypatch=monkeypatch)

        shown_fixes = [a for a in shown["actions"] if a.startswith("fix")]
        assert len(shown_fixes) == 5
        assert shown_fixes == ten[:5]


class TestLifecycle:
    """Tests for thread startup and clean shutdown."""

    def test_worker_thread_running_after_setup(self, editor: WikiTextEdit) -> None:
        assert editor.editor._lt_thread.isRunning()

    def test_shutdown_stops_worker_thread(self, editor: WikiTextEdit) -> None:
        view = editor.editor
        assert view._lt_thread.isRunning()
        view._shutdown_spell_check()
        assert not view._lt_thread.isRunning()

    def test_shutdown_is_idempotent(self, editor: WikiTextEdit) -> None:
        view = editor.editor
        view._shutdown_spell_check()
        # Second call must not raise.
        view._shutdown_spell_check()
