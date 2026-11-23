"""Graph authoring, scoped projections, and transactional history."""

from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QObject, QSettings

from src.app.coordinators.context_tag_coordinator import ContextTagCoordinator
from src.commands.entity_commands import CreateEntityCommand
from src.commands.event_commands import CreateEventCommand
from src.commands.graph_connection_command import GraphConnectionCommand
from src.commands.registry import get_command_types
from src.commands.relation_commands import AddRelationCommand
from src.core.authoring_scope import AuthoringScope
from src.core.command import CommandResult, is_graph_connection_result
from src.core.entities import Entity
from src.core.graph_temporal import GraphTemporalMode
from src.services.authored_relation_service import AuthoredRelationService
from src.services.command_execution import execute_with_history
from src.services.db_service import DatabaseService
from src.services.graph_data_service import GraphDataService
from src.services.graph_pair_service import graph_pair_relations
from src.services.history_service import HistoryService
from src.services.rag_service import RAGService
from src.services.search_service import EmbeddingProvider, SearchService

pytestmark = pytest.mark.ci_fast


class _WorldOwner(QObject):
    def __init__(self):
        super().__init__()
        self.current_world = SimpleNamespace(id="scoped-graph-test")


@pytest.mark.parametrize("kind", ["entity", "event"])
def test_create_connect_restore_undo_redo(db_service, tmp_path, kind):
    owner = _WorldOwner()
    setup = QSettings(str(tmp_path / "context.ini"), QSettings.Format.IniFormat)
    tags = ContextTagCoordinator(owner, setup)
    tags.set_available_tags(["Adventure", "Faction"])
    tags.set_scope_defaults(("Adventure",))
    source = CreateEntityCommand(
        {"name": "Scout", "type": "Character", "attributes": {"_tags": ["Adventure"]}}
    )
    assert source.execute(db_service).success
    target_data = {"name": "Council"}
    if kind == "entity":
        target_data["type"] = "Organization"
    else:
        target_data["lore_date"] = 36.0
    target, added = tags.graph_creation(kind, target_data)
    target_id = target.entity_id if kind == "entity" else target.event_id
    relation = AddRelationCommand(
        source.entity_id, target_id, "related", bidirectional=True
    )
    command = GraphConnectionCommand([target, relation], "Create and Connect")
    command.recovery = {
        "command_id": command.command_id,
        "item_type": kind,
        "item_id": target_id,
        "added_tags": added,
        "created_at": command.timestamp,
    }
    history = HistoryService(db_service, owner.current_world.id)
    for name, command_type in get_command_types().items():
        history.register_command_type(name, command_type)

    result = execute_with_history(db_service, history, command, "execute")
    assert result.success
    ids = set(result.data["graph_relation_ids"])
    assert len(ids) == 2
    assert not tags.snapshot()["history_count"]
    stacks = history.load_stacks()
    tags.restore_graph_recovery({**stacks, "world_id": owner.current_world.id})
    assert tags.snapshot()["history_count"] == 1

    payload = stacks["undo"][0]
    restored = GraphConnectionCommand.from_dict(payload["data"])
    restored.restore_base_state(payload["base"])
    assert [child.command_id for child in restored.commands] == [
        target.command_id,
        relation.command_id,
    ]
    assert {edge["id"] for edge in db_service.get_relations_for_item(target_id)} == ids
    assert execute_with_history(db_service, history, restored, "undo").success
    assert not db_service.get_relations_for_item(target_id)
    assert not db_service.get_entity(target_id) and not db_service.get_event(target_id)
    result = execute_with_history(db_service, history, restored, "redo")
    assert result.success
    assert set(result.data["graph_relation_ids"]) == ids
    record = db_service.get_entity(target_id) or db_service.get_event(target_id)
    assert record.tags == ["Adventure"]
    tags.clear_review_history()
    tags.restore_graph_recovery(
        {**history.load_stacks(), "world_id": owner.current_world.id}
    )
    assert not tags.snapshot()["history_count"]


def test_reciprocal_insert_failure_rolls_back_object_and_first_edge(
    db_service, monkeypatch
):
    source = Entity("Scout", "Character")
    db_service.insert_entity(source)
    target = CreateEventCommand(
        {"name": "Council", "lore_date": 1.0, "attributes": {"_tags": ["Adventure"]}}
    )
    relation = AddRelationCommand(
        source.id, target.event_id, "related", bidirectional=True
    )
    command = GraphConnectionCommand([target, relation])
    original = AuthoredRelationService.create

    def fail_reverse(self, source_id, target_id, *args, **kwargs):
        if source_id == target.event_id:
            raise ValueError("The reverse connection was rejected.")
        return original(self, source_id, target_id, *args, **kwargs)

    monkeypatch.setattr(AuthoredRelationService, "create", fail_reverse)
    history = HistoryService(db_service, "scoped-graph-test")
    result = execute_with_history(db_service, history, command, "execute")
    assert not result.success and result.data["graph_error"] == "rejected"
    assert not db_service.get_event(target.event_id)
    assert not db_service.get_relations_for_item(source.id)
    assert history.load_stacks() == {"undo": [], "redo": []}
    assert not command.is_executed


