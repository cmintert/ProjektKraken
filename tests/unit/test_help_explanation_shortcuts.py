"""Pointer and keyboard explanation routes preserve the live authoring origin."""

from unittest.mock import patch

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtGui import QCursor, QKeyEvent, QWhatsThisClickedEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.app.help_composition import HelpSurfaceBindings
from src.gui.dialogs.help_aware_dialog import HelpAwareDialog
from src.gui.utils.help_context import declare_inspection
from tests.unit import test_help_coordinator as existing

generated_root = existing.generated_root
help_setup = existing.help_setup
standard_calendar = existing.standard_calendar
focus_setup = existing.focus_setup
pytestmark = pytest.mark.ci_fast
SHIFT = Qt.KeyboardModifier.ShiftModifier
FOCUSED = SHIFT | Qt.KeyboardModifier.ControlModifier


def hover(widget, qapp, point=None):
    point = widget.rect().center() if point is None else point
    QCursor.setPos(widget.mapToGlobal(point))
    qapp.processEvents()


def explain(window, qapp, modifiers=SHIFT):
    QTest.keyClick(window.windowHandle(), Qt.Key.Key_F1, modifiers)
    qapp.processEvents()


@pytest.mark.parametrize("target_type", [QPushButton, QLabel, QLineEdit])
@pytest.mark.parametrize("enabled", [True, False])
def test_pointer_and_focus_are_distinct_without_activation(
    help_setup, qapp, target_type, enabled
):
    coordinator, registry, owner, panel, origin = help_setup
    target = target_type("Target", panel)
    panel.layout().addWidget(target)
    registry.register_inspection(origin, "event.duration", "event.timing")
    registry.register_inspection(target, "relation.direction", "relations.create")
    target.setEnabled(enabled)
    calls = []
    if isinstance(target, QPushButton):
        target.clicked.connect(lambda: calls.append(True))
    owner.activateWindow()
    origin.setFocus()
    QTest.qWait(30)
    cursor = origin.textCursor()
    cursor.setPosition(2)
    cursor.setPosition(9, cursor.MoveMode.KeepAnchor)
    origin.setTextCursor(cursor)
    snapshot = (
        origin.document(),
        origin.toPlainText(),
        cursor.position(),
        cursor.anchor(),
    )
    hover(target, qapp)
    explain(owner, qapp)
    assert coordinator.inspection._topic_id == "relations.create"
    assert QApplication.activePopupWidget() is not None
    coordinator.inspection.dismiss()
    qapp.processEvents()
    assert QApplication.focusWidget() is origin
    explain(owner, qapp, FOCUSED)
    assert coordinator.inspection._topic_id == "event.timing"
    assert snapshot == (
        origin.document(),
        origin.toPlainText(),
        origin.textCursor().position(),
        origin.textCursor().anchor(),
    )
    assert calls == []


def test_pointer_menu_action_wins_over_keyboard_highlight(help_setup, qapp):
    from src.app.help_declared_bindings import bind_declared_action

    coordinator, registry, owner, _, _ = help_setup
    outer = QMenu(owner)
    menu = outer.addMenu("Nested")
    first = declare_inspection(
        menu.addAction("First"), "first|authoring.create|help-authoring-create"
    )
    second = declare_inspection(
        menu.addAction("Second"), "second|writing.links|help-writing-links"
    )
    calls = []
    for action in (first, second):
        bind_declared_action(registry, action, menu)
        action.triggered.connect(lambda: calls.append(True))
    menu.popup(owner.mapToGlobal(QPoint(20, 20)))
    qapp.processEvents()
    hover(menu, qapp, menu.actionGeometry(second).center())
    menu.setActiveAction(first)
    explain(menu, qapp)
    assert coordinator.inspection._topic_id == "writing.links"
    assert calls == []


def test_unsupported_feedback_clears_content_and_f1_opens_origin_task(help_setup, qapp):
    coordinator, _, owner, panel, origin = help_setup
    target = QPushButton("Exempt", panel)
    panel.layout().addWidget(target)
    owner.activateWindow()
    origin.setFocus()
    qapp.processEvents()
    hover(target, qapp)
    with patch("src.app.help_inspection_controller.QWhatsThis.showText") as show:
        coordinator.inspection.explain_under_pointer()
        assert show.call_args.args[1] == coordinator.inspection.UNSUPPORTED_TEXT
        assert coordinator.inspection._topic_id is None
    explain(owner, qapp)
    popup = QApplication.activePopupWidget()
    assert popup is not None
    QTest.keyClick(popup.windowHandle(), Qt.Key.Key_F1)
    qapp.processEvents()
    assert coordinator.viewer.isVisible()
    assert coordinator.history[-1].uri.endswith("#help-writing-edit")


