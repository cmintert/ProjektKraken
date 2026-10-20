"""Context routing, real offline navigation and companion isolation regressions."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt, QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QLineEdit, QTextEdit, QVBoxLayout, QWidget

from src.app.coordinators.help_coordinator import HelpCoordinator
from src.gui.utils.help_context import HelpContextRegistry, owns_help_input
from src.services.help_bundle_service import HelpBundleService
from tests.unit import test_compact_date_widget as date_tests
from tests.unit import test_focus_writing as focus_tests
from tests.unit import test_help_bundle as bundle_tests

generated_root = bundle_tests.generated_root
focus_setup = focus_tests.focus_setup
standard_calendar = date_tests.standard_calendar

pytestmark = [
    pytest.mark.ci_fast,
    pytest.mark.usefixtures("isolated_theme_manager"),
]


@pytest.fixture
def help_setup(qapp, init_theme_manager, generated_root):
    owner = QWidget()
    panel = QWidget(owner)
    text = QTextEdit(panel)
    text.setPlainText("An unsaved draft with a selection")
    layout = QVBoxLayout(owner)
    layout.addWidget(panel)
    QVBoxLayout(panel).addWidget(text)
    registry = HelpContextRegistry()
    registry.register_panel(panel, "authoring.details")
    registry.register_control(text, "writing.edit", panel)
    service = HelpBundleService(root=generated_root / "docs/_build/help")
    coordinator = HelpCoordinator(owner, registry, service)
    owner.show()
    text.setFocus()
    qapp.processEvents()
    yield coordinator, registry, owner, panel, text
    coordinator.stop()
    coordinator.viewer.setParent(owner)
    owner.close()
    owner.deleteLater()
    qapp.processEvents()


def test_context_precedence_and_scoped_operation(help_setup):
    coordinator, registry, owner, panel, text = help_setup
    registry.register_operation(panel, lambda: "map.historical-geometry")
    coordinator.request()
    assert coordinator.history[-1].uri.endswith("#help-writing-edit")
    registry.controls[text] = "unknown.topic"
    coordinator.refresh()
    assert coordinator.history[-1].uri.endswith("#help-map-historical-geometry")
    dialog = QDialog(owner)
    field = QLineEdit(dialog)
    registry.register_dialog(dialog, "event.chronology")
    candidates, _ = registry.candidates(field)
    assert candidates == ["event.chronology", "manual.home"]
    registry.register_control(field, "date.precision")
    assert registry.candidates(field)[0][0] == "date.precision"


def test_f1_preserves_live_draft_and_reuses_viewer(help_setup, qapp):
    coordinator, _, _, _, text = help_setup
    cursor = text.textCursor()
    cursor.setPosition(2)
    cursor.setPosition(9, cursor.MoveMode.KeepAnchor)
    text.setTextCursor(cursor)
    document = text.document()
    snapshot = (text.toPlainText(), cursor.position(), cursor.anchor())
    QTest.keyClick(text, Qt.Key.Key_F1)
    qapp.processEvents()
    assert coordinator.viewer.isVisible()
    assert owns_help_input(coordinator.viewer.browser)
    QTest.keyClick(coordinator.viewer.browser, Qt.Key.Key_F1)
    assert len(coordinator.history) == 1
    QTest.keyClick(coordinator.viewer.browser, Qt.Key.Key_Escape)
    qapp.processEvents()
    assert not coordinator.viewer.isVisible()
    assert text.document() is document
    assert snapshot == (
        text.toPlainText(),
        text.textCursor().position(),
        text.textCursor().anchor(),
    )


def test_navigation_and_failed_link_recovery(help_setup):
    coordinator, _, _, _, _ = help_setup
    coordinator.request()
    first = coordinator.history[0].uri
    coordinator.open_topic("manual.home")
    assert len(coordinator.history) == 2
    coordinator.move(-1)
    assert coordinator.history[coordinator.index].uri == first
    coordinator.open_topic("date.precision")
    assert len(coordinator.history) == 2
    coordinator.follow_link(QUrl("https://example.invalid/"))
    assert coordinator.viewer.title.text() == "Help unavailable"
    coordinator.open_topic("date.precision")
    assert coordinator.viewer.title.text() != "Help unavailable"
    assert "Date" in coordinator.viewer.browser.toPlainText()


def test_modal_window_input_and_owner_transfer(help_setup, qapp):
    coordinator, registry, owner, _, _ = help_setup
    dialog = QDialog(owner)
    dialog.setModal(True)
    field = QLineEdit(dialog)
    QVBoxLayout(dialog).addWidget(field)
    registry.register_dialog(dialog, "relations.create")
    dialog.show()
    field.setFocus()
    qapp.processEvents()
    QTest.keyClick(dialog.windowHandle(), Qt.Key.Key_F1)
    qapp.processEvents()
    assert coordinator.viewer.parentWidget() is dialog
    assert not coordinator.viewer.isModal()
    QTest.keyClick(coordinator.viewer.windowHandle(), Qt.Key.Key_Escape)
    qapp.processEvents()
    assert not coordinator.viewer.isVisible()
    assert dialog.isVisible()
    coordinator.request()
    dialog.reject()
    assert coordinator.viewer.parentWidget() is owner
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert coordinator.viewer.isVisible()
    coordinator.return_to_work()


def test_missing_bundle_then_retry(help_setup, tmp_path):
    coordinator, _, _, _, _ = help_setup
    original = coordinator.service
    coordinator.service = HelpBundleService(root=tmp_path / "missing")
    coordinator.request()
    assert "Regenerate Help" in coordinator.viewer.browser.toPlainText()
    coordinator.service = original
    coordinator.refresh()
    assert coordinator.viewer.title.text() != "Help unavailable"


def test_reading_position_and_destroyed_origin(help_setup, qapp):
    coordinator, _, _, panel, text = help_setup
    coordinator.request()
    coordinator.viewer.browser.verticalScrollBar().setValue(80)
    position = coordinator.viewer.browser.verticalScrollBar().value()
    assert position > 0
    coordinator.open_topic("writing.edit")
    assert coordinator.viewer.browser.verticalScrollBar().value() == position
    coordinator.open_topic("manual.home")
    coordinator.move(-1)
    assert coordinator.viewer.browser.verticalScrollBar().value() == position
    text.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    coordinator.return_to_work()
    qapp.processEvents()
    assert (
        coordinator.live(coordinator.origin) is None
        or coordinator.live(coordinator.origin) is panel
    )
    assert panel.isVisible()


@pytest.mark.parametrize(
    "theme_name",
    [
        "dark_mode",
        "light_mode",
        "fantasy_mode",
        "imperial_mode",
        "cyberpunk_mode",
        "muted_light_mode",
    ],
)
def test_theme_switch_preserves_reading_and_authoring_context(
    help_setup, theme_name, qapp, monkeypatch
):
    from src.core.theme_manager import ThemeManager

    coordinator, _, _, _, text = help_setup
    coordinator.request()
    monkeypatch.setattr(qapp, "setStyleSheet", coordinator.viewer.setStyleSheet)
    monkeypatch.setattr(qapp, "setPalette", coordinator.viewer.setPalette)
    coordinator.viewer.browser.verticalScrollBar().setValue(80)
    snapshot = (
        coordinator.index,
        coordinator.viewer.browser.verticalScrollBar().value(),
        text.toPlainText(),
        text.textCursor().position(),
        coordinator.live(coordinator.origin),
    )
    ThemeManager().set_theme(theme_name)
    assert snapshot == (
        coordinator.index,
        coordinator.viewer.browser.verticalScrollBar().value(),
        text.toPlainText(),
        text.textCursor().position(),
        coordinator.live(coordinator.origin),
    )


def test_nested_modal_owner_deferred_deletion(help_setup, qapp):
    import shiboken6

    coordinator, registry, owner, _, _ = help_setup
    outer = QDialog(owner)
    inner = QDialog(outer)
    field = QLineEdit(inner)
    QVBoxLayout(inner).addWidget(field)
    outer.setModal(True)
    inner.setModal(True)
    registry.register_dialog(inner, "relations.timing")
    outer.show()
    inner.show()
    field.setFocus()
    qapp.processEvents()
    coordinator.request()
    assert coordinator.viewer.parentWidget() is inner
    inner.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert shiboken6.isValid(coordinator.viewer)
    assert coordinator.viewer.parentWidget() is outer
    outer.reject()
    assert coordinator.viewer.parentWidget() is owner


def test_deleting_outer_modal_detaches_inner_owned_help(help_setup, qapp):
    import shiboken6

    coordinator, registry, owner, _, _ = help_setup
    outer = QDialog(owner)
    inner = QDialog(outer)
    field = QLineEdit(inner)
    QVBoxLayout(inner).addWidget(field)
    outer.setModal(True)
    inner.setModal(True)
    registry.register_dialog(inner, "relations.create")
    outer.show()
    inner.show()
    field.setFocus()
    qapp.processEvents()
    coordinator.request()
    assert coordinator.viewer.parentWidget() is inner
    outer.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert shiboken6.isValid(coordinator.viewer)
    assert coordinator.viewer.parentWidget() is owner


def test_resource_loading_is_confined(help_setup, tmp_path):
    coordinator, _, _, _, _ = help_setup
    image = tmp_path / "outside.png"
    from PySide6.QtGui import QImage

    payload = QImage(2, 2, QImage.Format.Format_RGB32)
    payload.save(str(image))
    coordinator.load_resource(2, QUrl.fromLocalFile(str(image)))
    assert coordinator.viewer.browser.resource_result.isNull()
    coordinator.load_resource(2, QUrl("https://example.invalid/image.png"))
    assert coordinator.viewer.browser.resource_result.isNull()


def test_reparented_writing_keeps_semantic_owner(help_setup):
    coordinator, registry, owner, panel, text = help_setup
    presentation = QWidget(owner)
    text.setParent(presentation)
    candidates, _ = registry.candidates(text)
    assert candidates == ["writing.edit", "authoring.details", "manual.home"]
    text.setParent(panel)


def test_no_origin_falls_back_to_manual(help_setup):
    coordinator, registry, _, _, _ = help_setup
    assert registry.candidates(None) == (["manual.home"], None)
    coordinator.origin = None
    coordinator.refresh()
    assert coordinator.history[-1].uri.endswith("#help-manual-home")


@pytest.mark.parametrize("view_mode", ["rich", "source"])
def test_help_keeps_real_f11_writing_and_undo(
    focus_setup, generated_root, qapp, view_mode
):
    window, editor, focus = focus_setup
    registry = HelpContextRegistry()
    registry.register_panel(editor, "authoring.details")
    registry.register_control(editor.desc_edit, "writing.edit", editor)
    coordinator = HelpCoordinator(
        window, registry, HelpBundleService(root=generated_root / "docs/_build/help")
    )
    try:
        focus.enter(editor)
        text = editor.desc_edit.editor
        if view_mode == "source":
            text.toggle_view_mode()
        text.setFocus()
        QTest.keyClicks(text, " unsaved")
        snapshot = (
            text.toPlainText(),
            text.textCursor().position(),
            editor.has_unsaved_changes(),
            window.workspace.active_panel("center"),
        )
        document = text.document()
        QTest.keyClick(text, Qt.Key.Key_F1)
        qapp.processEvents()
        assert coordinator.viewer.isVisible()
        QTest.keyClick(coordinator.viewer.browser, Qt.Key.Key_F11)
        QTest.keyClick(coordinator.viewer.browser, Qt.Key.Key_Escape)
        qapp.processEvents()
        assert focus.active is editor
        assert text.document() is document
        assert snapshot == (
            text.toPlainText(),
            text.textCursor().position(),
            editor.has_unsaved_changes(),
            window.workspace.active_panel("center"),
        )
        text.undo()
        assert " unsaved" not in text.toPlainText()
    finally:
        coordinator.stop()


def test_help_keyboard_does_not_mutate_background_map(help_setup, qapp):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from src.app.main_window import GlobalShortcutFilter

    coordinator, registry, owner, panel, text = help_setup
    trajectory = MagicMock()
    trajectory.is_active = True
    trajectory.is_date_editing = False
    trajectory.is_equalization_previewing = False
    owner.app_coordinator = SimpleNamespace(trajectory_edit=trajectory)
    owner.coordinator = MagicMock()
    owner.list_widget = MagicMock()
    shortcut_filter = GlobalShortcutFilter(owner)
    qapp.installEventFilter(shortcut_filter)
    registry.controls.pop(text)
    registry.register_operation(panel, lambda: "map.trajectories")
    try:
        coordinator.request()
        assert coordinator.history[-1].uri.endswith("#help-map-trajectories")
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Delete):
            QTest.keyClick(coordinator.viewer.browser, key)
        for key in (
            Qt.Key.Key_Z,
            Qt.Key.Key_Y,
            Qt.Key.Key_E,
            Qt.Key.Key_I,
            Qt.Key.Key_M,
        ):
            QTest.keyClick(
                coordinator.viewer.browser, key, Qt.KeyboardModifier.ControlModifier
            )
        QTest.keyClick(coordinator.viewer.browser, Qt.Key.Key_Escape)
        trajectory.apply.assert_not_called()
        trajectory.cancel.assert_not_called()
        trajectory.delete_selected_keyframe.assert_not_called()
        owner.coordinator.undo.assert_not_called()
        owner.coordinator.redo.assert_not_called()
        assert not owner.list_widget.mock_calls
    finally:
        qapp.removeEventFilter(shortcut_filter)


def test_real_unsaved_relation_dialog_keeps_fields(help_setup, qapp):
    from src.app.help_composition import HelpSurfaceBindings
    from src.gui.dialogs.relation_dialog import RelationEditDialog

    coordinator, _, owner, panel, _ = help_setup
    coordinator.registry.register_operation(panel, lambda: "map.historical-geometry")
    bindings = HelpSurfaceBindings(coordinator)
    dialog = RelationEditDialog(owner, source_name="Ada")
    dialog.setModal(True)
    bindings.bind(dialog)
    bindings.bind(dialog.form)
    dialog.show()
    dialog.form.notes_edit.setPlainText("Unfinished relation notes")
    dialog.form.notes_edit.setFocus()
    qapp.processEvents()
    QTest.keyClick(dialog.windowHandle(), Qt.Key.Key_F1)
    qapp.processEvents()
    assert coordinator.history[-1].uri.endswith("#help-relations-create")
    assert coordinator.viewer.parentWidget() is dialog
    QTest.keyClick(coordinator.viewer.windowHandle(), Qt.Key.Key_Escape)
    qapp.processEvents()
    assert dialog.form.notes_edit.toPlainText() == "Unfinished relation notes"
    assert dialog.isVisible()
    assert dialog.result() == 0
    coordinator.request()
    dialog.reject()
    assert coordinator.viewer.parentWidget() is owner


def test_unfinished_chronology_input_keeps_dialog_state(help_setup, qapp):
    from src.app.help_composition import HelpSurfaceBindings
    from src.core.events import Event
    from src.gui.dialogs.event_chronology_dialog import EventChronologyDialog

    coordinator, _, owner, _, _ = help_setup
    event = Event(name="Arrival", lore_date=1)
    dialog = EventChronologyDialog(event.id, [event], parent=owner)
    dialog.setModal(True)
    bindings = HelpSurfaceBindings(coordinator)
    bindings.bind(dialog)
    dialog._add_row()
    unfinished = dialog._rows[-1]["target"].lineEdit()
    unfinished.setText("Unfinished event reference")
    dialog.show()
    unfinished.setFocus()
    qapp.processEvents()
    QTest.keyClick(dialog.windowHandle(), Qt.Key.Key_F1)
    qapp.processEvents()
    assert coordinator.history[-1].uri.endswith("#help-event-chronology")
    coordinator.return_to_work()
    assert unfinished.text() == "Unfinished event reference"
    assert dialog.operations == []
    assert dialog.result() == 0
    dialog.reject()


def test_help_preserves_real_geometry_working_copy(help_setup):
    from copy import deepcopy

    from src.app.coordinators.feature_geometry_coordinator import (
        FeatureGeometryCoordinator,
    )
    from tests.unit.test_feature_geometry_coordinator import _marker_snapshot, _Window

    coordinator, registry, _, panel, text = help_setup
    infrastructure = _Window()
    geometry = FeatureGeometryCoordinator(infrastructure)
    geometry.bind_ui()
    geometry.on_markers_ready("map", [_marker_snapshot()])
    infrastructure.timeline.time = 150.0
    geometry.start_edit_at_playhead("object")
    working = [{"x": 0.3, "y": 0.4}, {"x": 0.6, "y": 0.7}]
    geometry.on_preview_changed("object", working)
    snapshot = deepcopy(geometry._session)
    commands = []
    infrastructure.command_requested.connect(commands.append)
    registry.controls.pop(text)
    registry.register_operation(
        panel, lambda: "map.historical-geometry" if geometry.is_active else None
    )
    coordinator.request()
    coordinator.open_topic("manual.home")
    coordinator.refresh()
    coordinator.return_to_work()
    assert geometry._session == snapshot
    assert geometry.is_active
    assert infrastructure.timeline.time == 150.0
    assert commands == []


@pytest.mark.parametrize("route", ["f1", "menu"])
def test_help_does_not_validate_or_accept_date_draft(
    help_setup, standard_calendar, qapp, route
):
    from src.gui.widgets.compact_date_widget import CompactDateWidget

    coordinator, registry, _, panel, _ = help_setup
    date = CompactDateWidget(panel, text_first=True)
    date.set_calendar_converter(standard_calendar)
    panel.layout().addWidget(date)
    registry.register_control(date, "date.precision")
    date.show()
    date.txt_date.setFocus()
    qapp.processEvents()
    date.txt_date.selectAll()
    QTest.keyClicks(date.txt_date, "962")
    snapshot = (date.txt_date.text(), date.get_value(), date.feedback.text())
    changes = []
    date.value_changed.connect(changes.append)
    if route == "f1":
        QTest.keyClick(date.txt_date, Qt.Key.Key_F1)
    else:
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QMenu

        menu = QMenu(coordinator.owner)
        menu.aboutToShow.connect(coordinator.suspend_origin)
        action = menu.addAction("Help for current task")
        action.triggered.connect(coordinator.request)
        menu.popup(date.txt_date.mapToGlobal(QPoint(0, 0)))
        menu.setActiveAction(action)
        qapp.processEvents()
        QTest.keyClick(menu.windowHandle(), Qt.Key.Key_Return)
    qapp.processEvents()
    assert coordinator.history[-1].uri.endswith("#help-date-precision")
    assert snapshot == (date.txt_date.text(), date.get_value(), date.feedback.text())
    assert date.has_pending_draft()
    assert changes == []
    coordinator.return_to_work()
    qapp.processEvents()
    QTest.keyClick(date.txt_date, Qt.Key.Key_Return)
    assert not date.has_pending_draft()
    assert len(changes) == 1
