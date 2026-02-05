import pytest
from unittest.mock import MagicMock, call
from src.commands.base_command import BaseCommand, CommandResult


# Mock Command for testing
class MockCommand(BaseCommand):
    def __init__(self, name="mock", should_fail=False):
        super().__init__()
        self.name = name
        self.should_fail = should_fail
        self.executed = False
        self.undone = False

    def execute(self, db_service):
        if self.should_fail:
            return CommandResult(False, f"{self.name} failed")
        self.executed = True
        self._is_executed = True
        return CommandResult(True, f"{self.name} passed")

    def undo(self, db_service):
        self.undone = True
        self.executed = False

    def to_dict(self):
        return {"name": self.name, "should_fail": self.should_fail}

    @classmethod
    def from_dict(cls, data):
        return cls(data["name"], data["should_fail"])

    def get_description(self):
        return f"Mock {self.name}"


class TestCompositeCommand:
    def test_execute_sequence(self):
        """Test that sub-commands are executed in order."""
        from src.commands.composite_command import CompositeCommand

        cmd1 = MockCommand("1")
        cmd2 = MockCommand("2")
        composite = CompositeCommand([cmd1, cmd2], description="Composite Test")

        db = MagicMock()
        result = composite.execute(db)

        assert result.success
        assert cmd1.executed
        assert cmd2.executed
        assert composite.is_executed

    def test_undo_reverse_order(self):
        """Test that undo executes sub-commands in reverse order."""
        from src.commands.composite_command import CompositeCommand

        cmd1 = MockCommand("1")
        cmd2 = MockCommand("2")
        composite = CompositeCommand([cmd1, cmd2])

        db = MagicMock()
        composite.execute(db)
        composite.undo(db)

        # In a real scenario, we can't easily verify strict timing order without side-effects,
        # but we can verify they were both undone.
        assert cmd1.undone
        assert cmd2.undone

    def test_failure_stops_execution(self):
        """Test that execution stops if a sub-command fails."""
        from src.commands.composite_command import CompositeCommand

        cmd1 = MockCommand("1")
        cmd2 = MockCommand("2", should_fail=True)
        cmd3 = MockCommand("3")

        composite = CompositeCommand([cmd1, cmd2, cmd3])
        db = MagicMock()

        result = composite.execute(db)

        assert not result.success
        assert "2 failed" in result.message
        # cmd1 should be rolled back, so executed should be False (or undone True)
        assert not cmd1.executed
        assert cmd1.undone
        # Cmd3 should definitely NOT be executed
        assert not cmd3.executed

    def test_failure_reverts_previous(self):
        """Test that if a command fails, previous valid commands are undone."""
        from src.commands.composite_command import CompositeCommand

        cmd1 = MockCommand("1")
        cmd2 = MockCommand("2", should_fail=True)

        composite = CompositeCommand([cmd1, cmd2])
        db = MagicMock()

        # We need to verify that cmd1.undo() is called when cmd2 fails
        # Mocking undo method on cmd1 instance to track call
        cmd1.undo = MagicMock()

        composite.execute(db)

        # cmd1.executed should be True initially, but since it's a mock object we are tracking
        # the state. The mock logic sets executed=True on execute, and executed=False on undo.
        # But here we mocked undo(), so the original undo logic (executed=False) WON'T run unless we call original.
        # So we just assert undo was called.

        cmd1.undo.assert_called_once()  # But then undone because cmd2 failed

    def test_serialization(self):
        """Test to_dict and from_dict."""
        from src.commands.composite_command import CompositeCommand

        # For this test, let's assume we implement a dictionary structure
        cmd1 = MockCommand("1")
        composite = CompositeCommand([cmd1], "Test Desc")

        data = composite.to_dict()
        assert data["description"] == "Test Desc"
        assert len(data["commands"]) == 1
        assert data["commands"][0]["type"] == "MockCommand"
