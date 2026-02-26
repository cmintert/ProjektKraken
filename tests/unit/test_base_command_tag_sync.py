"""Unit tests for BaseCommand tag sync utility methods."""

from unittest.mock import MagicMock

import pytest

from src.commands.base_command import BaseCommand, CommandResult
from src.services.db_service import DatabaseService


class _ConcreteCommand(BaseCommand):
    """Minimal concrete command for testing base class utilities."""

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """No-op execute."""
        return CommandResult(success=True)

    def undo(self, db_service: DatabaseService) -> None:
        """No-op undo."""
        pass

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {}

    @classmethod
    def from_dict(cls, data: dict) -> "_ConcreteCommand":
        """Deserialize from dict."""
        return cls()


@pytest.fixture
def mock_db() -> MagicMock:
    """Mock database service."""
    return MagicMock(spec=DatabaseService)


@pytest.fixture
def cmd() -> _ConcreteCommand:
    """Concrete command instance for testing."""
    return _ConcreteCommand()


class TestAssignTags:
    """Tests for BaseCommand._assign_tags."""

    def test_assign_entity_tags(self, mock_db: MagicMock) -> None:
        """Tags are assigned to an entity via assign_tag_to_entity."""
        BaseCommand._assign_tags(mock_db, "e1", ["war", "peace"], "entity")

        assert mock_db.assign_tag_to_entity.call_count == 2
        mock_db.assign_tag_to_entity.assert_any_call("e1", "war")
        mock_db.assign_tag_to_entity.assert_any_call("e1", "peace")

    def test_assign_event_tags(self, mock_db: MagicMock) -> None:
        """Tags are assigned to an event via assign_tag_to_event."""
        BaseCommand._assign_tags(mock_db, "ev1", ["battle"], "event")

        mock_db.assign_tag_to_event.assert_called_once_with("ev1", "battle")

    def test_assign_empty_tags(self, mock_db: MagicMock) -> None:
        """No DB calls when the tag list is empty."""
        BaseCommand._assign_tags(mock_db, "e1", [], "entity")

        mock_db.assign_tag_to_entity.assert_not_called()

    def test_assign_continues_on_error(self, mock_db: MagicMock) -> None:
        """A failing tag does not prevent subsequent tags from being assigned."""
        mock_db.assign_tag_to_entity.side_effect = [Exception("fail"), None]

        BaseCommand._assign_tags(mock_db, "e1", ["bad", "good"], "entity")

        assert mock_db.assign_tag_to_entity.call_count == 2


class TestSyncTags:
    """Tests for BaseCommand._sync_tags."""

    def test_sync_adds_new_tags(self, mock_db: MagicMock) -> None:
        """New tags are added when they don't exist in the database."""
        mock_db.get_tags_for_entity.return_value = []

        BaseCommand._sync_tags(mock_db, "e1", {"alpha", "beta"}, "entity")

        assert mock_db.assign_tag_to_entity.call_count == 2
        mock_db.remove_tag_from_entity.assert_not_called()

    def test_sync_removes_stale_tags(self, mock_db: MagicMock) -> None:
        """Stale tags are removed when they are no longer in the desired set."""
        mock_db.get_tags_for_entity.return_value = [
            {"name": "old"},
            {"name": "keep"},
        ]

        BaseCommand._sync_tags(mock_db, "e1", {"keep"}, "entity")

        mock_db.remove_tag_from_entity.assert_called_once_with("e1", "old")
        mock_db.assign_tag_to_entity.assert_not_called()

    def test_sync_adds_and_removes(self, mock_db: MagicMock) -> None:
        """Both additions and removals happen in one sync call."""
        mock_db.get_tags_for_event.return_value = [{"name": "old"}]

        BaseCommand._sync_tags(mock_db, "ev1", {"new"}, "event")

        mock_db.remove_tag_from_event.assert_called_once_with("ev1", "old")
        mock_db.assign_tag_to_event.assert_called_once_with("ev1", "new")

    def test_sync_no_changes(self, mock_db: MagicMock) -> None:
        """No DB calls when the desired set matches the current set."""
        mock_db.get_tags_for_entity.return_value = [{"name": "a"}, {"name": "b"}]

        BaseCommand._sync_tags(mock_db, "e1", {"a", "b"}, "entity")

        mock_db.remove_tag_from_entity.assert_not_called()
        mock_db.assign_tag_to_entity.assert_not_called()

    def test_sync_continues_on_remove_error(self, mock_db: MagicMock) -> None:
        """A failing removal does not prevent other operations."""
        mock_db.get_tags_for_entity.return_value = [
            {"name": "fail"},
            {"name": "ok"},
        ]
        mock_db.remove_tag_from_entity.side_effect = [Exception("fail"), None]

        BaseCommand._sync_tags(mock_db, "e1", set(), "entity")

        assert mock_db.remove_tag_from_entity.call_count == 2
