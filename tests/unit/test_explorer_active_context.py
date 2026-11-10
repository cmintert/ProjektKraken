"""Active authoring context is independent of Explorer filtering and refresh."""

from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QDrag
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QMainWindow

from src.app.coordinators.navigation_coordinator import NavigationCoordinator
from src.core.entities import Entity
from src.core.events import Event
from src.gui.models.explorer_model import ExplorerModel
from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE, UnifiedListWidget

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def context(qtbot):
    window = QMainWindow()
    qtbot.addWidget(window)
    window.unified_list = UnifiedListWidget()
    window.setCentralWidget(window.unified_list)
    window.workspace = Mock()
    window.timeline = Mock()
    window.data_coordinator = Mock()
    window.event_editor = Mock()
    window.entity_editor = Mock()
    for editor in (window.event_editor, window.entity_editor):
        editor.has_unsaved_changes.return_value = False
        editor.relation_authoring = None
    window.navigation_coordinator = NavigationCoordinator(window)
    window.unified_list.item_selected.connect(
        window.navigation_coordinator.on_item_selected
    )
    return window


def identities(widget):
    proxy = widget._proxy_model
    return [
        (index.data(ExplorerModel.ItemTypeRole), index.data(ExplorerModel.ItemIdRole))
        for index in (proxy.index(row, 0) for row in range(proxy.rowCount()))
    ]


@pytest.mark.parametrize("kind", ["entity", "event"])
@pytest.mark.parametrize("filter_kind", ["search", "tags", "type"])
def test_active_pin_survives_refresh_without_navigation(
    context, qtbot, kind, filter_kind
):
    widget = context.unified_list
    nav = context.navigation_coordinator
    old = Entity(
        id="old", name="Alpha", type="Person", attributes={"_tags": ["visible"]}
    )
    target = (
        Entity(id="new", name="Zulu", type="Person")
        if kind == "entity"
        else Event(id="new", name="Zulu", lore_date=3.0)
    )
    events = [target] if kind == "event" else []
    entities = [old, target] if kind == "entity" else [old]
    widget.set_data(events, entities)
    nav.set_global_selection("entity", "old")
    if filter_kind == "search":
        widget.search_bar.setText("Alpha")
    elif filter_kind == "tags":
        widget.set_advanced_filter({"include": ["visible"]})
    else:
        widget.filter_combo.setCurrentText(
            "Entities Only" if kind == "event" else "Events Only"
        )
    signal = QSignalSpy(widget.item_selected)
    nav.on_item_selected("entity", "old")  # An older unresolved pointer gesture.
    nav.set_global_selection(kind, "new")
    assert not nav._selection_timer.isActive()
    assert nav._pending_selection is None
    assert identities(widget)[0] == (kind, "new")
    assert widget._proxy_model.index(0, 0).data(widget._proxy_model.PinnedRole)
    assert "Hidden by filters" in widget._proxy_model.index(0, 0).data(
        Qt.ItemDataRole.AccessibleTextRole
    )

    for _ in range(2):
        widget.set_data(events, entities)
        target.description = "A saved description"
        widget.apply_lore_effects(
            [
                dict(
                    object_type=kind,
                    operation="upsert",
                    object_id="new",
                    snapshot=target.to_dict(),
                    relations_changed=False,
                )
            ]
        )
        widget._toggle_sort_direction()
    qtbot.wait(330)
    assert nav.selected_id == "new"
    assert signal.count() == 0
    assert identities(widget).count((kind, "new")) == 1
    assert widget.search_bar.text() == ("Alpha" if filter_kind == "search" else "")
    assert widget.get_advanced_filter_config() == (
        {"include": ["visible"]} if filter_kind == "tags" else {}
    )
    if filter_kind == "type":
        assert widget.filter_combo.currentText() != "All Items"


