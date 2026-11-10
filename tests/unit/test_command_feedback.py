"""Deletion feedback follows successful ordinary actions, never request intent."""

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QWidget

from src.app.command_feedback import present_deletion_feedback
from src.core.command import CommandResult


@pytest.mark.parametrize(
    ("command", "title", "text"),
    [
        ("DeleteMapCommand", "Deleted", "Deleted map."),
        ("DeleteMarkerCommand", "Deleted", "Deleted marker."),
        ("DeleteLayerSubtreeCommand", "Deleted", "Deleted layer."),
        ("DeleteRasterLayerCommand", "Deleted", "Deleted raster layer."),
        ("RemoveRasterSnapshotCommand", "Deleted", "Deleted raster snapshot."),
        ("RemoveRelationCommand", "Deleted", "Deleted relation."),
        ("DeleteCalendarConfigCommand", "Deleted", "Deleted calendar configuration."),
        ("RemoveLongformEntryCommand", "Removed", "Removed entry from this document."),
    ],
)
def test_confirmed_removal_uses_shared_feedback(qtbot, command, title, text):
    parent = QWidget()
    qtbot.addWidget(parent)
    with patch("src.app.command_feedback.AutoClosingMessageBox.notify") as notify:
        present_deletion_feedback(CommandResult(True, command_name=command), parent)
    notify.assert_called_once_with(parent, title, text + "\n\nUndo with Ctrl+Z.")


@pytest.mark.parametrize(
    ("success", "command"),
    [
        (False, "DeleteMapCommand"),
        (True, "Undo_DeleteMapCommand"),
        (True, "Redo_DeleteMapCommand"),
        (True, "UpdateMapCommand"),
    ],
)
def test_non_deletion_results_never_claim_deleted(qtbot, success, command):
    parent = QWidget()
    qtbot.addWidget(parent)
    with patch("src.app.command_feedback.AutoClosingMessageBox.notify") as notify:
        present_deletion_feedback(CommandResult(success, command_name=command), parent)
    notify.assert_not_called()


def test_lore_refresh_owns_its_named_notification(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    result = CommandResult(
        True,
        command_name="CompositeCommand",
        data={
            "lore_effects": [
                {
                    "object_type": "event",
                    "object_id": "e1",
                    "operation": "delete",
                    "snapshot": None,
                    "relations_changed": True,
                }
            ]
        },
    )
    with patch("src.app.command_feedback.AutoClosingMessageBox.notify") as notify:
        present_deletion_feedback(result, parent)
    notify.assert_not_called()
