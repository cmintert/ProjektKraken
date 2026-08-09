"""Startup boundary tests for external world databases."""

from unittest.mock import MagicMock, patch

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from src.app.worker_manager import WorkerManager
from src.core.world import EXTERNAL_DATABASE_STORAGE, World, WorldManager
from src.services.world_storage_settings import WorldStorageSettings


def _external_world(tmp_path, *, create_database=True):
    worlds_root = tmp_path / "worlds"
    world = World.create(worlds_root, "External")
    database_path = tmp_path / "external.kraken"
    if create_database:
        database_path.touch()
    world.manifest.storage_mode = EXTERNAL_DATABASE_STORAGE
    world.manifest.db_filename = str(database_path.resolve())
    world.save_manifest()
    return worlds_root, world, database_path


def test_startup_cancellation_blocks_untrusted_external_database(qapp, tmp_path):
    """The startup path cannot reach an external database after cancellation."""
    worlds_root, world, database_path = _external_world(tmp_path)
    storage = WorldStorageSettings(QSettings())
    storage.set_active_world_path(world.path)
    manager = WorkerManager(MagicMock())
    world_manager = WorldManager(worlds_root)

    with patch.object(
        QMessageBox,
        "question",
        return_value=QMessageBox.StandardButton.No,
    ) as question:
        loaded = manager._load_active_world(world_manager, storage, None)

    assert loaded is None
    assert storage.active_world_path() is None
    assert not storage.is_external_path_approved(world)
    assert str(database_path.resolve()) in question.call_args.args[2]


def test_startup_loads_locally_approved_external_database(qapp, tmp_path):
    """A path bound to this manifest folder remains approved across startup."""
    worlds_root, world, database_path = _external_world(tmp_path)
    storage = WorldStorageSettings(QSettings())
    storage.set_active_world_path(world.path)
    storage.approve_external_path(world)
    manager = WorkerManager(MagicMock())
    world_manager = WorldManager(
        worlds_root,
        approved_external_paths=storage.external_approvals(),
    )

    with patch.object(QMessageBox, "question") as question:
        loaded = manager._load_active_world(world_manager, storage, None)

    assert loaded is not None
    assert loaded.db_path == database_path.resolve()
    question.assert_not_called()


def test_startup_never_recreates_missing_approved_external_database(qapp, tmp_path):
    """Recovery from a missing external target happens before the SQLite sink."""
    worlds_root, world, database_path = _external_world(
        tmp_path,
        create_database=False,
    )
    storage = WorldStorageSettings(QSettings())
    storage.set_active_world_path(world.path)
    storage.approve_external_path(world)
    manager = WorkerManager(MagicMock())
    world_manager = WorldManager(
        worlds_root,
        approved_external_paths=storage.external_approvals(),
    )

    with patch.object(QMessageBox, "warning") as warning:
        loaded = manager._load_active_world(world_manager, storage, None)

    assert loaded is None
    assert not database_path.exists()
    warning.assert_called_once()
