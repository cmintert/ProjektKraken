"""Tests for worker-owned single-item Obsidian exports."""

from pathlib import Path
from unittest.mock import MagicMock

from src.core.entities import Entity
from src.services.worker import DatabaseWorker


def _worker_with_entity(entity: Entity) -> DatabaseWorker:
    """Create a database worker with a mocked service containing one entity."""
    worker = DatabaseWorker(":memory:")
    db_service = MagicMock()
    db_service.get_entity.return_value = entity
    db_service.get_all_entities.return_value = [entity]
    db_service.get_all_events.return_value = []
    db_service.get_relations.return_value = []
    worker.db_service = db_service
    return worker


def test_prepare_single_obsidian_export_emits_serializable_snapshot() -> None:
    """Preparation should emit item identity without exposing the domain object."""
    entity = Entity(name="The Kraken", type="creature", id="entity-1")
    worker = _worker_with_entity(entity)
    snapshots: list[dict[str, object]] = []
    worker.obsidian_export_prepared.connect(snapshots.append)

    worker.prepare_single_obsidian_export("entity", entity.id)

    assert snapshots == [
        {
            "item_type": "entity",
            "item_id": entity.id,
            "item_name": entity.name,
            "error": "",
        }
    ]


def test_run_single_obsidian_export_writes_user_selected_path(
    tmp_path: Path,
) -> None:
    """The worker should own DB reads and write the selected Markdown file."""
    entity = Entity(
        name="The Kraken",
        type="creature",
        description="It waits beneath the waves.",
        id="entity-1",
    )
    worker = _worker_with_entity(entity)
    snapshots: list[dict[str, object]] = []
    worker.obsidian_export_finished.connect(snapshots.append)
    target_path = tmp_path / "Chosen Name.md"

    worker.run_single_obsidian_export(
        "entity",
        entity.id,
        str(target_path),
    )

    assert target_path.exists()
    assert "It waits beneath the waves." in target_path.read_text(encoding="utf-8")
    assert snapshots == [
        {
            "success": True,
            "item_type": "entity",
            "item_id": entity.id,
            "item_name": entity.name,
            "file_path": str(target_path.resolve()),
            "error": "",
        }
    ]


def test_embedding_stats_failure_emits_safe_snapshot_and_error() -> None:
    """A statistics read failure must not escape the worker slot."""
    worker = DatabaseWorker(":memory:")
    db_service = MagicMock()
    db_service.get_embedding_stats.side_effect = RuntimeError("broken")
    worker.db_service = db_service
    snapshots: list[dict[str, object]] = []
    errors: list[str] = []
    worker.embedding_stats_loaded.connect(snapshots.append)
    worker.error_occurred.connect(errors.append)

    worker.load_embedding_stats()

    assert snapshots == [{"count": 0, "last_updated": None}]
    assert errors == ["Failed to load semantic-index statistics."]
