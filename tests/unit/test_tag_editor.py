"""Tests for the model/view inspector tag editor."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QStyleOptionViewItem

from src.core.theme_manager import ThemeManager
from src.gui.widgets.tag_chip_view import TagChipDelegate
from src.gui.widgets.tag_editor import TagEditorWidget


@pytest.fixture
def tag_editor(qtbot):
    widget = TagEditorWidget()
    widget.resize(520, 220)
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(10)
    return widget


def test_initial_state_is_compact(tag_editor):
    assert tag_editor.get_tags() == []
    assert tag_editor._model.rowCount() == 0
    assert tag_editor.tag_view.isHidden()
    assert not tag_editor.btn_add.isEnabled()


def test_controls_stay_grouped_at_top(tag_editor, qtbot):
    tag_editor.resize(520, 700)
    tag_editor.load_tags(["top-aligned"])
    qtbot.waitUntil(lambda: not tag_editor.tag_view.isHidden())

    assert tag_editor.tag_input.geometry().top() < 30
    assert tag_editor.tag_view.geometry().top() < 80
    assert tag_editor.tag_view.geometry().top() > tag_editor.tag_input.geometry().top()


def test_add_tag_via_enter_keeps_input_focus(tag_editor, qtbot):
    tag_editor.tag_input.setText("urgent")
    qtbot.keyPress(tag_editor.tag_input, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: not tag_editor.tag_view.isHidden())

    assert tag_editor.get_tags() == ["urgent"]
    assert tag_editor.tag_input.text() == ""
    assert tag_editor.tag_input.hasFocus()
    assert not tag_editor.tag_view.isHidden()


def test_add_button_tracks_valid_input(tag_editor, qtbot):
    tag_editor.tag_input.setText("new-tag")
    assert tag_editor.btn_add.isEnabled()

    qtbot.mouseClick(tag_editor.btn_add, Qt.MouseButton.LeftButton)

    assert tag_editor.get_tags() == ["new-tag"]
    assert not tag_editor.btn_add.isEnabled()


def test_close_affordance_removes_only_clicked_tag(tag_editor, qtbot):
    tag_editor.load_tags(["tag1", "tag2"])
    qtbot.wait(10)
    index = tag_editor._model.index(0, 0)
    option = QStyleOptionViewItem()
    tag_editor.tag_view.initViewItemOption(option)
    option.rect = tag_editor.tag_view.visualRect(index)
    close_pos = tag_editor._delegate.close_rect(option).center()

    qtbot.mouseClick(
        tag_editor.tag_view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=close_pos,
    )

    assert tag_editor.get_tags() == ["tag2"]


def test_delete_key_removes_selected_tag(tag_editor, qtbot):
    tag_editor.load_tags(["tag1", "tag2"])
    tag_editor.tag_view.setCurrentIndex(tag_editor._model.index(1, 0))
    tag_editor.tag_view.setFocus()

    qtbot.keyPress(tag_editor.tag_view, Qt.Key.Key_Delete)

    assert tag_editor.get_tags() == ["tag1"]


def test_disabled_editor_prevents_removal(tag_editor):
    tag_editor.load_tags(["protected"])
    tag_editor.setEnabled(False)

    tag_editor._remove_row(0)

    assert tag_editor.get_tags() == ["protected"]


def test_duplicate_and_empty_tags_are_rejected(tag_editor, qtbot):
    tag_editor.load_tags(["existing"])
    tag_editor.tag_input.setText("existing")
    qtbot.keyPress(tag_editor.tag_input, Qt.Key.Key_Return)
    tag_editor.tag_input.setText("   ")
    qtbot.keyPress(tag_editor.tag_input, Qt.Key.Key_Return)

    assert tag_editor.get_tags() == ["existing"]


def test_tags_are_trimmed_and_case_sensitive(tag_editor, qtbot):
    tag_editor.load_tags(["Important"])
    tag_editor.tag_input.setText("  important  ")
    qtbot.keyPress(tag_editor.tag_input, Qt.Key.Key_Return)

    assert tag_editor.get_tags() == ["Important", "important"]


def test_load_tags_uses_one_reset_and_preserves_order(tag_editor):
    reset_spy = QSignalSpy(tag_editor._model.modelReset)
    tags = ["fantasy", "medieval", "main-plot"]

    tag_editor.load_tags(tags)

    assert reset_spy.count() == 1
    assert tag_editor.get_tags() == tags


def test_load_tags_does_not_emit_user_change(tag_editor):
    changed = MagicMock()
    tag_editor.tags_changed.connect(changed)

    tag_editor.load_tags(["loaded"])

    changed.assert_not_called()


def test_user_add_and_remove_emit_changes(tag_editor, qtbot):
    changed = MagicMock()
    tag_editor.tags_changed.connect(changed)
    tag_editor.tag_input.setText("new")
    qtbot.keyPress(tag_editor.tag_input, Qt.Key.Key_Return)
    tag_editor._remove_row(0)

    assert changed.call_count == 2


def test_completer_is_reused_and_excludes_selected_tags(tag_editor):
    completer = tag_editor.tag_input.completer()
    tag_editor.update_suggestions(["alpha", "beta"])
    tag_editor.load_tags(["alpha"])

    assert tag_editor.tag_input.completer() is completer
    assert tag_editor._completer_model.stringList() == ["beta"]
    assert completer.caseSensitivity() == Qt.CaseSensitivity.CaseInsensitive
    assert completer.filterMode() == Qt.MatchFlag.MatchContains


def test_completion_selection_adds_immediately(tag_editor):
    tag_editor.update_suggestions(["suggested"])

    tag_editor._on_completion_activated("suggested")

    assert tag_editor.get_tags() == ["suggested"]
    assert tag_editor.tag_input.text() == ""


def test_long_tags_are_bounded_and_expose_full_tooltip(tag_editor):
    long_tag = "a very long tag name " * 20
    tag_editor.load_tags([long_tag])
    index = tag_editor._model.index(0, 0)
    option = QStyleOptionViewItem()
    tag_editor.tag_view.initViewItemOption(option)

    assert tag_editor._delegate.sizeHint(option, index).width() == 220
    assert index.data(Qt.ItemDataRole.ToolTipRole) == long_tag


def test_tag_colors_are_stable_and_content_based(tag_editor):
    delegate = tag_editor._delegate
    first = delegate.color_for_tag("deity")

    assert delegate.color_for_tag("deity").name() == first.name()
    assert delegate.color_for_tag("location").name() != first.name()


def test_tag_hash_colors_are_visually_varied(tag_editor):
    colors = {
        tag_editor._delegate.color_for_tag(f"tag-{index}").name()
        for index in range(16)
    }

    assert len(colors) >= 14


def test_chip_view_grows_to_three_rows_then_scrolls(tag_editor, qtbot):
    tag_editor.resize(180, 300)
    tag_editor.load_tags([f"wide-tag-{index}" for index in range(12)])
    qtbot.wait(20)

    expected_max_height = (
        TagChipDelegate.CHIP_HEIGHT * 3
        + tag_editor.tag_view.SPACING * 4
    )
    assert tag_editor.tag_view.height() <= expected_max_height
    assert (
        tag_editor.tag_view.verticalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )


def test_large_load_has_no_per_tag_widgets(tag_editor):
    tags = [f"tag-{index}" for index in range(1000)]

    tag_editor.load_tags(tags)

    assert tag_editor._model.rowCount() == 1000
    assert tag_editor.get_tags() == tags
    assert tag_editor.tag_view.indexWidget(tag_editor._model.index(0, 0)) is None


def test_theme_and_base_color_repaint_without_rebuilding_model(tag_editor):
    tag_editor.load_tags(["themed"])
    reset_spy = QSignalSpy(tag_editor._model.modelReset)
    tag_editor.set_base_color("#123456")
    theme_manager = ThemeManager()
    original_theme = theme_manager.current_theme_name

    try:
        for theme_name in ("dark_mode", "light_mode", "muted_light_mode"):
            theme_manager.set_theme(theme_name)
            assert tag_editor._delegate._theme["text_main"] == (
                theme_manager.get_theme()["text_main"]
            )
    finally:
        theme_manager.set_theme(original_theme)

    assert tag_editor._delegate._accent().name() == "#123456"
    assert reset_spy.count() == 0
