"""Regression tests for command-level database atomicity."""

from src.commands.base_command import BaseCommand, CommandResult
from src.core.entities import Entity
from src.services.db_service import DatabaseService


class _PartiallyFailingCommand(BaseCommand):
    """Write one entity and then report a command failure."""

    def __init__(self, entity: Entity) -> None:
        super().__init__()
        self.entity = entity

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Perform a write before returning a failed result."""
        db_service.insert_entity(self.entity)
        return CommandResult(success=False, message="deliberate failure")

    def undo(self, db_service: DatabaseService) -> CommandResult:
        """Return a successful no-op undo result."""
        return CommandResult(success=True)

    def to_dict(self) -> dict:
        """Serialize the test command."""
        return {"entity": self.entity.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> "_PartiallyFailingCommand":
        """Deserialize the test command."""
        return cls(Entity.from_dict(data["entity"]))


def test_failed_command_result_rolls_back_earlier_writes(
    db_service: DatabaseService,
) -> None:
    """A failed result must not leave partial command data committed."""
    entity = Entity(name="Must Roll Back", type="test")

    result = _PartiallyFailingCommand(entity).execute(db_service)

    assert result.success is False
    assert db_service.get_entity(entity.id) is None