def test_pin_matches_again_and_genuine_selection_navigates(context, qtbot):
    widget = context.unified_list
    nav = context.navigation_coordinator
    old = Entity(id="old", name="Alpha", type="Person")
    new = Entity(id="new", name="Zulu", type="Person")
    widget.set_data([], [old, new])
    widget.search_bar.setText("Alpha")
    nav.set_global_selection("entity", "new")
    pinned = widget._proxy_model.index(0, 0)
    widget._proxy_model.setData(
        pinned, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole
    )
    assert widget.get_checked_items() == [("entity", "new")]
    widget.search_bar.clear()
    assert identities(widget) == [("entity", "old"), ("entity", "new")]
    assert not any(
        widget._proxy_model.index(row, 0).data(widget._proxy_model.PinnedRole)
        for row in range(2)
    )
    assert widget.get_checked_items() == [("entity", "new")]
    widget.list_widget.setCurrentIndex(widget._proxy_model.index(0, 0))
    qtbot.waitUntil(lambda: nav.selected_id == "old")
    assert widget._active_item == ("entity", "old")


def test_missing_deleted_and_cleared_active_objects_never_choose_fallback(context):
    widget = context.unified_list
    widget.set_data([], [Entity(id="a", name="Alpha", type="Person")])
    widget.set_active_item("entity", "missing")
    assert not widget.list_widget.currentIndex().isValid()
    assert not widget.list_widget.selectionModel().selectedIndexes()
    widget.set_active_item("entity", "a")
    widget.apply_lore_effects(
        [
            dict(
                object_type="entity",
                operation="delete",
                object_id="a",
                snapshot=None,
                relations_changed=False,
            )
        ]
    )
    assert widget._active_item is None
    assert identities(widget) == []
    widget.set_active_item(None, None)
    assert not widget.list_widget.currentIndex().isValid()


def test_explicit_reveal_api_still_clears_filters_for_pinned_object(context):
    widget = context.unified_list
    widget.set_data([], [Entity(id="a", name="Alpha", type="Person")])
    widget.search_bar.setText("unmatched")
    widget.set_advanced_filter({"include": ["other"]})
    widget.filter_combo.setCurrentText("Events Only")
    widget.set_active_item("entity", "a")
    assert widget.select_item("entity", "a", reveal_hidden=True)
    assert widget.search_bar.text() == ""
    assert widget.get_advanced_filter_config() == {}
    assert widget.filter_combo.currentText() == "All Items"
    assert not widget._proxy_model.index(0, 0).data(widget._proxy_model.PinnedRole)


def test_same_target_navigation_cancels_older_gesture(context, qtbot):
    nav = context.navigation_coordinator
    context.unified_list.set_data(
        [],
        [
            Entity(id="a", name="Alpha", type="Person"),
            Entity(id="b", name="Bravo", type="Person"),
        ],
    )
    nav.set_global_selection("entity", "a")
    nav.on_item_selected("entity", "b")
    nav.set_global_selection("entity", "a")
    qtbot.wait(330)
    assert nav.selected_id == "a"
    assert nav._pending_selection is None


def test_cancelled_navigation_keeps_pin_and_draft(context, qtbot):
    from PySide6.QtWidgets import QMessageBox

    widget = context.unified_list
    widget.set_data(
        [],
        [
            Entity(id="a", name="Alpha", type="Person"),
            Entity(id="b", name="Bravo", type="Person"),
        ],
    )
    nav = context.navigation_coordinator
    nav.set_global_selection("entity", "a")
    widget.search_bar.setText("Bravo")
    context.entity_editor.has_unsaved_changes.return_value = True
    with patch(
        "src.app.coordinators.navigation_coordinator.QMessageBox.warning",
        return_value=QMessageBox.StandardButton.Cancel,
    ):
        widget.list_widget.setCurrentIndex(widget._proxy_model.index(1, 0))
        qtbot.wait(330)
    assert nav.selected_id == "a"
    assert widget._active_item == ("entity", "a")
    assert widget.list_widget.currentIndex().data(ExplorerModel.ItemIdRole) == "a"
    context.entity_editor.set_dirty.assert_not_called()


