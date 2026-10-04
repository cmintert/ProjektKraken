"""Canonical routes and live-state preservation for the four-page inspector."""

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt, QUrl
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QListWidgetItem, QWidget

from src.core.authoring_context import (
    ContextItem,
    EntityAuthoringContext,
    EventAuthoringContext,
)
from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.entities import Entity
from src.core.events import Event
from src.core.summary_data import SummaryData
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.splitter_tab_inspector import DraggableTabWidget, _move_tab

pytestmark = pytest.mark.ci_fast


@pytest.fixture(params=["entity", "event"])
def editor(request, qtbot):
    parent = QWidget()
    parent.worker = MagicMock()
    qtbot.addWidget(parent)
    if request.param == "entity":
        widget = EntityEditorWidget(parent)
        widget.load_entity(
            Entity(
                id="person",
                name="Ada",
                type="Character",
                description="Old harbor",
                attributes={"rank": "Scholar"},
            )
        )
    else:
        widget = EventEditorWidget(parent)
        widget.set_calendar_converter(
            CalendarConverter(CalendarConfig.create_default())
        )
        widget.load_event(
            Event(
                id="event",
                name="Arrival",
                lore_date=0.0,
                description="Old harbor",
                attributes={"rank": "Scholar"},
            )
        )
    qtbot.addWidget(widget)
    widget.resize(871, 720)
    widget.setWindowFlag(Qt.WindowType.Window, True)
    widget.show()
    return widget


def test_canonical_destinations_and_details_are_live_views(editor):
    inspector = editor.inspector
    tabs = inspector.main_tabs
    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        "Overview",
        "Connections",
        "Details",
        "Media",
    ]
    composition = editor._presentation.composition
    assert composition.details_views.currentIndex() == 0
    assert composition.details.isAncestorOf(editor.tag_editor)
    assert composition.details_views.widget(0).isAncestorOf(editor.attribute_editor)
    assert composition.sheet_home.content.isAncestorOf(editor.sheet_builder)
    for key, section in zip(
        ("overview", "connections", "details", "media"),
        (
            editor.tab_details,
            editor.tab_relations,
            composition.details,
            editor.tab_gallery,
        ),
        strict=True,
    ):
        inspector.activate_section_id(key)
        assert tabs.currentWidget() is section
        assert section.isVisible()
        assert all(
            tabs.widget(i).isHidden()
            for i in range(tabs.count())
            if tabs.widget(i) is not section
        )
    assert not editor.has_unsaved_changes()


@pytest.mark.parametrize("section_id", ["world_context", "sheet"])
def test_auxiliary_split_return_and_reset_preserve_live_content(editor, section_id):
    inspector = editor.inspector
    composition = editor._presentation.composition
    home = (
        composition.context_home
        if section_id == "world_context"
        else composition.sheet_home
    )
    content = home.content
    document = editor.desc_edit.editor.document()
    editor.desc_edit.editor.moveCursor(QTextCursor.MoveOperation.End)
    editor.desc_edit.editor.insertPlainText(" rebuilt")
    cursor = editor.desc_edit.editor.textCursor()
    selection = (cursor.anchor(), cursor.position())
    views = composition.details_views
    views.setCurrentIndex(1)
    inspector.activate_section_id(section_id)
    inspector.open_auxiliary_below(section_id)
    assert home.detached
    assert home.placeholder.isVisibleTo(home)
    assert home.pane.isAncestorOf(content)
    assert inspector.splitter.count() == 2
    inspector.open_auxiliary_below(section_id)
    assert inspector.splitter.count() == 2
    assert inspector._pane_for(home.pane).currentWidget() is home.pane
    inspector.return_auxiliary(section_id)
    assert not home.detached
    assert content.parentWidget() is home
    assert inspector.splitter.count() == 1
    assert views.currentIndex() == 1
    inspector.open_auxiliary_below(section_id)
    inspector.reset_layout()
    assert not home.detached
    assert tabs_count(inspector) == 4
    assert views.currentIndex() == 1
    assert editor.desc_edit.editor.document() is document
    assert editor.desc_edit.get_wiki_text().endswith(" rebuilt")
    cursor = editor.desc_edit.editor.textCursor()
    assert (cursor.anchor(), cursor.position()) == selection
    assert editor.has_unsaved_changes()
    assert document.isUndoAvailable()


