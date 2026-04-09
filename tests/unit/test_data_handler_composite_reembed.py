"""Regression tests for DataHandler.on_command_finished re-embed behaviour.

- Plain Update* commands must trigger index_object_requested (existing path).
- CompositeCommand wrapping an Update* sub-command must also trigger it (fixed path).
- Commands unrelated to indexing must NOT trigger it.
"""

from unittest.mock import MagicMock

import pytest

from src.app.data_handler import DataHandler
from src.commands.base_command import CommandResult
from src.commands.entity_commands import UpdateEntityCommand
from src.commands.event_commands import UpdateEventCommand


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(command_name: str, data: dict | None = None) -> CommandResult:
    return CommandResult(
        success=True,
        message="ok",
        command_name=command_name,
        data=data or {},
    )


def _make_composite(sub_cmd: object) -> object:
    """Return a minimal object that looks like a CompositeCommand."""
    composite = MagicMock()
    composite.commands = [sub_cmd]
    return composite


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def handler():
    return DataHandler()


@pytest.fixture()
def index_calls(handler):
    """Collect (obj_type, obj_id) tuples emitted by index_object_requested."""
    calls: list[tuple[str, str]] = []
    handler.index_object_requested.connect(
        lambda t, i: calls.append((t, i))
    )
    return calls


# ---------------------------------------------------------------------------
# Plain Update* commands (existing path — must not regress)
# ---------------------------------------------------------------------------


class TestPlainUpdateCommands:
    def test_update_entity_emits_index_request(self, handler, index_calls):
        result = _make_result("UpdateEntityCommand", {"id": "entity-1"})
        handler.on_command_finished(result)
        assert ("entity", "entity-1") in index_calls

    def test_update_event_emits_index_request(self, handler, index_calls):
        result = _make_result("UpdateEventCommand", {"id": "event-1"})
        handler.on_command_finished(result)
        assert ("event", "event-1") in index_calls

    def test_create_entity_emits_index_request(self, handler, index_calls):
        result = _make_result("CreateEntityCommand", {"id": "entity-new"})
        handler.on_command_finished(result)
        assert ("entity", "entity-new") in index_calls

    def test_create_event_emits_index_request(self, handler, index_calls):
        result = _make_result("CreateEventCommand", {"id": "event-new"})
        handler.on_command_finished(result)
        assert ("event", "event-new") in index_calls


# ---------------------------------------------------------------------------
# CompositeCommand path (the regression fix)
# ---------------------------------------------------------------------------


class TestCompositeCommandReEmbed:
    """CompositeCommand wrapping UpdateEntity/UpdateEvent must trigger re-embed.

    This is the scenario from autosave/save with a description field present:
    EditorCoordinator wraps UpdateEntityCommand + ProcessWikiLinksCommand into
    a CompositeCommand, which previously produced command_name='CompositeCommand'
    and was invisible to the plain _INDEX_COMMANDS lookup.
    """

    def test_composite_with_update_entity_emits_index(self, handler, index_calls):
        sub = UpdateEntityCommand("entity-42", {"name": "Foo"})
        composite = _make_composite(sub)
        result = _make_result("CompositeCommand", {"command": composite})
        handler.on_command_finished(result)
        assert ("entity", "entity-42") in index_calls

    def test_composite_with_update_event_emits_index(self, handler, index_calls):
        sub = UpdateEventCommand("event-99", {"name": "Bar"})
        composite = _make_composite(sub)
        result = _make_result("CompositeCommand", {"command": composite})
        handler.on_command_finished(result)
        assert ("event", "event-99") in index_calls

    def test_composite_with_non_index_sub_does_not_emit(self, handler, index_calls):
        """ProcessWikiLinksCommand alone (no Update* sub) must not emit."""
        from src.commands.wiki_commands import ProcessWikiLinksCommand

        sub = ProcessWikiLinksCommand("entity-77", "some [[link]]")
        composite = _make_composite(sub)
        result = _make_result("CompositeCommand", {"command": composite})
        handler.on_command_finished(result)
        assert index_calls == []

    def test_composite_emits_only_once_for_first_matching_sub(
        self, handler, index_calls
    ):
        """If two Update* sub-commands exist, only the first triggers re-embed."""
        sub1 = UpdateEntityCommand("entity-A", {})
        sub2 = UpdateEntityCommand("entity-B", {})
        composite = MagicMock()
        composite.commands = [sub1, sub2]
        result = _make_result("CompositeCommand", {"command": composite})
        handler.on_command_finished(result)
        assert len(index_calls) == 1
        assert index_calls[0] == ("entity", "entity-A")

    def test_composite_without_command_key_does_not_crash(self, handler, index_calls):
        """result.data missing 'command' key must not raise."""
        result = _make_result("CompositeCommand", {})
        handler.on_command_finished(result)  # must not raise
        assert index_calls == []

    def test_composite_with_none_command_does_not_crash(self, handler, index_calls):
        result = _make_result("CompositeCommand", {"command": None})
        handler.on_command_finished(result)
        assert index_calls == []


# ---------------------------------------------------------------------------
# Unrelated commands must NOT emit
# ---------------------------------------------------------------------------


class TestUnrelatedCommandsNoEmit:
    def test_delete_entity_does_not_emit_index(self, handler, index_calls):
        result = _make_result("DeleteEntityCommand", {"id": "entity-del"})
        handler.on_command_finished(result)
        assert index_calls == []

    def test_add_relation_does_not_emit_index(self, handler, index_calls):
        result = _make_result("AddRelationCommand", {"id": "rel-1"})
        handler.on_command_finished(result)
        assert index_calls == []
