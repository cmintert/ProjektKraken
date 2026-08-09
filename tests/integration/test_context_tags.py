"""Integration coverage for context-tag creation and cleanup commands."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from PySide6.QtCore import QObject, QSettings

from src.app.coordinators.context_tag_coordinator import ContextTagCoordinator


class FakeWindow(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.current_world = SimpleNamespace(id="integration-world")
        self.event_editor = MagicMock()
        self.entity_editor = MagicMock()
        self.event_editor._current_event_id = None
        self.entity_editor._current_entity_id = None


def test_context_create_cleanup_and_undo_round_trip(db_service, tmp_path):
    settings = QSettings(
        str(tmp_path / "context.ini"),
        QSettings.Format.IniFormat,
    )
    coordinator = ContextTagCoordinator(FakeWindow(), settings)
    coordinator.save_tags(["Foggenburg", "Adventure"], activate=True)
    create = coordinator.create_entity_command(
        {
            "name": "North Gate",
            "type": "Location",
            "attributes": {"_tags": ["Keep"]},
        }
    )

    result = create.execute(db_service)
    result.data["command_id"] = create.command_id
    coordinator.on_command_finished(result)
    created = db_service.get_entity(create._entity.id)
    assert created is not None
    assert created.tags == ["Keep", "Foggenburg", "Adventure"]

    coordinator.reconcile([], [created])
    cleanup = coordinator.build_cleanup_command([("entity", created.id)])
    assert cleanup is not None
    cleanup_result = cleanup.execute(db_service)
    assert cleanup_result.success
    cleaned = db_service.get_entity(created.id)
    assert cleaned is not None
    assert cleaned.tags == ["Keep"]
    assert [tag["name"] for tag in db_service.get_tags_for_entity(created.id)] == [
        "Keep"
    ]

    cleanup.undo(db_service)
    restored = db_service.get_entity(created.id)
    assert restored is not None
    assert restored.tags == ["Keep", "Foggenburg", "Adventure"]
    assert sorted(
        tag["name"] for tag in db_service.get_tags_for_entity(created.id)
    ) == ["Adventure", "Foggenburg", "Keep"]