def tabs_count(inspector):
    return sum(pane.count() for pane in inspector.findChildren(DraggableTabWidget))


def test_more_menu_has_visible_layout_and_support_routes(editor):
    tabs = editor.inspector.main_tabs
    assert tabs.overflow_button.isVisible()
    assert tabs.overflow_button.text() == "More"
    assert tabs.overflow_button.geometry().left() >= 0
    assert tabs.overflow_button.geometry().right() <= tabs.rect().right()
    tabs._populate_overflow()
    actions = {action.text(): action for action in tabs.overflow_menu.actions()}
    assert {
        "Overview",
        "Connections",
        "Details",
        "Media",
        "Split active section below",
        "Open World context below",
        "Open Sheet below",
        "Reset inspector layout",
    } <= actions.keys()
    actions["Open World context below"].trigger()
    assert editor._presentation.composition.context_home.detached
    assert not editor.authoring_context._embedded
    tabs._populate_overflow()
    next(
        action
        for action in tabs.overflow_menu.actions()
        if action.text() == "Return World context here"
    ).trigger()
    assert editor.authoring_context._embedded
    assert editor.authoring_context.scroll_area.isHidden()
    assert editor._presentation.context_disclosure.isChecked()
    assert not editor.has_unsaved_changes()


def test_split_content_can_be_dragged_and_returned_to_its_home(editor):
    inspector = editor.inspector
    inspector.open_auxiliary_below("sheet")
    home = editor._presentation.composition.sheet_home
    source = inspector._pane_for(home.pane)
    target = inspector.main_tabs
    assert _move_tab(source, target, 0, 0)
    inspector.return_auxiliary("sheet")
    assert home.content.parentWidget() is home
    assert target.count() == 4
    assert inspector.splitter.count() == 1
    inspector.reset_layout()
    assert not editor.has_unsaved_changes()


@pytest.mark.parametrize("partial_insert", [False, True])
def test_failed_auxiliary_split_restores_original_home(
    editor, monkeypatch, partial_insert
):
    inspector = editor.inspector
    home = editor._presentation.composition.context_home
    insert = DraggableTabWidget.addTab

    def fail(target, *args):
        if partial_insert:
            insert(target, *args)
        raise RuntimeError("Rejected pane insertion")

    monkeypatch.setattr(DraggableTabWidget, "addTab", fail)
    inspector.open_auxiliary_below("world_context")
    assert not home.detached
    assert home.content.parentWidget() is home
    assert home.pane.parentWidget() is home
    assert inspector.splitter.count() == 1
    assert inspector.main_tabs.count() == 4
    assert editor.authoring_context._embedded
    assert not editor.has_unsaved_changes()


def test_same_object_and_new_object_keep_destination_and_details_view(editor):
    inspector = editor.inspector
    inspector.activate_section_id("details")
    editor._presentation.composition.details_views.setCurrentIndex(1)
    inspector.open_auxiliary_below("world_context")
    editor._presentation.context_disclosure.setChecked(True)
    for item_id in (editor._get_current_item_id(), "next"):
        if isinstance(editor, EntityEditorWidget):
            editor.load_entity(
                Entity(
                    id=item_id,
                    name="Next",
                    type="Character",
                    attributes={"rank": "Scholar"},
                )
            )
        else:
            editor.load_event(
                Event(
                    id=item_id,
                    name="Next",
                    lore_date=0.0,
                    attributes={"rank": "Scholar"},
                )
            )
        assert (
            inspector.main_tabs.currentWidget()
            is editor._presentation.composition.details
        )
        assert editor._presentation.composition.details_views.currentIndex() == 1
        assert editor._presentation.composition.context_home.detached
        assert editor._presentation.context_disclosure.isChecked()
        assert not editor.has_unsaved_changes()


def test_partial_content_relocation_returns_widget_home(editor, monkeypatch):
    home = editor._presentation.composition.context_home
    insert = home._pane_layout.addWidget

    def fail(*args):
        insert(*args)
        raise RuntimeError("Content relocation failed after insertion")

    monkeypatch.setattr(home._pane_layout, "addWidget", fail)
    editor.inspector.open_auxiliary_below("world_context")
    assert not home.detached
    assert home.content.parentWidget() is home
    assert home._layout.indexOf(home.content) == 0
    assert home.placeholder.isHidden()
    assert editor.authoring_context._embedded
    assert editor.inspector.splitter.count() == 1
    assert not editor.has_unsaved_changes()


