"""Tests for locally trusted world storage settings."""

from PySide6.QtCore import QSettings

from src.core.world import EXTERNAL_DATABASE_STORAGE, World, WorldManifest
from src.services.world_storage_settings import WorldStorageSettings


def _external_world(tmp_path, folder_name, database_path):
    world_path = tmp_path / folder_name
    world_path.mkdir()
    return World(
        path=world_path.resolve(),
        manifest=WorldManifest(
            id=folder_name,
            name=folder_name,
            db_filename=str(database_path.resolve()),
            storage_mode=EXTERNAL_DATABASE_STORAGE,
        ),
    )


def test_external_approval_persists_and_can_be_revoked(tmp_path):
    """External trust survives a new facade and remains explicitly revocable."""
    database_path = tmp_path / "external.kraken"
    database_path.touch()
    world = _external_world(tmp_path, "world", database_path)

    storage = WorldStorageSettings(QSettings())
    assert not storage.is_external_path_approved(world)

    storage.approve_external_path(world)
    reloaded = WorldStorageSettings(QSettings())

    assert reloaded.is_external_path_approved(world)
    reloaded.revoke_external_path(world)
    assert not WorldStorageSettings(QSettings()).is_external_path_approved(world)


def test_external_approval_is_bound_to_manifest_location(tmp_path):
    """A copied manifest cannot reuse another folder's local approval."""
    database_path = tmp_path / "external.kraken"
    database_path.touch()
    approved_world = _external_world(tmp_path, "approved", database_path)
    copied_world = _external_world(tmp_path, "copied", database_path)
    storage = WorldStorageSettings(QSettings())

    storage.approve_external_path(approved_world)

    assert storage.is_external_path_approved(approved_world)
    assert not storage.is_external_path_approved(copied_world)


def test_registered_world_and_active_path_persist(tmp_path):
    """Complete world folders outside the default root remain discoverable."""
    world_path = tmp_path / "shared" / "world"
    world_path.mkdir(parents=True)
    storage = WorldStorageSettings(QSettings())

    storage.register_world_path(world_path)
    storage.set_active_world_path(world_path)
    reloaded = WorldStorageSettings(QSettings())

    assert reloaded.registered_world_paths() == [world_path.resolve()]
    assert reloaded.active_world_path() == world_path.resolve()
