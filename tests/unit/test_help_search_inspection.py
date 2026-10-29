"""Offline query relevance, native control inspection and authoring isolation."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtGui import QCursor, QHelpEvent, QWhatsThisClickedEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QWhatsThis

from src.app.help_control_bindings import CONTROL_TOPICS, HelpControlBindings
from src.core.help_bundle import HelpSearchDocument
from src.services.help_bundle_service import HelpBundleService
from src.services.help_search_service import HelpSearchService
from tests.unit import test_entity_editor as entity_tests
from tests.unit import test_help_coordinator as coordinator_tests

generated_root = coordinator_tests.generated_root
help_setup = coordinator_tests.help_setup
standard_calendar = coordinator_tests.standard_calendar
editor = entity_tests.editor
focus_setup = coordinator_tests.focus_setup
pytestmark = pytest.mark.ci_fast


def test_search_normalization_prefix_deduplication_and_snippets():
    document = HelpSearchDocument(
        "calendar.html",
        "months",
        "Calendar ÉTÉ",
        "Year uncertainty " * 40,
        ("date.precision",),
    )
    service = HelpSearchService((document, document))
    results = service.search("calendar E\u0301TE\u0301 uncerta 962")
    assert len(results) == 1
    assert results[0].topic_ids == ("date.precision",)
    assert len(results[0].snippet) <= 180
    assert service.search("why does a") == ()
    assert service.search("xyzzy") == ()


@pytest.mark.parametrize(
    "query, topic",
    [
        ("change a border in 962", "map.historical-geometry"),
        ("why does a year have uncertain date", "date.precision"),
        ("find relation validity", "relations.timing"),
        ("visible value source correction", "entity.value-source"),
        ("attributes relations mentions", "authoring.representations"),
        ("Longform recover removed document", "longform.recovery"),
        ("Show dependency trail", "timeline.viewing"),
    ],
)
def test_expert_queries_find_canonical_topics(generated_root, query, topic):
    bundle = HelpBundleService(root=generated_root / "docs/_build/help")
    results = HelpSearchService(bundle.search_documents()).search(query)
    assert any(topic in result.topic_ids for result in results[:5])


def test_dependency_inspection_excerpt_describes_every_mode(generated_root):
    bundle = HelpBundleService(root=generated_root / "docs/_build/help")
    excerpt = bundle.load_inspection_excerpt(
        "timeline.viewing", "help-inspect-timeline-show-dependencies"
    )
    assert excerpt is not None
    for phrase in (
        "All",
        "Selected",
        "Show dependency trail",
        "Off",
        "branches and merges",
        "without a selected Event",
    ):
        assert phrase in excerpt


def test_search_flush_enter_retains_query_and_local_escape(help_setup, qapp):
    coordinator, _, _, _, _ = help_setup
    coordinator.request()
    coordinator.show_search()
    before = len(coordinator.history)
    coordinator.viewer.query.setText("relation validity")
    assert coordinator.search_timer.isActive()
    QTest.keyClick(coordinator.viewer.query, Qt.Key.Key_Return)
    qapp.processEvents()
    assert not coordinator.search_timer.isActive()
    assert len(coordinator.history) == before + 1
    assert coordinator.viewer.query.text() == "relation validity"
    assert "relations.timing" in coordinator.search_results[0].topic_ids
    QTest.keyClick(coordinator.viewer.browser, Qt.Key.Key_Escape)
    assert not coordinator.viewer.search_panel.isVisible()
    assert coordinator.viewer.isVisible()
    QTest.keyClick(
        coordinator.viewer.browser, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier
    )
    assert coordinator.viewer.search_panel.isVisible()
    coordinator.viewer.query.setText("xyzzy")
    coordinator.search()
    assert "No matching" in coordinator.viewer.search_status.text()


def test_debounce_and_query_undo_are_local(help_setup, qtbot):
    coordinator, _, _, _, text = help_setup
    coordinator.show_search()
    QTest.keyClicks(coordinator.viewer.query, "border")
    assert coordinator.search_results == ()
    qtbot.waitUntil(lambda: bool(coordinator.search_results), timeout=1000)
    QTest.keyClick(
        coordinator.viewer.query, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier
    )
    assert coordinator.viewer.query.text() == ""
    assert text.toPlainText() == "An unsaved draft with a selection"


def test_twenty_meanings_have_nonempty_generated_excerpts(generated_root):
    service = HelpBundleService(root=generated_root / "docs/_build/help")
    assert len(CONTROL_TOPICS) == 20
    assert len(set(CONTROL_TOPICS.values())) == 9
    for topic in CONTROL_TOPICS.values():
        excerpt = service.load_control_excerpt(topic)
        assert excerpt is not None and len(excerpt) > 200
        assert "<blockquote>" in excerpt


def test_native_shift_f1_uses_validated_excerpt(help_setup, qapp):
    coordinator, registry, _, panel, _ = help_setup
    button = QPushButton("Duration", panel)
    panel.layout().addWidget(button)
    registry.register_inspection(button, "event.duration", "event.timing")
    button.show()
    button.setFocus()
    qapp.processEvents()
    QCursor.setPos(button.mapToGlobal(button.rect().center()))
    with patch.object(
        coordinator.service,
        "load_control_excerpt",
        wraps=coordinator.service.load_control_excerpt,
    ) as load:
        QTest.keyClick(
            button,
            Qt.Key.Key_F1,
            Qt.KeyboardModifier.ShiftModifier,
        )
        qapp.processEvents()
        load.assert_called_with("event.timing")
        assert coordinator.inspection._topic_id == "event.timing"
    assert QApplication.activePopupWidget() is not None
    QWhatsThis.hideText()
    qapp.processEvents()


def test_inspection_exempt_click_does_not_activate(help_setup, qapp):
    coordinator, _, _, panel, _ = help_setup
    button = QPushButton("Ordinary action", panel)
    panel.layout().addWidget(button)
    button.show()
    clicks = []
    button.clicked.connect(lambda: clicks.append(True))
    qapp.processEvents()
    coordinator.inspection.enter()
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert clicks == []
    coordinator.inspection.dismiss()


def test_inspection_task_link_and_modal_deletion(help_setup, qapp):
    from src.gui.dialogs.help_aware_dialog import HelpAwareDialog

    coordinator, registry, owner, _, _ = help_setup
    dialog = HelpAwareDialog(owner)
    button = QPushButton("Direction", dialog)
    registry.register_inspection(button, "relation.direction", "relations.create")
    dialog.setModal(True)
    dialog.show()
    button.setFocus()
    qapp.processEvents()
    event = QHelpEvent(
        QEvent.Type.WhatsThis, QPoint(2, 2), button.mapToGlobal(QPoint(2, 2))
    )
    QCoreApplication.sendEvent(button, event)
    assert QApplication.activePopupWidget() is not None
    QCoreApplication.sendEvent(button, QWhatsThisClickedEvent("topic:relations.create"))
    assert coordinator.viewer.parentWidget() is dialog
    assert coordinator.viewer.isVisible()
    assert not QWhatsThis.inWhatsThisMode()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert coordinator.viewer.parentWidget() is owner


def test_geometry_region_uses_pointer_without_selection(help_setup, qapp):
    from src.gui.dialogs.feature_geometry_states_dialog import (
        FeatureGeometryStatesDialog,
    )

    coordinator, registry, owner, _, _ = help_setup
    dialog = FeatureGeometryStatesDialog(
        "Border", [{"id": "dated", "effective_date": 10}], parent=owner
    )
    HelpControlBindings(registry).bind(dialog)
    dialog.show()
    qapp.processEvents()
    listing = dialog.state_list
    target = listing.visualItemRect(listing.item(1)).center()
    resolved = registry.inspection_for(listing.viewport(), target)
    assert resolved[1].meaning == "geometry.dated"
    assert listing.currentRow() == 0
    coordinator.inspection.dismiss()
    dialog.close()


@pytest.mark.parametrize(
    "meaning, expected",
    [
        ("entity.baseline", {"scope": "baseline"}),
        ("entity.at-time", {"scope": "dated", "event_id": "handover"}),
        (None, None),
    ],
)
def test_destination_extraction_preserves_choices_and_help_metadata(
    editor, meaning, expected, monkeypatch
):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        editor, "_choose_dated_event", lambda snapshot=None: {"event_id": "handover"}
    )
    seen = []

    def choose():
        dialog = QApplication.activeModalWidget()
        controls = {
            button.property("krakenHelpMeaning"): button for button in dialog.buttons()
        }
        seen.extend(key for key in controls if key)
        if meaning:
            controls[meaning].click()
        else:
            dialog.button(QMessageBox.StandardButton.Cancel).click()

    QTimer.singleShot(0, choose)
    assert editor._new_attribute_destination("Office", {}) == expected
    assert set(seen) == {"entity.baseline", "entity.at-time"}


def test_hidden_baseline_confirmation_still_cancels(editor, monkeypatch):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No
    )

    def choose():
        dialog = QApplication.activeModalWidget()
        next(
            button
            for button in dialog.buttons()
            if button.property("krakenHelpMeaning") == "entity.baseline"
        ).click()

    QTimer.singleShot(0, choose)
    assert (
        editor._new_attribute_destination(
            "Office", {"absent_attribute_sources": {"Office": {}}}
        )
        is None
    )


def test_all_production_meanings_are_reachable(
    help_setup, qapp, standard_calendar, monkeypatch
):
    from PySide6.QtCore import QTimer

    from src.core.map import MapLayerNode
    from src.gui.dialogs.feature_geometry_states_dialog import (
        FeatureGeometryStatesDialog,
    )
    from src.gui.dialogs.temporal_validity_dialog import TemporalValidityDialog
    from src.gui.widgets.entity_editor import EntityEditorWidget
    from src.gui.widgets.relation_form import RelationForm
    from src.gui.widgets.temporal_range_widget import TemporalRangeWidget
    from src.gui.widgets.timeline import TimelineWidget

    coordinator, registry, owner, _, _ = help_setup
    bindings = HelpControlBindings(registry)
    span = TemporalRangeWidget(owner)
    entity = EntityEditorWidget(owner)
    relation = RelationForm(owner, source_event_date=10, source_name="Ada")
    geometry = FeatureGeometryStatesDialog(
        "Border", [{"id": "dated", "effective_date": 10}], parent=owner
    )
    visibility = TemporalValidityDialog(
        MapLayerNode(name="Border", layer_type="vector"),
        parent=owner,
        calendar_converter=standard_calendar,
        playhead_time=0,
    )
    timeline = TimelineWidget(owner)
    objects = [span, entity, relation, geometry, visibility, timeline]
    for widget in objects:
        bindings.bind(widget)
        for child in widget.findChildren(type(owner)):
            bindings.bind(child)
    found = {registration.meaning for registration in registry.inspection.values()}
    geometry.show()
    timeline.show()
    qapp.processEvents()
    listing = geometry.state_list
    for row in range(2):
        point = listing.visualItemRect(listing.item(row)).center()
        found.add(registry.inspection_for(listing.viewport(), point)[1].meaning)
    view = timeline.view
    view._playhead.setX(20)
    view._current_time_line.setX(200)
    view._playhead.show()
    view._current_time_line.show()
    for marker in (view._playhead, view._current_time_line):
        point = QPoint(view.mapFromScene(marker.x(), 0).x(), view.RULER_HEIGHT + 20)
        found.add(registry.inspection_for(view.viewport(), point)[1].meaning)

    def choose():
        dialog = QApplication.activeModalWidget()
        for button in dialog.buttons():
            bindings.bind(button)
        found.update(
            registration.meaning for registration in registry.inspection.values()
        )
        dialog.reject()

    QTimer.singleShot(0, choose)
    entity._new_attribute_destination("Office", {})
    assert found == set(CONTROL_TOPICS)
    for widget in objects:
        widget.hide()
        widget.deleteLater()


def test_pointer_inspection_keeps_date_draft(help_setup, standard_calendar, qapp):
    from src.gui.widgets.compact_date_widget import CompactDateWidget

    coordinator, registry, _, panel, _ = help_setup
    date = CompactDateWidget(panel, text_first=True)
    date.set_calendar_converter(standard_calendar)
    panel.layout().addWidget(date)
    HelpControlBindings(registry).bind(date)
    date.show()
    date.date_fields_button.click()
    date.txt_date.setFocus()
    qapp.processEvents()
    date.txt_date.selectAll()
    QTest.keyClicks(date.txt_date, "962")
    snapshot = (
        date.txt_date.text(),
        date.get_value(),
        date.feedback.text(),
        date.combo_month.currentIndex(),
    )
    changes = []
    date.value_changed.connect(changes.append)
    coordinator.inspection.enter()
    QTest.mouseClick(date.combo_month, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert QApplication.activePopupWidget() is not None
    assert snapshot == (
        date.txt_date.text(),
        date.get_value(),
        date.feedback.text(),
        date.combo_month.currentIndex(),
    )
    assert changes == []
    assert date.has_pending_draft()
    QWhatsThis.hideText()
    qapp.processEvents()


def test_native_popup_keys_do_not_apply_background_map(help_setup, qapp):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from src.app.main_window import GlobalShortcutFilter

    coordinator, registry, owner, panel, _ = help_setup
    trajectory = MagicMock()
    trajectory.is_active = True
    trajectory.is_date_editing = False
    trajectory.is_equalization_previewing = False
    owner.app_coordinator = SimpleNamespace(trajectory_edit=trajectory)
    owner.coordinator = MagicMock()
    owner.list_widget = MagicMock()
    shortcut_filter = GlobalShortcutFilter(owner)
    qapp.installEventFilter(shortcut_filter)
    button = QPushButton("Duration", panel)
    panel.layout().addWidget(button)
    registry.register_inspection(button, "event.duration", "event.timing")
    button.show()
    qapp.processEvents()
    try:
        for key, modifiers in (
            (Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier),
            (Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier),
            (Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier),
            (Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier),
            (Qt.Key.Key_E, Qt.KeyboardModifier.ControlModifier),
        ):
            coordinator.inspection.display(
                button, None, button.mapToGlobal(QPoint(2, 2))
            )
            qapp.processEvents()
            popup = QApplication.activePopupWidget()
            assert popup is not None and popup.windowHandle() is not None
            QTest.keyClick(popup.windowHandle(), key, modifiers)
            qapp.processEvents()
        trajectory.apply.assert_not_called()
        trajectory.cancel.assert_not_called()
        trajectory.delete_selected_keyframe.assert_not_called()
        owner.coordinator.undo.assert_not_called()
        assert not owner.list_widget.mock_calls
    finally:
        coordinator.inspection.dismiss()
        qapp.removeEventFilter(shortcut_filter)


def test_pointer_inspection_does_not_exit_f11(focus_setup, generated_root, qapp):
    from src.app.coordinators.help_coordinator import HelpCoordinator
    from src.gui.utils.help_context import HelpContextRegistry

    owner, editor, focus = focus_setup
    coordinator = HelpCoordinator(
        owner,
        HelpContextRegistry(),
        HelpBundleService(root=generated_root / "docs/_build/help"),
    )
    button = QPushButton("Unmapped action", owner)
    button.show()
    try:
        focus.enter(editor)
        text = editor.desc_edit.editor
        text.setFocus()
        QTest.keyClicks(text, " unfinished")
        document = text.document()
        snapshot = (
            text.toPlainText(),
            text.textCursor().position(),
            editor.has_unsaved_changes(),
        )
        coordinator.inspection.enter()
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        assert focus.active is editor
        assert text.document() is document
        assert snapshot == (
            text.toPlainText(),
            text.textCursor().position(),
            editor.has_unsaved_changes(),
        )
        coordinator.inspection.dismiss()
    finally:
        coordinator.stop()


def test_cpp_owned_label_and_viewport_keep_registration_after_wrapper_gc(
    help_setup, qapp
):
    import gc

    from PySide6.QtWidgets import QFormLayout, QLineEdit, QWidget

    from src.gui.dialogs.feature_geometry_states_dialog import (
        FeatureGeometryStatesDialog,
    )

    _, registry, owner, _, _ = help_setup
    group = QWidget(owner)
    form = QFormLayout(group)
    field = QLineEdit(group)
    form.addRow("Source", field)
    HelpControlBindings(registry).control(field, "entity.source")
    gc.collect()
    label = form.labelForField(field)
    assert registry.inspection_for(label)[1].meaning == "entity.source"
    dialog = FeatureGeometryStatesDialog(
        "Border", [{"id": "dated", "effective_date": 10}], parent=owner
    )
    HelpControlBindings(registry).bind(dialog)
    dialog.show()
    qapp.processEvents()
    gc.collect()
    point = dialog.state_list.visualItemRect(dialog.state_list.item(1)).center()
    assert (
        registry.inspection_for(dialog.state_list.viewport(), point)[1].meaning
        == "geometry.dated"
    )
    registry.clear()
    assert label.whatsThis() == ""
    assert registry.inspection_for(label) is None
    dialog.close()


def test_disabled_control_and_missing_excerpt_never_activate_or_show_stale_text(
    help_setup, qapp
):
    coordinator, registry, _, panel, _ = help_setup
    button = QPushButton("Duration", panel)
    panel.layout().addWidget(button)
    registry.register_inspection(button, "event.duration", "event.timing")
    button.setEnabled(False)
    button.show()
    clicks = []
    button.clicked.connect(lambda: clicks.append(True))
    qapp.processEvents()
    coordinator.inspection.enter()
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert QApplication.activePopupWidget() is not None
    assert clicks == []
    coordinator.inspection.dismiss()

    with patch.object(coordinator.service, "load_control_excerpt", return_value=None):
        with patch(
            "src.app.help_inspection_controller.QWhatsThis.showText",
            wraps=QWhatsThis.showText,
        ) as show:
            coordinator.inspection.display(
                button, None, button.mapToGlobal(QPoint(0, 0))
            )
            assert "unavailable" in show.call_args.args[1]
            assert "Duration records" not in show.call_args.args[1]
    coordinator.inspection.dismiss()


def test_search_reveal_retains_selected_result_and_bundle_error_clears_hits(
    help_setup, tmp_path
):
    coordinator, _, _, _, _ = help_setup
    coordinator.show_search()
    coordinator.viewer.query.setText("border")
    coordinator.search()
    assert len(coordinator.search_results) > 1
    coordinator.viewer.results.setCurrentRow(1)
    coordinator.viewer.hide_search()
    coordinator.show_search()
    assert coordinator.viewer.results.currentRow() == 1
    coordinator.service = HelpBundleService(root=tmp_path / "missing")
    coordinator.search()
    assert coordinator.search_results == ()
    assert coordinator.viewer.results.count() == 0
    assert "Regenerate Help" in coordinator.viewer.browser.toPlainText()