def test_context_navigation_retains_original_signals_and_renderer(editor, qtbot):
    renderer = editor.authoring_context
    if isinstance(editor, EntityEditorWidget):
        renderer.set_entity_context(EntityAuthoringContext(entity_id="person"))
    else:
        renderer.set_context(
            EventAuthoringContext(
                event_id="event",
                context_date=0.0,
                participants=(ContextItem("person", "entity", "Ada"),),
            )
        )
    html = renderer.primary_view.toHtml()
    editor.inspector.open_auxiliary_below("world_context")
    with qtbot.waitSignal(editor.navigate_to_relation) as signal:
        renderer.primary_view.anchorClicked.emit(QUrl("kraken://person"))
    assert signal.args == ["person"]
    editor.inspector.return_auxiliary("world_context")
    assert renderer.primary_view.toHtml() == html
    assert not editor.has_unsaved_changes()


def test_same_context_refresh_preserves_nested_disclosure(editor):
    renderer = editor.authoring_context
    if isinstance(editor, EntityEditorWidget):
        context = EntityAuthoringContext(
            entity_id="person", omitted_counts=(("relations", 3),)
        )
        present = renderer.set_entity_context
        other = replace(context, entity_id="next")
    else:
        context = EventAuthoringContext(
            event_id="event", context_date=0, omitted_counts=(("relations", 3),)
        )
        present = renderer.set_context
        other = replace(context, event_id="next")
    present(context)
    editor.inspector.activate_section_id("world_context")
    renderer.more_button.setChecked(True)
    renderer.set_loading()
    present(context)
    assert renderer.more_button.isChecked()
    assert not renderer.more_view.isHidden()
    editor.inspector.open_auxiliary_below("world_context")
    editor.inspector.return_auxiliary("world_context")
    assert renderer.more_button.isChecked()
    present(other)
    assert not renderer.more_button.isChecked()
    assert not editor.has_unsaved_changes()


def test_tags_and_sheet_edits_remain_dirty_through_view_changes(editor, qtbot):
    editor.inspector.activate_section_id("details")
    qtbot.keyClicks(editor.tag_editor.tag_input, "historical")
    qtbot.keyClick(editor.tag_editor.tag_input, Qt.Key.Key_Return)
    assert editor.tag_editor.get_tags() == ["historical"]
    editor.sheet_builder._pairs["rank"].value_edit.setPlainText("Master")
    editor.inspector.open_auxiliary_below("sheet")
    editor.inspector.return_auxiliary("sheet")
    editor._presentation.composition.details_views.setCurrentIndex(0)
    assert editor.attribute_editor.get_attributes()["rank"] == "Master"
    assert editor.sheet_builder.get_attributes()["rank"] == "Master"
    assert editor.has_unsaved_changes()


@pytest.mark.parametrize("editor", ["entity"], indirect=True)
def test_media_attachment_navigation_follows_dragged_destination(editor):
    assert isinstance(editor, EntityEditorWidget)
    inspector = editor.inspector
    inspector.activate_section_id("media")
    inspector.split_active_section()
    item = QListWidgetItem("Caption")
    item.setData(Qt.ItemDataRole.UserRole, "attachment")
    editor.gallery.list_widget.addItem(item)
    inspector.activate_section_id("overview")
    editor._show_context_attachment("attachment")
    assert inspector._pane_for(editor.tab_gallery).currentWidget() is editor.tab_gallery
    assert editor.gallery.list_widget.currentItem() is item
    assert not editor.has_unsaved_changes()


@pytest.mark.parametrize("editor", ["event"], indirect=True)
def test_invalid_date_and_newer_prose_survive_section_navigation(editor, qtbot):
    assert isinstance(editor, EventEditorWidget)
    field = editor.date_edit.txt_date
    field.setFocus()
    field.selectAll()
    qtbot.keyClicks(field, "not a date")
    qtbot.keyClick(field, Qt.Key.Key_Return)
    editor.desc_edit.editor.moveCursor(QTextCursor.MoveOperation.End)
    editor.desc_edit.editor.insertPlainText(" again")
    editor.inspector.activate_section_id("details")
    editor.inspector.open_auxiliary_below("sheet")
    editor.inspector.reset_layout()
    assert field.text() == "not a date"
    assert editor.temporal_widget.has_pending_draft()
    assert editor.desc_edit.get_wiki_text().endswith(" again")
    assert not editor.btn_save.isEnabled()
    assert not editor.autosave_manager._autosave_timer.isActive()
    qtbot.keyClick(field, Qt.Key.Key_Escape)
    assert editor.has_unsaved_changes()


