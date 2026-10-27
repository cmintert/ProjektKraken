"""Expanded inspection resolves real controls without running their actions."""

from __future__ import annotations

import ast
import gc
import json
from pathlib import Path

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtGui import QHelpEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMenu,
    QMenuBar,
    QPushButton,
    QTabBar,
    QToolButton,
    QWidget,
)

from src.app.help_composition import HelpSurfaceBindings
from src.app.help_declared_bindings import bind_declared_action, bind_declared_widget
from src.core.help_inspection_inventory import check_inventory, symbol_fingerprint
from src.gui.utils.help_context import declare_inspection
from src.gui.workspace import WorkspaceShell
from src.services.help_bundle_service import HelpBundleService
from src.services.help_search_service import HelpSearchService
from tests.unit import test_help_coordinator as existing
from tests.unit import test_unified_list as explorer_tests

help_setup = existing.help_setup
generated_root = existing.generated_root
unified_list = explorer_tests.unified_list
pytestmark = pytest.mark.ci_fast
ROOT = Path(__file__).resolve().parents[2]


def test_map_event_endpoint_inspection_keeps_the_reference_draft(help_setup, qapp):
    from src.core.events import Event
    from src.core.map import MapLayerNode
    from src.core.temporal_context import TemporalResolutionContext
    from src.gui.dialogs.temporal_validity_dialog import TemporalValidityDialog

    coordinator, _registry, owner, _, _ = help_setup
    node = MapLayerNode(
        "Castle",
        "marker",
        attributes={
            "temporal": {
                "schema": 2,
                "start": {"anchor": {"anchor_id": "event:e", "endpoint": "start"}},
                "end": {"status": "open"},
            }
        },
    )
    dialog = TemporalValidityDialog(
        node,
        owner,
        temporal_context=TemporalResolutionContext.build(
            [Event("Foundation", id="e", lore_date=100)], None
        ),
    )
    bindings = HelpSurfaceBindings(coordinator)
    for widget in [dialog, *dialog.findChildren(QWidget)]:
        bindings.bind(widget)
    dialog._event_controls["start"].disclosure.setChecked(True)
    dialog.show()
    dialog.activateWindow()
    target = dialog._event_controls["start"].endpoint
    target.setFocus()
    qapp.processEvents()
    before = dialog.properties()
    QTest.keyClick(
        target,
        Qt.Key.Key_F1,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    qapp.processEvents()
    assert coordinator.inspection._topic_id == "map.visibility"
    assert coordinator.inspection._excerpt_target == "help-inspect-map-anchor-endpoint"
    assert dialog.properties() == before
    coordinator.inspection.dismiss()
    dialog.close()


def test_every_declared_explanation_is_generated_and_bounded(generated_root):
    inventory = json.loads((ROOT / "docs/help-inspection.json").read_text("utf-8"))
    service = HelpBundleService(root=generated_root / "docs/_build/help")
    service.validate()
    for record in inventory["bindings"]:
        content = service.load_inspection_excerpt(record["topic_id"], record["target"])
        assert content and content.strip(), record["id"]
        assert "<script" not in content
    assert check_inventory(ROOT) == []


def test_control_search_lands_on_concise_explanation(generated_root):
    service = HelpBundleService(root=generated_root / "docs/_build/help")
    results = HelpSearchService(service.search_documents()).search("brush hardness")
    assert any(
        result.fragment == "help-inspect-raster-hardness" for result in results[:5]
    )


def test_activity_help_does_not_switch_workspace_or_change_draft(help_setup, qapp):
    from src.gui.workspace.activity_bar import ActivityBar

    coordinator, registry, owner, _, text = help_setup
    rail = ActivityBar("Workspaces", owner)
    rail.setOrientation(Qt.Orientation.Vertical)
    rail.configure_workspaces()
    rail.set_entries([("overview", "Overview"), ("writing", "Writing")], "overview")
    owner.layout().addWidget(rail)
    bindings = HelpSurfaceBindings(coordinator)
    for widget in [rail, *rail.findChildren(QWidget)]:
        bindings.bind(widget)
    requests = []
    rail.workspace_requested.connect(requests.append)
    button = rail.widgetForAction(rail.workspace_actions["writing"])
    assert registry.candidates(button)[0][0] == "workspace.navigation"
    meaning = registry.inspection_for(button)[1]
    assert meaning.meaning == "workspace.activity"
    snapshot = text.toPlainText(), text.document(), text.document().availableUndoSteps()
    owner.resize(700, 700)
    owner.activateWindow()
    qapp.processEvents()
    button.setFocus()
    qapp.processEvents()
    assert button.hasFocus()
    QTest.keyClick(button, Qt.Key.Key_F1)
    qapp.processEvents()
    assert coordinator.history[-1].uri.endswith("#help-workspace-navigation")
    assert not requests
    assert snapshot == (
        text.toPlainText(),
        text.document(),
        text.document().availableUndoSteps(),
    )


@pytest.mark.parametrize("mode", ["pointer", "focused"])
def test_workspace_close_inspection_preserves_live_panel_across_recreation(
    help_setup, qapp, mode
):
    coordinator, registry, owner, _, text = help_setup
    shell = WorkspaceShell(owner)
    owner.layout().addWidget(shell)
    shell.register_panel("draft", "Draft", text, "center")
    # Keep another tab so accidental activation/reordering is observable.
    shell.register_panel("other", "Other", QWidget(), "center")
    owner.move(0, 0)
    owner.resize(700, 600)
    cursor = text.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    cursor.insertText(" still unsaved")
    cursor.setPosition(2)
    cursor.setPosition(9, cursor.MoveMode.KeepAnchor)
    text.setTextCursor(cursor)
    bindings = HelpSurfaceBindings(coordinator)
    qapp.installEventFilter(bindings)

    def draft_snapshot():
        return (
            text.document(),
            text.toPlainText(),
            text.document().isModified(),
            text.document().availableUndoSteps(),
            text.textCursor().position(),
            text.textCursor().anchor(),
            text.verticalScrollBar().value(),
        )

    try:
        for zone in ("center", "left", "right", "bottom"):
            shell.move_panel("draft", zone)
            for _generation in range(2):
                shell.show_panel("draft")
                shell.horizontal_splitter.setSizes([150, 350, 150])
                shell.vertical_splitter.setSizes([350, 150])
                qapp.processEvents()
                pane = shell.panes[zone]
                button = pane.tabs.tabBar().tabButton(
                    pane.index_of("draft"), QTabBar.ButtonPosition.RightSide
                )
                assert isinstance(button, QToolButton)
                registration = registry.inspection_for(button)[1]
                assert registration.meaning == "workspace.close-panel"
                assert registration.topic_id == "workspace.navigation"
                assert (
                    registration.excerpt_target == "help-inspect-workspace-close-panel"
                )
                snapshot = draft_snapshot()
                layout = shell.capture_layout()
                if mode == "pointer":
                    coordinator.inspection.enter()
                    point = button.mapToGlobal(button.rect().center())
                    QTest.mouseClick(
                        owner.windowHandle(),
                        Qt.MouseButton.LeftButton,
                        pos=owner.mapFromGlobal(point),
                    )
                else:
                    owner.activateWindow()
                    button.setFocus()
                    qapp.processEvents()
                    assert button.hasFocus()
                    QTest.keyClick(
                        button,
                        Qt.Key.Key_F1,
                        Qt.KeyboardModifier.ControlModifier
                        | Qt.KeyboardModifier.ShiftModifier,
                    )
                qapp.processEvents()
                assert coordinator.inspection._topic_id == "workspace.navigation"
                assert (
                    coordinator.inspection._excerpt_target
                    == "help-inspect-workspace-close-panel"
                )
                assert QApplication.activePopupWidget() is not None, (zone, _generation)
                assert shell.capture_layout() == layout
                assert draft_snapshot() == snapshot
                coordinator.inspection.dismiss()
                qapp.processEvents()
                QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                assert not shell.is_panel_open("draft")
                shell.show_panel("draft")
                qapp.processEvents()
                assert shell.panel("draft") is text
                assert draft_snapshot() == snapshot
    finally:
        coordinator.inspection.dismiss()
        qapp.removeEventFilter(bindings)


def test_explorer_buttons_and_creation_actions_have_specific_help(
    help_setup, unified_list, qapp
):
    coordinator, registry, owner, _, _ = help_setup
    owner.layout().addWidget(unified_list)
    bindings = HelpSurfaceBindings(coordinator)
    for widget in [unified_list, *unified_list.findChildren(QPushButton)]:
        bindings.bind(widget)
    create = registry.inspection_for(unified_list.btn_new)
    delete = registry.inspection_for(unified_list.btn_delete)
    assert create[1].topic_id == "authoring.create"
    assert delete[1].topic_id == "authoring.delete"
    for action in (
        unified_list.action_create_event,
        unified_list.action_create_entity,
        unified_list.action_create_map,
    ):
        bind_declared_action(registry, action, unified_list)
        assert registry.inspection_action(action) is not None
    gc.collect()
    assert shiboken6.isValid(unified_list.action_create_event)
    assert shiboken6.isValid(unified_list.new_menu)


def test_menu_inspection_never_triggers_action(help_setup, qapp):
    coordinator, registry, owner, _, _ = help_setup
    record = next(
        r
        for r in json.loads((ROOT / "docs/help-inspection.json").read_text("utf-8"))[
            "bindings"
        ]
        if r["id"] == "feature.geometry"
    )
    menu = QMenu(owner)
    action = declare_inspection(
        menu.addAction("Edit border"),
        "|".join((record["id"], record["topic_id"], record["target"])),
    )
    action.setCheckable(True)
    action.setChecked(True)
    calls = []
    action.triggered.connect(lambda: calls.append(True))
    bind_declared_action(registry, action, menu)
    coordinator.inspection.enter()
    menu.popup(owner.mapToGlobal(QPoint(20, 20)))
    qapp.processEvents()
    QTest.mouseClick(
        menu.windowHandle(),
        Qt.MouseButton.LeftButton,
        pos=menu.actionGeometry(action).center(),
    )
    qapp.processEvents()
    assert calls == []
    assert action.isChecked()
    assert QApplication.activePopupWidget() is not None
    assert coordinator.inspection._topic_id == "map.historical-geometry"
    coordinator.inspection.dismiss()


@pytest.mark.parametrize("menu_type", [QMenu, QMenuBar])
def test_focused_shortcut_explains_active_menu_action_without_activation(
    help_setup, qapp, menu_type
):
    coordinator, registry, owner, _, text = help_setup
    menu = menu_type(owner)
    action = declare_inspection(
        menu.addAction("Create"),
        "test.create|authoring.create|help-authoring-create",
    )
    action.setCheckable(True)
    action.setChecked(True)
    bind_declared_action(registry, action, menu)
    calls = []
    action.triggered.connect(lambda: calls.append(True))
    snapshot = (text.document(), text.toPlainText(), text.textCursor().position())
    if isinstance(menu, QMenu):
        menu.popup(owner.mapToGlobal(QPoint(20, 20)))
    else:
        owner.layout().setMenuBar(menu)
        menu.show()
        owner.activateWindow()
        menu.setFocus(Qt.FocusReason.MenuBarFocusReason)
    menu.setActiveAction(action)
    qapp.processEvents()
    QTest.keyClick(
        menu.windowHandle() or owner.windowHandle(),
        Qt.Key.Key_F1,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    qapp.processEvents()
    popup = QApplication.activePopupWidget()
    assert popup is not None and popup is not menu
    assert coordinator.inspection._topic_id == "authoring.create"
    assert coordinator.inspection._excerpt_target == "help-authoring-create"
    assert calls == []
    assert action.isChecked()
    assert not coordinator.viewer.isVisible()
    assert snapshot == (
        text.document(),
        text.toPlainText(),
        text.textCursor().position(),
    )
    QTest.keyClick(popup.windowHandle(), Qt.Key.Key_Escape)
    qapp.processEvents()
    assert QApplication.activePopupWidget() is None


def test_focused_shortcut_exempt_menu_action_does_not_reuse_previous_explanation(
    help_setup, qapp
):
    coordinator, registry, owner, _, _ = help_setup
    menu = QMenu(owner)
    mapped = declare_inspection(
        menu.addAction("Create"),
        "test.create|authoring.create|help-authoring-create",
    )
    bind_declared_action(registry, mapped, menu)
    exempt = menu.addAction("Exempt")
    calls = []
    exempt.triggered.connect(lambda: calls.append(True))
    for action in (mapped, exempt):
        menu.popup(owner.mapToGlobal(QPoint(20, 20)))
        menu.setActiveAction(action)
        qapp.processEvents()
        QTest.keyClick(
            menu.windowHandle(),
            Qt.Key.Key_F1,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        qapp.processEvents()
        popup = QApplication.activePopupWidget()
        if action is mapped:
            assert popup is not None and popup is not menu
            coordinator.inspection.dismiss()
        else:
            assert popup is not None and popup is not menu
            assert coordinator.inspection._topic_id is None
            coordinator.inspection.dismiss()
        qapp.processEvents()
    assert calls == []
    menu.hide()


def test_disabled_hover_uses_event_position_not_stale_cursor(help_setup, qapp):
    coordinator, registry, owner, panel, _ = help_setup
    button = QPushButton("Mapped", panel)
    panel.layout().addWidget(button)
    registry.register_inspection(button, "event.duration", "event.timing")
    button.setEnabled(False)
    button.show()
    qapp.processEvents()
    coordinator.inspection.enter()
    point = button.mapToGlobal(button.rect().center())
    query = QHelpEvent(QEvent.Type.QueryWhatsThis, button.rect().center(), point)
    QApplication.sendEvent(button, query)
    assert query.isAccepted()
    QTest.mouseMove(owner.windowHandle(), owner.mapFromGlobal(point))
    qapp.processEvents()
    assert QApplication.overrideCursor().shape() == Qt.CursorShape.WhatsThisCursor
    coordinator.inspection.dismiss()


def test_standard_dialog_buttons_use_roles_and_task_destination(help_setup):
    coordinator, registry, _, panel, _ = help_setup
    record = next(
        r
        for r in json.loads((ROOT / "docs/help-inspection.json").read_text("utf-8"))[
            "bindings"
        ]
        if r["kind"] == "QDialogButtonBox"
    )
    box = declare_inspection(
        QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            panel,
        ),
        "|".join((record["id"], record["topic_id"], record["target"])),
    )
    bind_declared_widget(registry, box)
    accept = registry.inspection_for(box.button(QDialogButtonBox.StandardButton.Ok))[1]
    cancel = registry.inspection_for(
        box.button(QDialogButtonBox.StandardButton.Cancel)
    )[1]
    assert accept.excerpt_target == "help-inspect-dialog-accept"
    assert cancel.excerpt_target == "help-inspect-dialog-cancel"
    assert coordinator.service.load_inspection_excerpt(
        accept.topic_id, accept.excerpt_target
    )


def test_review_fingerprint_ignores_format_but_detects_behavior():
    original = symbol_fingerprint(ast.parse("def act():\n    return 1\n"), "act")
    assert (
        symbol_fingerprint(
            ast.parse("def act():\n    # layout\n    return (1)\n"), "act"
        )
        == original
    )
    assert (
        symbol_fingerprint(ast.parse("def act():\n    return 2\n"), "act") != original
    )


def test_action_owner_teardown_releases_cached_native_handles(help_setup, qapp):
    _, registry, owner, _, _ = help_setup
    menu = QMenu(owner)
    action = declare_inspection(
        menu.addAction("Create"),
        "test.create|authoring.create|help-authoring-create",
    )
    bind_declared_action(registry, action, menu)
    token = id(action)
    assert token in registry._action_handles
    menu.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert token not in registry._action_handles
    assert registry.inspection_action(action) is None


def test_exempt_menu_wrappers_survive_binding_scan_until_native_teardown(help_setup):
    _, registry, owner, _, _ = help_setup
    menu = QMenu(owner)
    submenu = menu.addMenu("No declaration")
    action = submenu.menuAction()
    bind_declared_action(registry, action, menu)
    gc.collect()
    assert shiboken6.isValid(submenu)
    assert registry.inspection_action(action) is None


def test_form_label_and_default_action_reuse_exact_meaning(help_setup):
    _, registry, owner, _, _ = help_setup
    page = QWidget(owner)
    form = QFormLayout(page)
    field = declare_inspection(
        QLineEdit(page), "test.field|authoring.create|help-authoring-create"
    )
    form.addRow("Displayed label", field)
    bind_declared_widget(registry, field)
    assert registry.inspection_for(form.labelForField(field))[1].meaning == "test.field"
    menu = QMenu(page)
    action = declare_inspection(
        menu.addAction("Displayed action"),
        "test.action|writing.links|help-writing-links",
    )
    button = QToolButton(page)
    button.setDefaultAction(action)
    bind_declared_widget(registry, button)
    assert registry.inspection_for(button)[1].meaning == "test.action"


def test_overflow_equivalent_wins_over_generic_proxy_declaration(help_setup):
    _, registry, owner, _, _ = help_setup
    button = declare_inspection(
        QPushButton("Original", owner),
        "test.original|writing.links|help-writing-links",
    )
    bind_declared_widget(registry, button)
    menu = QMenu(owner)
    proxy = declare_inspection(
        menu.addAction("Proxy"), "test.generic|manual.home|help-manual-home"
    )
    proxy.setProperty("krakenHelpEquivalent", button)
    bind_declared_action(registry, proxy, menu)
    assert registry.inspection_action(proxy)[0] is owner
    assert registry.inspection_action(proxy)[1].meaning == "test.original"


def test_new_input_factory_requires_declaration_or_reason(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/help-topics.json").write_text('{"topics": []}')
    (tmp_path / "docs/help-inspection.json").write_text(
        '{"bindings": [], "source_reviews": []}'
    )
    source = tmp_path / "src/gui/new_panel.py"
    source.parent.mkdir(parents=True)
    source.write_text("def build():\n    return QPushButton('New operation')\n")
    assert any("declare inspection" in error for error in check_inventory(tmp_path))


def test_inspection_resolves_nested_graph_child_input(help_setup, qapp):
    from src.gui.widgets.graph_view.graph_widget import GraphWidget

    coordinator, registry, owner, _, _ = help_setup
    graph = GraphWidget(owner)
    owner.layout().addWidget(graph)
    bindings = HelpSurfaceBindings(coordinator)
    for widget in [graph, *graph.findChildren(QWidget)]:
        bindings.bind(widget)
    engine = graph._web_view._web_view
    graph.show()
    owner.resize(700, 650)
    qapp.processEvents()
    coordinator.inspection.enter()
    point = engine.mapToGlobal(engine.rect().center())
    QTest.mouseClick(
        owner.windowHandle(),
        Qt.MouseButton.LeftButton,
        pos=owner.mapFromGlobal(point),
    )
    qapp.processEvents()
    assert QApplication.activePopupWidget() is not None
    assert coordinator.inspection._topic_id == "graph.exploring"
    assert registry.inspection_for(engine)[1].topic_id == "graph.exploring"
    coordinator.inspection.dismiss()
    graph.close()


def test_drift_missing_target_and_binding_fail_with_actionable_diagnostics(tmp_path):
    (tmp_path / "docs/user").mkdir(parents=True)
    (tmp_path / "src").mkdir()
    source = "def act():\n    return 'control|task|excerpt'\n"
    (tmp_path / "src/control.py").write_text(source)
    (tmp_path / "docs/user/task.md").write_text("(excerpt)=\n\nMeaning\n")
    (tmp_path / "docs/help-topics.json").write_text(
        json.dumps({"topics": [{"id": "task", "source": "task.md"}]})
    )
    catalog = {
        "bindings": [
            {
                "id": "control",
                "topic_id": "task",
                "target": "excerpt",
                "source": "src/control.py",
                "symbol": "act",
            }
        ],
        "source_reviews": [
            {
                "source": "src/control.py",
                "symbol": "act",
                "sha256": symbol_fingerprint(ast.parse(source), "act"),
            }
        ],
    }
    (tmp_path / "docs/help-inspection.json").write_text(json.dumps(catalog))
    assert check_inventory(tmp_path) == []
    (tmp_path / "src/control.py").write_text(
        source.replace("return", "print('changed'); return")
    )
    assert any(
        "Help impact review required" in error for error in check_inventory(tmp_path)
    )
    (tmp_path / "docs/user/task.md").write_text("No target")
    assert any(
        "missing canonical explanation" in error for error in check_inventory(tmp_path)
    )
    (tmp_path / "src/control.py").write_text("def act():\n    return 0\n")
    assert any(
        "missing construction declaration" in error
        for error in check_inventory(tmp_path)
    )
