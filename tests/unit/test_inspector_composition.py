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
from src.core.theme_manager import ThemeManager
from src.gui.widgets.editor_presentation import SupportingSectionHeader
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
    assert editor.summary_checkbox.text() == "Summary…"
    assert not editor._presentation.summary_availability.isHidden()
    editor.inspector.open_auxiliary_below("world_context")
    editor.inspector.reset_layout()
    assert not editor._presentation.summary_availability.isHidden()
    editor.summary_widget.clear_summary()
    assert editor.summary_checkbox.text() == "Summary…"
    assert editor._presentation.summary_availability.isHidden()
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


def test_supporting_tools_are_contextual_and_start_closed(editor):
    presentation = editor._presentation
    row, _role = editor.form_layout.getWidgetPosition(editor.description_field)
    tools_row, _role = editor.form_layout.getWidgetPosition(
        presentation.writing_actions
    )
    assert tools_row == row + 1
    assert editor.summary_checkbox.text() == "Summary…"
    assert editor.llm_checkbox.text() == "Draft with AI…"
    assert presentation.writing_actions.isAncestorOf(editor.summary_checkbox)
    assert presentation.writing_actions.isAncestorOf(editor.llm_checkbox)
    assert editor.summary_container.isHidden()
    assert editor.llm_container.isHidden()
    assert isinstance(presentation.history_disclosure, SupportingSectionHeader)
    assert presentation.history_disclosure.accessibleName() == "History & context"
    assert not presentation.history_disclosure.isChecked()
    assert presentation.composition.history_body.isHidden()
    assert not editor.raster_appearances_checkbox.isVisibleTo(editor)
    if isinstance(editor, EntityEditorWidget):
        assert not editor.timeline_checkbox.isVisibleTo(editor)
    else:
        assert all(
            getattr(label, "text", lambda: "")() != "Linked events"
            for label in presentation.composition.history_body.findChildren(QWidget)
        )
    assert not editor.has_unsaved_changes()


def test_opening_supporting_tools_never_generates_or_mutates(editor, qtbot):
    summary_requests = []
    generated_text = []
    saves = []
    editor.summary_generation_requested.connect(summary_requests.append)
    editor.llm_generator.text_generated.connect(generated_text.append)
    editor.save_requested.connect(saves.append)
    text = editor.desc_edit.get_wiki_text()
    for button in (
        editor.summary_checkbox,
        editor.llm_checkbox,
        editor._presentation.history_disclosure,
    ):
        button.setFocus()
        qtbot.keyClick(button, Qt.Key.Key_Space)
        assert button.isChecked()
    assert editor.summary_container.isVisibleTo(editor)
    assert editor.llm_container.isVisibleTo(editor)
    assert editor._presentation.composition.history_body.isVisibleTo(editor)
    assert editor.desc_edit.get_wiki_text() == text
    assert not summary_requests and not generated_text and not saves
    assert not editor.has_unsaved_changes()


def test_concurrent_summary_edit_and_generation_inputs_survive_toggle(editor):
    summary = editor.summary_widget
    summary.set_summary(
        SummaryData(text="Old summary", hash="source", timestamp=0, model="test")
    )
    editor.summary_checkbox.click()
    editor.llm_checkbox.click()
    summary._begin_edit()
    inner = summary.text_display.editor
    inner.moveCursor(QTextCursor.MoveOperation.End)
    inner.insertPlainText(" unsaved")
    cursor = inner.textCursor()
    cursor.setPosition(3)
    cursor.setPosition(8, QTextCursor.MoveMode.KeepAnchor)
    inner.setTextCursor(cursor)
    document = inner.document()
    generator = editor.llm_generator
    generator.custom_prompt_edit.setPlainText("Keep the shoreline unchanged")
    prompt_document = generator.custom_prompt_edit.editor.document()
    generator.temperature_spin.setValue(33)
    generator.max_tokens_spin.setValue(1024)
    generator.rag_cb.setChecked(False)
    committed = []
    summary.edit_committed.connect(committed.append)
    editor.summary_checkbox.click()
    assert editor.llm_container.isVisibleTo(editor)
    editor.summary_checkbox.click()
    editor.llm_checkbox.click()
    assert editor.summary_container.isVisibleTo(editor)
    editor.llm_checkbox.click()
    editor.inspector.open_auxiliary_below("world_context")
    editor.inspector.reset_layout()
    assert summary.text_display.get_wiki_text().endswith(" unsaved")
    assert not summary.text_display.isReadOnly()
    assert inner.document() is document
    assert (inner.textCursor().anchor(), inner.textCursor().position()) == (3, 8)
    assert inner.document().isUndoAvailable()
    assert generator.custom_prompt_edit.editor.document() is prompt_document
    assert generator.custom_prompt_edit.toPlainText() == "Keep the shoreline unchanged"
    assert generator.temperature_spin.value() == 33
    assert generator.max_tokens_spin.value() == 1024
    assert not generator.rag_cb.isChecked()
    assert editor.summary_checkbox.isChecked() and editor.llm_checkbox.isChecked()
    assert not committed