@pytest.mark.parametrize("editor", ["event"], indirect=True)
def test_local_pane_width_reflows_date_without_changing_semantics(editor, qtbot):
    assert isinstance(editor, EventEditorWidget)
    field = editor.date_edit
    field.txt_date.setText("c. 1218")
    field._on_draft_edited("c. 1218")
    assert field.commit_draft()
    expression = field.get_expression().to_dict()
    field.date_fields_button.setChecked(True)
    field.resize(300, field.height())
    qtbot.waitUntil(lambda: field._structured_compact)
    grid = field._structured_grid
    assert [
        grid.getItemPosition(grid.indexOf(control))[0]
        for control in (field.spin_year, field.combo_month, field.combo_day)
    ] == [1, 3, 5]
    field.resize(700, field.height())
    assert not field._structured_compact
    assert field.get_expression().to_dict() == expression
    assert "uncertainty" in field.date_fields_button.text()


def test_auxiliary_reset_does_not_leave_deferred_deletion_with_content(editor, qtbot):
    inspector = editor.inspector
    inspector.open_auxiliary_below("world_context")
    inspector.open_auxiliary_below("sheet")
    source = inspector._pane_for(editor._presentation.composition.sheet_home.pane)
    assert _move_tab(source, inspector.main_tabs, 0, 0)
    source._cleanup_empty_pane(source, inspector.splitter)
    inspector.reset_layout()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qtbot.wait(250)
    inspector.open_auxiliary_below("sheet")
    inspector.return_auxiliary("sheet")
    assert editor.sheet_builder.get_attributes()["rank"] == "Scholar"
    assert not editor.has_unsaved_changes()


def test_selection_scroll_and_undo_survive_navigation_and_resize(editor, qtbot):
    text = editor.desc_edit.editor
    text.setPlainText("\n".join(f"Paragraph {i}" for i in range(100)))
    text.moveCursor(QTextCursor.MoveOperation.End)
    text.insertPlainText(" newer draft")
    cursor = text.textCursor()
    cursor.setPosition(10)
    cursor.setPosition(25, QTextCursor.MoveMode.KeepAnchor)
    text.setTextCursor(cursor)
    document = text.document()
    scroll = text.verticalScrollBar()
    scroll.setValue(scroll.maximum() // 2)
    position = scroll.value()
    editor.inspector.activate_section_id("details")
    editor.inspector.open_auxiliary_below("sheet")
    editor.inspector.reset_layout()
    editor.resize(331, 720)
    editor.resize(871, 720)
    qtbot.wait(10)
    assert text.document() is document
    assert (text.textCursor().anchor(), text.textCursor().position()) == (10, 25)
    assert scroll.value() == position
    assert document.isUndoAvailable()
    text.undo()
    assert not text.toPlainText().endswith(" newer draft")
    assert editor.has_unsaved_changes()


def test_collapsed_summary_indicates_retained_content(editor):
    editor.summary_widget.set_summary(
        SummaryData(text="Saved summary", hash="source", timestamp=0, model="test")
    )
    assert not editor.summary_checkbox.isChecked()
    assert editor.summary_checkbox.text() == "Summary (available)"
    editor.inspector.open_auxiliary_below("world_context")
    editor.inspector.reset_layout()
    assert editor.summary_checkbox.text() == "Summary (available)"
    editor.summary_widget.clear_summary()
    assert editor.summary_checkbox.text() == "Summary"
    assert not editor.has_unsaved_changes()


def test_narrow_toolbar_menus_reuse_authored_actions(editor, qtbot):
    editor.resize(331, 720)
    writing, sheet = editor._presentation._toolbar_more_buttons
    qtbot.waitUntil(writing.isVisible)
    assert editor.desc_edit.action_toggle_mode in writing.menu().actions()
    editor.inspector.activate_section_id("sheet")
    assert sheet.isVisible()
    assert editor.sheet_builder._act_add_header in sheet.menu().actions()
    sheet.menu().actions()[2].trigger()  # The existing Add Divider action.
    assert any("divider" in str(row) for row in editor.sheet_builder.get_layout())
    assert editor.has_unsaved_changes()
