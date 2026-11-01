"""Real worker dispatch persists one batch and restores it after reopening."""

from types import SimpleNamespace

import pytest

from src.app.command_coordinator import CommandCoordinator
from src.commands.batch_metadata_command import BatchMetadataCommand
from src.commands.registry import get_command_types
from src.core.batch_metadata import MetadataOperation
from src.core.entities import Entity
from src.core.events import Event
from src.services.batch_metadata_service import prepare_metadata
from src.services.db_service import DatabaseService
from src.services.history_service import HistoryService
from src.services.worker import DatabaseWorker

pytestmark = pytest.mark.ci_fast


def test_worker_batch_is_one_undo_entry_and_survives_reopening(tmp_path, qapp):
    path = str(tmp_path / "world.kraken")
    db = DatabaseService(path)
    db.connect()
    db.insert_entity(Entity("Person", "character", id="person"))
    db.insert_event(Event("Council", 4, id="council"))
    targets = [("entity", "person"), ("event", "council")]
    operation = MetadataOperation("add_tags", tags=["shared"])
    preview = prepare_metadata(db, targets, operation)
    command = BatchMetadataCommand(targets, operation.to_dict(), preview["rows"])
    worker = DatabaseWorker(path, get_command_types())
    worker.db_service = db
    worker.history_service = HistoryService(db, "world")
    worker.history_service.register_command_type(
        "BatchMetadataCommand", BatchMetadataCommand
    )
    coordinator = CommandCoordinator(SimpleNamespace(current_world=None))
    coordinator.command_requested.connect(worker.run_command)
    coordinator.undo_requested.connect(worker.run_undo)
    coordinator.redo_requested.connect(worker.run_redo)
    worker.command_finished.connect(coordinator.on_command_result)
    results = []
    worker.command_finished.connect(results.append)
    try:
        coordinator.execute_command(command)
        assert results[-1].success
        assert len(coordinator.undo_stack) == 1
        assert len(worker.history_service.load_recent_history()) == 1
        coordinator.undo()
        assert results[-1].success
        assert not db.get_entity("person").tags and not db.get_event("council").tags
        assert len(coordinator.redo_stack) == 1 and not coordinator.undo_stack
        coordinator.redo()
        assert results[-1].success
        assert len(coordinator.undo_stack) == 1 and not coordinator.redo_stack
        assert db.get_entity("person").tags == ["shared"]
        assert db.get_event("council").tags == ["shared"]
    finally:
        worker.db_service = None
        worker.history_service = None
        db.close()
    reopened = DatabaseService(path)
    reopened.connect()
    try:
        history = HistoryService(reopened, "world")
        history.register_command_type("BatchMetadataCommand", BatchMetadataCommand)
        (restored,) = history.load_recent_history()
        assert restored.undo(reopened).success
        assert "_tags" not in reopened.get_entity("person").attributes
        assert "_tags" not in reopened.get_event("council").attributes
        assert restored.execute(reopened).success
        assert reopened.get_tags_for_entity("person")[0]["name"] == "shared"
        assert reopened.get_tags_for_event("council")[0]["name"] == "shared"
    finally:
        reopened.close()