def test_failed_history_record_and_undo_restore_the_transaction(
    db_service, monkeypatch
):
    source = Entity("Scout", "Character")
    db_service.insert_entity(source)
    target = CreateEntityCommand({"name": "Faction", "type": "Organization"})
    relation = AddRelationCommand(target.entity_id, source.id, "related")
    command = GraphConnectionCommand([target, relation])
    history = HistoryService(db_service, "scoped-graph-test")

    def fail(*_args, **_kwargs):
        raise RuntimeError("Injected history or undo failure.")

    with monkeypatch.context() as patch:
        patch.setattr(history, "record_transition", fail)
        with pytest.raises(RuntimeError, match="Injected"):
            execute_with_history(db_service, history, command, "execute")
    assert not db_service.get_entity(target.entity_id)
    assert not db_service.get_relations_for_item(source.id)
    assert history.load_stacks() == {"undo": [], "redo": []}
    result = execute_with_history(db_service, history, command, "execute")
    relation_id = result.data["graph_relation_ids"][0]
    with monkeypatch.context() as patch:
        patch.setattr(db_service, "delete_entity", fail)
        with pytest.raises(RuntimeError, match="Injected"):
            execute_with_history(db_service, history, command, "undo")
    assert db_service.get_entity(target.entity_id)
    assert db_service.get_relation(relation_id)
    assert command.is_executed


def test_scope_checks_both_endpoints_after_temporal_evaluation(db_service):
    source = Entity("Scout", "Character", attributes={"_tags": ["A", "B"]})
    target = Entity("Faction", "Organization", attributes={"_tags": ["A", "B"]})
    outside = Entity("Other", "Organization", attributes={"_tags": ["A"]})
    for item in (source, target, outside):
        assert CreateEntityCommand(item.to_dict()).execute(db_service).success
    fixed = {"valid_from": 25.0}
    assert (
        AddRelationCommand(source.id, target.id, "member_of", fixed)
        .execute(db_service)
        .success
    )
    assert (
        AddRelationCommand(source.id, outside.id, "related").execute(db_service).success
    )
    scope = AuthoringScope(("A", "B"), "all")
    service = GraphDataService()
    nodes, edges = service.get_graph_data(
        db_service,
        lore_time=10.0,
        temporal_mode=GraphTemporalMode.AT_PLAYHEAD,
        authoring_scope=scope,
    )
    assert {node["id"] for node in nodes} == {source.id, target.id}
    assert not edges
    _, edges = service.get_graph_data(
        db_service,
        lore_time=30.0,
        temporal_mode=GraphTemporalMode.AT_PLAYHEAD,
        authoring_scope=scope,
    )
    assert [edge["rel_type"] for edge in edges] == ["member_of"]
    assert graph_pair_relations(db_service, target.id, source.id, 10.0)


def test_search_excludes_canonical_outside_candidates_before_top_k(tmp_path):
    class Provider(EmbeddingProvider):
        def embed(self, texts):
            return np.array(
                [[0.8, 0.6] if "Scout" in text else [1.0, 0.0] for text in texts],
                dtype=np.float32,
            )

        def get_dimension(self):
            return 2

        def get_model_name(self):
            return "scope-test"

    database_path = str(tmp_path / "search.kraken")
    db = DatabaseService(database_path)
    db.connect()
    try:
        scout = CreateEntityCommand(
            {
                "name": "Scout",
                "type": "Character",
                "attributes": {"_tags": ["Adventure"]},
            }
        )
        outsider = CreateEntityCommand({"name": "Outsider", "type": "Character"})
        assert scout.execute(db).success and outsider.execute(db).success
        provider = Provider()
        index = SearchService(db.require_connection(), provider)
        index.index_entity(scout.entity_id)
        index.index_entity(outsider.entity_id)
        search = RAGService(database_path, embedding_provider=provider)
        scope = AuthoringScope(("Adventure",))
        unscoped = search.search("Find a guide", top_k=1)
        assert [row["object_id"] for row in unscoped] == [outsider.entity_id]
        scoped = search.search("Find a guide", top_k=1, scope=scope)
        assert [row["object_id"] for row in scoped] == [scout.entity_id]
        named = search.search("Scout and Outsider", top_k=0, scope=scope)
        assert [row["object_id"] for row in named] == [scout.entity_id]
    finally:
        db.close()


def test_graph_recovery_recognizes_the_persistent_event_timing_wrapper(tmp_path):
    owner = _WorldOwner()
    settings = QSettings(str(tmp_path / "context.ini"), QSettings.Format.IniFormat)
    tags = ContextTagCoordinator(owner, settings)
    record = {
        "command_id": "outer",
        "item_type": "event",
        "item_id": "council",
        "added_tags": ["Adventure"],
        "created_at": 1.0,
    }
    payload = {
        "type": "ApplyEventTimingPlanCommand",
        "data": {
            "command_type": "GraphConnectionCommand",
            "command": {"graph_context_tags": record},
        },
    }
    result = CommandResult(
        True,
        command_name="Redo_ApplyEventTimingPlanCommand",
        data={"command_state": payload},
    )
    assert is_graph_connection_result(result)
    tags.restore_graph_recovery({"world_id": owner.current_world.id, "undo": [payload]})
    assert tags.snapshot()["history_count"] == 1