def test_same_object_refresh_and_reset_keep_supporting_choices(editor):
    editor.summary_checkbox.setChecked(True)
    editor.llm_checkbox.setChecked(True)
    editor._presentation.history_disclosure.setChecked(True)
    if isinstance(editor, EntityEditorWidget):
        editor.load_entity(Entity(id="person", name="Ada", type="Character"))
    else:
        editor.load_event(Event(id="event", name="Arrival", lore_date=0))
    editor.inspector.open_auxiliary_below("world_context")
    editor.inspector.open_auxiliary_below("sheet")
    editor.inspector.reset_layout()
    assert editor.summary_checkbox.isChecked()
    assert editor.llm_checkbox.isChecked()
    assert editor._presentation.history_disclosure.isChecked()
    assert not editor.has_unsaved_changes()


@pytest.mark.parametrize("editor", ["entity"], indirect=True)
def test_linked_events_fit_the_existing_document_without_nested_scroll(editor, qtbot):
    assert isinstance(editor, EntityEditorWidget)
    view = editor.timeline_display._text_display
    document = view.document()
    editor.timeline_display.set_relations(
        [
            {
                "id": str(i),
                "source_id": f"event-{i}",
                "source_event_date": float(i),
                "source_event_name": "A council meeting with a long name",
                "attributes": {"payload": {"rank": "Master"}},
            }
            for i in range(6)
        ]
    )
    editor.resize(331, 720)
    editor._presentation.history_disclosure.setChecked(True)
    qtbot.waitUntil(lambda: editor.scroll_area.verticalScrollBar().maximum() > 0)
    qtbot.waitUntil(lambda: view.verticalScrollBar().maximum() == 0)
    assert view.document() is document
    assert view.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert view.height() >= view.document().size().height()
    assert editor.scroll_area.verticalScrollBar().maximum() > 0
    assert not editor.has_unsaved_changes()


def test_writing_tool_toggles_preserve_prose_selection_scroll_and_undo(editor, qtbot):
    text = editor.desc_edit.editor
    text.setPlainText("\n".join(f"Paragraph {i}" for i in range(100)))
    text.moveCursor(QTextCursor.MoveOperation.End)
    text.insertPlainText(" newer draft")
    cursor = text.textCursor()
    cursor.setPosition(10)
    cursor.setPosition(25, QTextCursor.MoveMode.KeepAnchor)
    text.setTextCursor(cursor)
    scroll = text.verticalScrollBar()
    scroll.setValue(scroll.maximum() // 2)
    position = scroll.value()
    document = text.document()
    for button in (
        editor.summary_checkbox,
        editor.llm_checkbox,
        editor._presentation.history_disclosure,
    ):
        button.setFocus()
        qtbot.keyClick(button, Qt.Key.Key_Space)
        qtbot.keyClick(button, Qt.Key.Key_Space)
    assert text.document() is document
    assert (text.textCursor().anchor(), text.textCursor().position()) == (10, 25)
    assert scroll.value() == position
    text.undo()
    assert not text.toPlainText().endswith(" newer draft")
    assert editor.has_unsaved_changes()


def test_quiet_support_styles_survive_theme_changes(editor, qapp):
    manager = ThemeManager()
    for theme in ("light_mode", "dark_mode"):
        manager.set_theme(theme, qapp)
        for button in (editor.summary_checkbox, editor.llm_checkbox):
            assert button.icon().isNull()
            assert manager.get_theme()["accent_secondary"] in button.styleSheet()
        assert manager.get_theme()["text_dim"] in (
            editor._presentation.composition.history_container.styleSheet()
        )


def test_summary_action_retains_generation_and_staged_edit_signals(editor, qtbot):
    editor.summary_checkbox.click()
    with qtbot.waitSignal(editor.summary_generation_requested) as request:
        editor.summary_widget.generate_btn.click()
    assert request.args[0].id == editor._get_current_item_id()
    assert not editor.has_unsaved_changes()
    editor.summary_widget.set_summary(
        SummaryData(text="Original summary", hash="source", timestamp=0, model="test")
    )
    editor.summary_widget.edit_btn.click()
    editor.summary_widget.text_display.editor.moveCursor(QTextCursor.MoveOperation.End)
    editor.summary_widget.text_display.editor.insertPlainText(" refined")
    with qtbot.waitSignal(editor.summary_widget.edit_committed) as commit:
        editor.summary_widget.done_btn.click()
    assert commit.args == ["Original summary refined"]
    assert editor.has_unsaved_changes()
    assert not editor._presentation.summary_availability.isHidden()