def test_pinned_row_uses_normal_drag_context_and_delete_routes(
    context, qtbot, monkeypatch
):
    import json

    widget = context.unified_list
    widget.set_data([], [Entity(id="new", name="Zulu", type="Person")])
    widget.search_bar.setText("missing")
    widget.set_active_item("entity", "new")
    context.show()
    qtbot.waitUntil(context.isVisible)
    payloads = []

    def drag_exec(drag, actions):
        payloads.append(json.loads(bytes(drag.mimeData().data(KRAKEN_ITEM_MIME_TYPE))))
        return Qt.DropAction.IgnoreAction

    monkeypatch.setattr(QDrag, "exec", drag_exec)
    widget.list_widget.startDrag(Qt.DropAction.CopyAction)
    assert payloads == [{"id": "new", "type": "entity", "name": "Zulu"}]
    with patch.object(widget, "_execute_context_menu", return_value=None) as execute:
        point = widget.list_widget.visualRect(widget._proxy_model.index(0, 0)).center()
        widget._show_context_menu(point)
        assert execute.called
    with patch.object(widget, "_delete_items") as delete:
        widget._on_delete_clicked()
        delete.assert_called_once_with([("entity", "new", "Zulu")])
    assert widget.btn_delete.isEnabled()


def test_keyboard_navigation_and_native_checkbox_on_pinned_row(context, qtbot):
    from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

    widget = context.unified_list
    widget.set_data(
        [],
        [
            Entity(id="a", name="Alpha", type="Person"),
            Entity(id="z", name="Zulu", type="Person"),
        ],
    )
    widget.search_bar.setText("Alpha")
    context.navigation_coordinator.set_global_selection("entity", "z")
    context.show()
    context.activateWindow()
    qtbot.waitUntil(context.isActiveWindow)
    view = widget.list_widget
    view.setFocus()
    index = widget._proxy_model.index(0, 0)
    option = QStyleOptionViewItem()
    option.initFrom(view)
    widget.list_widget.itemDelegate().initStyleOption(option, index)
    option.rect = view.visualRect(index)
    option.widget = view
    indicator = view.style().subElementRect(
        QStyle.SubElement.SE_ItemViewItemCheckIndicator, option, view
    )
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=indicator.center())
    assert widget.get_checked_items() == [("entity", "z")]
    qtbot.keyClick(view, Qt.Key.Key_Down)
    qtbot.waitUntil(lambda: context.navigation_coordinator.selected_id == "a")
    assert identities(widget) == [("entity", "a")]
    assert widget.get_checked_items() == [("entity", "z")]


@pytest.mark.parametrize("width", [360, 800])
def test_pinned_row_caption_themes_focus_and_narrow(
    context, qtbot, isolated_theme_manager, width
):
    from pathlib import Path

    from src.gui.delegates.explorer_delegate import PINNED_CAPTION

    widget = context.unified_list
    widget.set_data(
        [], [Entity(id="new", name="A very long authored title " * 8, type="Person")]
    )
    widget.search_bar.setText("unmatched")
    widget.set_active_item("entity", "new")
    context.resize(width, 600)
    context.show()
    template = Path("src/resources/main.qss").read_text("utf-8")
    for name in isolated_theme_manager.themes:
        isolated_theme_manager.set_theme(name, persist=False)
        widget.setStyleSheet(isolated_theme_manager.format_stylesheet(template))
        widget.list_widget.setFocus()
        widget.list_widget.doItemsLayout()
        index = widget._proxy_model.index(0, 0)
        rect = widget.list_widget.visualRect(index)
        assert rect.height() >= widget.fontMetrics().height() * 2
        assert PINNED_CAPTION in index.data(Qt.ItemDataRole.ToolTipRole)
        assert not widget.list_widget.viewport().grab().isNull()
        widget.list_widget.setEnabled(False)
        assert not widget.list_widget.viewport().grab().isNull()
        widget.list_widget.setEnabled(True)