@pytest.mark.parametrize("blocked", ["foreign", "missing", "help", "modal"])
def test_pointer_does_not_fall_back_to_focus_or_blocked_surface(
    help_setup, qapp, blocked
):
    coordinator, registry, owner, panel, origin = help_setup
    registry.register_inspection(origin, "event.duration", "event.timing")
    foreign = QWidget()
    foreign.show()
    dialog = HelpAwareDialog(owner)
    if blocked == "modal":
        dialog.setModal(True)
        dialog.show()
    if blocked == "help":
        coordinator.request()
    qapp.processEvents()
    target = {
        "foreign": foreign,
        "missing": None,
        "help": coordinator.viewer.browser,
        "modal": origin,
    }[blocked]
    try:
        with patch(
            "src.app.help_inspection_controller.QApplication.widgetAt",
            return_value=target,
        ):
            with patch(
                "src.app.help_inspection_controller.QWhatsThis.showText"
            ) as show:
                coordinator.inspection.explain_under_pointer()
                show.assert_not_called()
    finally:
        foreign.close()
        dialog.close()


def test_shortcut_override_repeat_and_popup_replacement(help_setup, qapp):
    coordinator, registry, owner, panel, origin = help_setup
    registry.register_inspection(origin, "event.duration", "event.timing")
    target = QPushButton("Target", panel)
    panel.layout().addWidget(target)
    registry.register_inspection(target, "relation.direction", "relations.create")
    qapp.processEvents()
    hover(target, qapp)
    event = QKeyEvent(QEvent.Type.ShortcutOverride, Qt.Key.Key_F1, SHIFT)
    QCoreApplication.sendEvent(origin, event)
    assert event.isAccepted()
    with patch.object(coordinator.inspection, "explain_under_pointer") as show:
        repeat = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F1, SHIFT, "", True)
        QCoreApplication.sendEvent(origin, repeat)
        show.assert_not_called()
    explain(owner, qapp)
    assert not coordinator.inspection._explanation_chord
    assert coordinator.inspection._topic_id == "relations.create"
    # A second completed chord can replace the explanation using keyboard focus.
    popup = QApplication.activePopupWidget()
    QTest.keyClick(popup.windowHandle(), Qt.Key.Key_F1, FOCUSED)
    qapp.processEvents()
    assert coordinator.inspection._topic_id == "event.timing"
    assert not coordinator.inspection._explanation_chord
    popup = QApplication.activePopupWidget()
    QTest.keyClick(popup.windowHandle(), Qt.Key.Key_Escape)
    qapp.processEvents()
    assert QApplication.activePopupWidget() is None


def test_pointer_geometry_region_and_task_link_leave_selection_unchanged(
    help_setup, qapp
):
    from src.gui.dialogs.feature_geometry_states_dialog import (
        FeatureGeometryStatesDialog,
    )

    coordinator, _, owner, _, _ = help_setup
    dialog = FeatureGeometryStatesDialog(
        "Border", [{"id": "dated", "effective_date": 962}], parent=owner
    )
    bindings = HelpSurfaceBindings(coordinator)
    for widget in [dialog, *dialog.findChildren(QWidget)]:
        bindings.bind(widget)
    dialog.show()
    qapp.processEvents()
    listing = dialog.state_list
    before = listing.currentRow()
    hover(listing.viewport(), qapp, listing.visualItemRect(listing.item(1)).center())
    explain(dialog, qapp)
    assert coordinator.inspection._topic_id == "map.historical-geometry"
    assert listing.currentRow() == before
    QCoreApplication.sendEvent(
        listing.viewport(), QWhatsThisClickedEvent("topic:map.historical-geometry")
    )
    assert coordinator.viewer.isVisible()
    assert coordinator.history[-1].uri.endswith("#help-map-historical-geometry")
    dialog.close()


@pytest.mark.parametrize("modifiers", [SHIFT, FOCUSED])
def test_explanation_preserves_unfinished_date(
    help_setup, standard_calendar, qapp, modifiers
):
    from src.gui.widgets.compact_date_widget import CompactDateWidget

    coordinator, _, owner, panel, _ = help_setup
    date = CompactDateWidget(panel, text_first=True)
    date.set_calendar_converter(standard_calendar)
    panel.layout().addWidget(date)
    bindings = HelpSurfaceBindings(coordinator)
    for widget in [date, *date.findChildren(QWidget)]:
        bindings.bind(widget)
    date.show()
    date.date_fields_button.click()
    owner.activateWindow()
    date.txt_date.setFocus()
    qapp.processEvents()
    date.txt_date.selectAll()
    QTest.keyClicks(date.txt_date, "962")
    before = (date.txt_date.text(), date.get_value(), date.feedback.text())
    changes = []
    date.value_changed.connect(changes.append)
    hover(date.combo_month, qapp)
    explain(owner, qapp, modifiers)
    assert QApplication.activePopupWidget() is not None
    coordinator.inspection.dismiss()
    qapp.processEvents()
    assert before == (date.txt_date.text(), date.get_value(), date.feedback.text())
    assert date.has_pending_draft()
    assert changes == []


