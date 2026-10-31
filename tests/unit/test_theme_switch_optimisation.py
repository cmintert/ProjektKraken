"""Regression boundaries for bounded theme-switch work (KRT-120)."""

from collections import OrderedDict
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtGui import QIcon, QPixmap, QTextCursor
from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.core.theme_manager import ThemeManager
from src.gui.utils import icon_loader
from src.gui.widgets.longform.content import LongformContentWidget
from src.gui.widgets.standard_buttons import LabelSizedToolButton, StandardButton

pytestmark = pytest.mark.ci_fast


@pytest.mark.parametrize("kind", [StandardButton, LabelSizedToolButton])
def test_style_burst_coalesces_geometry_without_stale_hints(qapp, qtbot, kind):
    button = kind()
    qtbot.addWidget(button)
    button.setText("A complete action label")
    qapp.processEvents()
    with patch.object(button, "updateGeometry") as update:
        for _ in range(8):
            button.changeEvent(QEvent(QEvent.Type.StyleChange))
        assert button.sizeHint().width() > 0
        update.assert_not_called()
        qapp.processEvents()
        update.assert_called_once()
    button.deleteLater()
    qapp.processEvents()


def test_svg_cache_reuses_render_and_returns_independent_icons(qapp, tmp_path):
    source = tmp_path / "icon.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<rect width="16" height="16" fill="currentColor"/></svg>',
        encoding="utf-8",
    )
    with patch.object(
        icon_loader, "QSvgRenderer", wraps=icon_loader.QSvgRenderer
    ) as render:
        first = icon_loader.load_icon(str(source), "red")
        second = icon_loader.load_icon(str(source), "red")
        assert render.call_count == 1
        assert not first.isNull()
        first.addPixmap(QPixmap(24, 24), QIcon.Mode.Disabled)
        assert first.cacheKey() != second.cacheKey()
        assert icon_loader.load_icon(str(source), "red").cacheKey() == second.cacheKey()
        icon_loader.load_icon(str(source), "blue")
        assert render.call_count == 2


def test_missing_svg_is_retried_after_creation(qapp, tmp_path):
    source = tmp_path / "later.svg"
    assert icon_loader.load_icon(str(source)).isNull()
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<circle cx="8" cy="8" r="6"/></svg>',
        encoding="utf-8",
    )
    assert not icon_loader.load_icon(str(source)).isNull()


def test_svg_cache_is_bounded(qapp, tmp_path, monkeypatch):
    source = tmp_path / "bounded.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<circle cx="8" cy="8" r="6" fill="currentColor"/></svg>',
        encoding="utf-8",
    )
    monkeypatch.setattr(icon_loader, "_ICON_CACHE_LIMIT", 2)
    monkeypatch.setattr(icon_loader, "_icon_cache", OrderedDict())
    for color in ("red", "blue", "green"):
        icon_loader.load_icon(str(source), color)
    assert len(icon_loader._icon_cache) == 2
    with patch.object(
        icon_loader, "QSvgRenderer", wraps=icon_loader.QSvgRenderer
    ) as render:
        icon_loader.load_icon(str(source), "red")
        render.assert_called_once()


def test_longform_theme_uses_cached_body_and_retains_selection(
    qapp, qtbot, theme_delivery
):
    widget = LongformContentWidget()
    qtbot.addWidget(widget)
    widget.resize(500, 300)
    widget.show()
    sequence = [
        {
            "id": "chapter",
            "table": "events",
            "name": "Chapter",
            "heading_level": 1,
            "meta": {},
            "content": "A **passage**.\n\n" * 80,
        }
    ]
    widget.load_content(sequence)
    qapp.processEvents()
    cursor = widget.textCursor()
    cursor.setPosition(10)
    cursor.setPosition(20, QTextCursor.MoveMode.KeepAnchor)
    widget.setTextCursor(cursor)
    widget.verticalScrollBar().setValue(150)
    selection = cursor.selectedText()
    with patch.object(
        widget, "_render_markdown_fragment", wraps=widget._render_markdown_fragment
    ) as render:
        for name in ("light_mode", "dark_mode"):
            ThemeManager().set_theme(name, persist=False)
            qapp.processEvents()
        render.assert_not_called()
        assert widget.textCursor().selectedText() == selection
        assert widget.verticalScrollBar().value() == 150
        sequence[0]["content"] = "Updated passage"
        widget.load_content(sequence)
        render.assert_called_once()
    assert "Updated passage" in widget.toPlainText()


