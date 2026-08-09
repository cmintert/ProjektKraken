"""World Manager tests for portable folders and external database approval."""

from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from src.core.world import EXTERNAL_DATABASE_STORAGE, World
from src.gui.dialogs.database_manager_dialog import DatabaseManagerDialog


def _select_world(dialog, world_path: Path) -> None:
    for row in range(dialog.db_list.count()):
        item = dialog.db_list.item(row)
        if Path(item.data(Qt.ItemDataRole.UserRole)) == world_path.resolve():
            dialog.db_list.setCurrentItem(item)
            return
    raise AssertionError(f"World row not found for {world_path}")


def test_add_complete_world_folder_from_registered_location(qtbot, tmp_path):
    """A complete world folder can be registered without moving its contents."""
    default_root = tmp_path / "default"
    shared_world = World.create(tmp_path / "shared", "Shared World")

    with (
        patch(
            "src.gui.dialogs.database_manager_dialog.ensure_worlds_directory",
            return_value=default_root,
        ),
        patch(
            "src.gui.dialogs.database_manager_dialog.QFileDialog.getExistingDirectory",
            return_value=str(shared_world.path),
        ),
    ):
        dialog = DatabaseManagerDialog()
        qtbot.addWidget(dialog)
        dialog._add_world_folder()

    assert (
        shared_world.path.resolve() in dialog.storage_settings.registered_world_paths()
    )
    assert dialog.db_list.count() == 1


def test_select_external_world_requires_and_remembers_approval(qtbot, tmp_path):
    """Selecting an external world shows approval before persisting trust."""
    default_root = tmp_path / "default"
    external_database = tmp_path / "database" / "linked.kraken"
    external_database.parent.mkdir()
    external_database.touch()
    world = World.create(default_root, "External World")
    world.manifest.storage_mode = EXTERNAL_DATABASE_STORAGE
    world.manifest.db_filename = str(external_database.resolve())
    world.save_manifest()

    with patch(
        "src.gui.dialogs.database_manager_dialog.ensure_worlds_directory",
        return_value=default_root,
    ):
        dialog = DatabaseManagerDialog()
        qtbot.addWidget(dialog)
        _select_world(dialog, world.path)
        with (
            patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.Yes,
            ) as question,
            patch.object(QMessageBox, "information"),
        ):
            dialog._select_world()

    question.assert_called_once()
    inspected = World.inspect(world.path)
    assert inspected is not None
    assert dialog.storage_settings.is_external_path_approved(inspected)
    assert dialog.storage_settings.active_world_path() == world.path.resolve()


def test_link_and_revoke_external_database(qtbot, tmp_path):
    """Advanced linking writes explicit mode and revocation removes local trust."""
    default_root = tmp_path / "default"
    world = World.create(default_root, "Link World")
    external_database = tmp_path / "external.kraken"
    external_database.touch()

    with patch(
        "src.gui.dialogs.database_manager_dialog.ensure_worlds_directory",
        return_value=default_root,
    ):
        dialog = DatabaseManagerDialog()
        qtbot.addWidget(dialog)
        _select_world(dialog, world.path)
        with (
            patch(
                "src.gui.dialogs.database_manager_dialog.QFileDialog.getOpenFileName",
                return_value=(str(external_database), ""),
            ),
            patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch.object(QMessageBox, "information"),
        ):
            dialog._link_external_database()

        linked = World.inspect(world.path)
        assert linked is not None
        assert linked.is_external_database
        assert linked.db_path == external_database.resolve()
        assert dialog.storage_settings.is_external_path_approved(linked)

        _select_world(dialog, world.path)
        with patch.object(QMessageBox, "information"):
            dialog._revoke_external_database()

    assert not dialog.storage_settings.is_external_path_approved(linked)