@pytest.mark.parametrize("modifiers", [SHIFT, FOCUSED])
@pytest.mark.parametrize("view_mode", ["rich", "source"])
def test_shortcuts_preserve_f11_live_writing(
    focus_setup, generated_root, qapp, modifiers, view_mode
):
    from src.app.coordinators.help_coordinator import HelpCoordinator
    from src.gui.utils.help_context import HelpContextRegistry
    from src.services.help_bundle_service import HelpBundleService

    owner, editor, focus = focus_setup
    coordinator = HelpCoordinator(
        owner,
        HelpContextRegistry(),
        HelpBundleService(root=generated_root / "docs/_build/help"),
    )
    bindings = HelpSurfaceBindings(coordinator)
    for widget in [owner, *owner.findChildren(QWidget)]:
        bindings.bind(widget)
    try:
        focus.enter(editor)
        text = editor.desc_edit.editor
        if view_mode == "source":
            text.toggle_view_mode()
        owner.activateWindow()
        text.setFocus()
        qapp.processEvents()
        QTest.keyClicks(text, " unfinished")
        before = (
            text.document(),
            text.toPlainText(),
            text.textCursor().position(),
            editor.has_unsaved_changes(),
        )
        hover(text, qapp)
        explain(owner, qapp, modifiers)
        assert coordinator.inspection._topic_id == "writing.edit"
        popup = QApplication.activePopupWidget()
        assert popup is not None
        QTest.keyClick(popup.windowHandle(), Qt.Key.Key_Escape)
        qapp.processEvents()
        assert focus.active is editor
        assert before == (
            text.document(),
            text.toPlainText(),
            text.textCursor().position(),
            editor.has_unsaved_changes(),
        )
    finally:
        coordinator.stop()


@pytest.mark.parametrize("modifiers", [SHIFT, FOCUSED])
def test_shortcut_nested_modal_target_and_outer_deletion(help_setup, qapp, modifiers):
    coordinator, registry, owner, _, _ = help_setup
    outer = HelpAwareDialog(owner)
    inner = HelpAwareDialog(outer)
    field = QLineEdit("unfinished", inner)
    QVBoxLayout(inner).addWidget(field)
    registry.register_inspection(field, "relation.direction", "relations.create")
    outer.setModal(True)
    inner.setModal(True)
    outer.show()
    inner.show()
    inner.activateWindow()
    field.setFocus()
    qapp.processEvents()
    hover(field, qapp)
    explain(inner, qapp, modifiers)
    assert coordinator.inspection._topic_id == "relations.create"
    assert QApplication.activePopupWidget() is not None
    assert field.text() == "unfinished"
    outer.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()
    assert QApplication.activePopupWidget() is None
    assert not qapp.property("krakenInspectionPopup")


def test_empty_menu_space_shows_feedback_without_focused_fallback(help_setup, qapp):
    coordinator, registry, owner, _, origin = help_setup
    registry.register_inspection(origin, "event.duration", "event.timing")
    menu = QMenu(owner)
    menu.addAction("Exempt")
    # Reserve genuine empty space; menu frame pixels can belong to the first
    # action under production QSS and native styles with no outer menu margin.
    menu.setMinimumHeight(menu.sizeHint().height() + 24)
    menu.popup(owner.mapToGlobal(QPoint(20, 20)))
    qapp.processEvents()
    point = QPoint(menu.width() // 2, menu.height() - 8)
    assert menu.actionAt(point) is None
    hover(menu, qapp, point)
    explain(menu, qapp)
    popup = QApplication.activePopupWidget()
    assert popup is not None and popup is not menu
    assert coordinator.inspection._topic_id is None


def test_help_chords_are_visible_in_shortcuts_dialog(qtbot):
    from src.gui.dialogs.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
    from src.gui.utils.shortcut_manager import ShortcutManager

    dialog = KeyboardShortcutsDialog()
    qtbot.addWidget(dialog)
    labels = {label.text() for label in dialog.findChildren(QLabel)}
    for shortcut in (
        ShortcutManager.HELP,
        ShortcutManager.EXPLAIN_CONTROL,
        ShortcutManager.EXPLAIN_FOCUSED_CONTROL,
    ):
        assert shortcut.sequence in labels
        assert shortcut.description in labels
