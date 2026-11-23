"""Scope persistence and presentation without canonical history changes."""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, QSettings
from PySide6.QtWidgets import QWidget

from src.app.coordinators.authoring_scope_coordinator import AuthoringScopeCoordinator
from src.app.coordinators.context_tag_coordinator import ContextTagCoordinator
from src.app.coordinators.scoped_history import ScopedHistory
from src.core.authoring_scope import AuthoringScope
from src.core.entities import Entity
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext
from src.gui.dialogs.graph_connection_dialog import GraphConnectionDialog
from src.gui.widgets.graph_view.graph_widget import GraphWidget
from src.gui.widgets.timeline import TimelineWidget
from src.gui.widgets.unified_list import UnifiedListWidget

pytestmark = pytest.mark.ci_fast


def test_any_requires_explicit_default_and_all_uses_all_tags():
    with pytest.raises(ValueError, match="creation tags"):
        AuthoringScope(("a", "b"))
    any_scope = AuthoringScope(("a", "b"), "any", ("a",))
    all_scope = AuthoringScope(("a", "b"), "all")
    assert any_scope.matches(["b"])
    assert not any_scope.matches(["B"])
    assert not all_scope.matches(["b"])
    assert all_scope.matches(["a", "b"])
    assert all_scope.creation_tags == ("a", "b")
    assert AuthoringScope.from_dict(any_scope.to_dict()) == any_scope


def test_scope_restores_per_world_and_clear_keeps_other_world_settings(
    qtbot, tmp_path, monkeypatch
):
    settings = QSettings(str(tmp_path / "scope.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(
        "src.app.coordinators.authoring_scope_coordinator.QSettings",
        lambda *_args: settings,
    )
    window = QWidget()
    qtbot.addWidget(window)

    def catalog():
        return ["Adventure", "Faction"]

    one = AuthoringScopeCoordinator("one", catalog, window)
    two = AuthoringScopeCoordinator("two", catalog, window)
    selected = AuthoringScope(("Adventure", "Faction"), "any", ("Adventure",))
    one.set_scope(selected)
    two.set_scope(AuthoringScope(("Faction",)))
    restored = AuthoringScopeCoordinator("one", catalog, window)
    assert restored.scope == selected
    restored.set_scope(AuthoringScope())
    assert AuthoringScopeCoordinator("one", catalog, window).scope == AuthoringScope()
    assert AuthoringScopeCoordinator("two", catalog, window).scope == two.scope


def test_follow_scope_and_explicit_custom_survive_reopen(tmp_path):
    owner = QObject()
    owner.current_world = SimpleNamespace(id="scope")
    settings = QSettings(str(tmp_path / "context.ini"), QSettings.Format.IniFormat)
    tags = ContextTagCoordinator(owner, settings)
    tags.set_available_tags(["Adventure"])
    tags.set_scope_defaults(("Adventure",))
    tags.follow_scope()
    assert tags.graph_creation("entity", {"name": "Scout", "type": "Character"})[1] == [
        "Adventure"
    ]
    tags.save_tags(["Custom"])
    tags.enable()
    restored = ContextTagCoordinator(owner, settings)
    restored.set_scope_defaults(("Adventure",))
    assert restored.snapshot()["policy"] == "custom"
    assert restored.graph_creation("entity", {"name": "Scout", "type": "Character"})[
        1
    ] == ["Custom"]
    restored.follow_scope()
    assert not restored.is_active
    restored.set_available_tags(["Adventure"])
    assert restored.is_active


def test_explorer_intersects_local_search_and_preserves_active_pin(qtbot):
    explorer = UnifiedListWidget()
    qtbot.addWidget(explorer)
    scoped = Entity("Scout", "Character", attributes={"_tags": ["Adventure"]})
    outside = Entity("Anchor", "Location")
    explorer.set_data([], [scoped, outside])
    explorer.set_active_item("entity", outside.id)
    explorer.set_authoring_scope(AuthoringScope(("Adventure",)))
    assert explorer._proxy_model.rowCount() == 2
    explorer._proxy_model.set_search_term("missing")
    assert explorer._proxy_model.rowCount() == 1
    explorer.set_authoring_scope(AuthoringScope())
    assert explorer._proxy_model.rowCount() == 1


def test_timeline_reveals_only_relevant_events_with_full_context(qtbot):
    timeline = TimelineWidget()
    qtbot.addWidget(timeline)
    visible = Event("Council", 50.0, attributes={"_tags": ["Adventure"]})
    related = Event("Foundation", 12.0)
    unrelated = Event("Other", 1.0)
    events = [unrelated, related, visible]
    timeline.view.set_temporal_context(TemporalResolutionContext.build(events, None))
    timeline.view.set_playhead_time(41.0)
    history = ScopedHistory(timeline, lambda: events)
    history.scope_changed(AuthoringScope(("Adventure",)))
    history.selected("entity", "scout", "selected")
    history.relations(
        "entity",
        "scout",
        [{"source_id": related.id, "target_id": "scout", "rel_type": "related"}],
    )
    assert [event.id for event in timeline.view.events] == [visible.id]
    history.toggle()
    assert [event.id for event in timeline.view.events] == [related.id, visible.id]
    assert timeline.get_playhead_time() == 41.0
    assert len(timeline.view._temporal_context.events()) == 3
    history.selected("event", visible.id, "selected")
    assert [event.id for event in timeline.view.events] == [visible.id]


def test_connection_dialog_preserves_pending_input_and_protects_mentions(qtbot):
    timeline = TimelineWidget()
    qtbot.addWidget(timeline)
    dialog = GraphConnectionDialog("Scout", ["mentions", "member_of"], timeline)
    qtbot.addWidget(dialog)
    dialog.set_target("Faction", awaiting_relations=True)
    dialog.type_field.setCurrentText("related")
    assert not dialog.save.isEnabled()
    dialog.pair_ready([("read-only", {"rel_type": "mentions"})])
    dialog.existing.setCurrentIndex(1)
    assert not dialog.edit_button.isEnabled()
    assert dialog.save.isEnabled()
    dialog.set_pending(True)
    dialog.set_pending(False, "Rejected")
    assert dialog.save.isEnabled()
    assert dialog.type_field.currentText() == "related"


def test_graph_reveal_respects_world_scope_and_temporal_presentation(qtbot):
    graph = GraphWidget()
    qtbot.addWidget(graph)
    graph.set_authoring_scope(AuthoringScope(("Adventure",)))
    graph._advanced_filter_config["rel_types"] = {"include": ["member_of"]}
    nodes = [
        {"id": "scout", "name": "Scout", "tags": ["Adventure"]},
        {"id": "faction", "name": "Faction", "tags": ["Adventure"]},
        {"id": "outside", "name": "Outside", "tags": ["Other"]},
    ]
    edges = [
        {
            "id": "saved",
            "source_id": "scout",
            "target_id": "faction",
            "rel_type": "related",
        },
        {
            "id": "external",
            "source_id": "scout",
            "target_id": "outside",
            "rel_type": "related",
        },
        {
            "id": "possible",
            "source_id": "scout",
            "target_id": "faction",
            "rel_type": "related",
            "validity_status": "possible",
        },
    ]
    graph.display_graph(nodes, edges)
    assert not graph.visible_node_ids
    local, excluded = graph.show_saved_relations(
        frozenset({"saved", "external", "possible"})
    )
    assert local == ("relation type",) and excluded == 2
    assert graph.visible_node_ids == {"scout", "faction"}
    graph.authoring_context_changed()
    assert not graph.visible_node_ids
    assert graph.get_filter_config()["rel_types"] == ["member_of"]