def test_inspector_focus_rules_are_not_added_to_actions(qapp, qtbot):
    from src.gui.utils.style_helper import StyleHelper
    from src.gui.widgets.entity_editor import EntityEditorWidget

    editor = EntityEditorWidget()
    qtbot.addWidget(editor)
    assert StyleHelper.get_inspector_focus_style() not in editor.btn_inject.styleSheet()
    assert StyleHelper.get_inspector_focus_style() in editor.name_edit.styleSheet()


@pytest.mark.parametrize("kind", ["entity", "event"])
@pytest.mark.parametrize("mode", ["rich", "source"])
def test_six_theme_switches_preserve_authoring_state(
    qapp, qtbot, kind, mode, theme_delivery
):
    from src.core.entities import Entity
    from src.core.events import Event
    from src.gui.widgets.entity_editor import EntityEditorWidget
    from src.gui.widgets.event_editor import EventEditorWidget

    parent = QWidget()
    parent.worker = MagicMock()
    qtbot.addWidget(parent)
    editor = (
        EntityEditorWidget(parent) if kind == "entity" else EventEditorWidget(parent)
    )
    QVBoxLayout(parent).addWidget(editor)
    if kind == "entity":
        editor.load_entity(Entity(id="draft", name="Draft", type="person"))
    else:
        editor.load_event(Event(id="draft", name="Draft", lore_date=0.0))
    editor.resize(960, 720)
    parent.resize(960, 720)
    parent.show()
    editor.show()
    parent.activateWindow()
    editor.name_edit.setText("Unfinished draft")
    editor.desc_edit.set_wiki_text("A **draft** with [[Somewhere]].\n\nAnother line.")
    view = editor.desc_edit.editor
    if mode == "source":
        view.toggle_view_mode()
    cursor = view.textCursor()
    cursor.setPosition(3)
    cursor.setPosition(8, QTextCursor.MoveMode.KeepAnchor)
    view.setTextCursor(cursor)
    editor.autosave_manager.stop_timer()
    qapp.processEvents()
    view.setFocus()
    qapp.processEvents()
    assert qapp.focusWidget() in (view, view.viewport())
    document = view.document()
    before = (
        editor.desc_edit.get_wiki_text(),
        document.toPlainText(),
        cursor.position(),
        cursor.anchor(),
        document.availableUndoSteps(),
        document.availableRedoSteps(),
        editor.has_unsaved_changes(),
    )
    for name in ThemeManager().themes:
        ThemeManager().set_theme(name, persist=False)
        qapp.processEvents()
        cursor = view.textCursor()
        assert view.document() is document
        assert (
            editor.desc_edit.get_wiki_text(),
            document.toPlainText(),
            cursor.position(),
            cursor.anchor(),
            document.availableUndoSteps(),
            document.availableRedoSteps(),
            editor.has_unsaved_changes(),
        ) == before
        assert qapp.focusWidget() in (view, view.viewport())
    editor.set_dirty(False)
    editor.autosave_manager.stop_timer()


def test_timeline_theme_switch_preserves_playhead_and_selection(
    qapp, qtbot, theme_delivery
):
    from src.core.events import Event
    from src.gui.widgets.timeline import TimelineWidget

    timeline = TimelineWidget()
    qtbot.addWidget(timeline)
    timeline.set_events([Event(id="event", name="An event", lore_date=12.0)])
    timeline.view.set_playhead_time(7.0)
    for name in ThemeManager().themes:
        ThemeManager().set_theme(name, persist=False)
        qapp.processEvents()
        assert timeline.view._playhead._time == 7.0
