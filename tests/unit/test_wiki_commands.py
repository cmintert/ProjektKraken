from unittest.mock import MagicMock

from src.commands.wiki_commands import ProcessWikiLinksCommand


def _make_mock_db(
    entities: list | None = None,
    events: list | None = None,
    existing_relations: list | None = None,
) -> MagicMock:
    """Build a mock DatabaseService with sensible defaults."""
    mock_db = MagicMock()
    mock_db.get_all_entities.return_value = entities or []
    mock_db.get_all_events.return_value = events or []
    mock_db.get_relations.return_value = existing_relations or []
    mock_db.reconcile_mentions.return_value = {
        "before": existing_relations or [],
        "after": [],
        "created_count": 1,
        "updated_count": 0,
        "deleted_count": 0,
    }
    return mock_db


def _make_entity(entity_id: str, name: str) -> MagicMock:
    entity = MagicMock()
    entity.id = entity_id
    entity.name = name
    entity.attributes = {}
    return entity


class TestProcessWikiLinksCommand:
    def test_creates_relations(self):
        """The command sends canonical grouped occurrences to reconciliation."""
        cmd = ProcessWikiLinksCommand("source_1", "Check [[Target Entity]] here.")

        source_entity = _make_entity("source_1", "Source Entity")
        target_entity = _make_entity("target_1", "Target Entity")

        mock_db = _make_mock_db(entities=[source_entity, target_entity])

        result = cmd.execute(mock_db)

        assert result.success
        assert result.data["valid_count"] == 1

        mock_db.reconcile_mentions.assert_called_once()
        source_id, field, occurrences = mock_db.reconcile_mentions.call_args.args
        assert source_id == "source_1"
        assert field == "description"
        assert set(occurrences) == {"target_1"}
        assert occurrences["target_1"][0]["start_offset"] == 6

    def test_undo_restores_previous_relations(self):
        """Undo restores the complete pre-reconciliation snapshot."""
        cmd = ProcessWikiLinksCommand("source_1", "Check [[Target Entity]]")
        mock_db = MagicMock()
        previous = [{"id": "rel_123", "rel_type": "mentions"}]
        cmd._before_relations = previous
        cmd._is_executed = True

        cmd.undo(mock_db)

        mock_db.restore_mentions.assert_called_once_with("source_1", previous)

    def test_second_execute_does_not_create_duplicates(self):
        """Executing the same command a second time must not create duplicate
        'mentions' relations for the same wikilink span.

        Simulates the autosave retrigger scenario: user saves twice without
        changing the description text.
        """
        text = "Mentions [[Frodo]] here."
        cmd1 = ProcessWikiLinksCommand("source_1", text)
        cmd2 = ProcessWikiLinksCommand("source_1", text)

        target = _make_entity("frodo-id", "Frodo")
        source = _make_entity("source_1", "Source")

        mock_db = _make_mock_db(entities=[source, target])

        # First execution creates the relation.
        result1 = cmd1.execute(mock_db)
        assert result1.success
        assert result1.data["valid_count"] == 1

        # The repository owns idempotency; both commands submit the same desired set.
        result2 = cmd2.execute(mock_db)
        assert result2.success
        assert result2.data["valid_count"] == 1
        assert mock_db.reconcile_mentions.call_count == 2
        first_desired = mock_db.reconcile_mentions.call_args_list[0].args[2]
        second_desired = mock_db.reconcile_mentions.call_args_list[1].args[2]
        assert first_desired == second_desired

    def test_two_links_same_target_are_grouped_as_occurrences(self):
        """Multiple textual occurrences produce one desired graph relation."""
        text = "[[Frodo]] went to [[Frodo]]'s house."
        cmd = ProcessWikiLinksCommand("source_1", text)

        target = _make_entity("frodo-id", "Frodo")
        source = _make_entity("source_1", "Source")

        mock_db = _make_mock_db(entities=[source, target])

        result = cmd.execute(mock_db)

        assert result.success
        assert result.data["valid_count"] == 1
        assert result.data["occurrence_count"] == 2
        occurrences = mock_db.reconcile_mentions.call_args.args[2]["frodo-id"]
        offsets = {item["start_offset"] for item in occurrences}
        assert len(offsets) == 2

    def test_span_offset_used_for_dedup_not_hardcoded_zero(self):
        """Existing relation at offset 0 must not suppress a new link at a
        different offset — the old hardcoded-0 bug.
        """
        text = "Something [[Frodo]] appears here."
        # [[Frodo]] starts at index 10
        cmd = ProcessWikiLinksCommand("source_1", text)

        target = _make_entity("frodo-id", "Frodo")
        source = _make_entity("source_1", "Source")

        mock_db = _make_mock_db(entities=[source, target])

        result = cmd.execute(mock_db)

        assert result.success
        assert result.data["valid_count"] == 1
        occurrence = mock_db.reconcile_mentions.call_args.args[2]["frodo-id"][0]
        assert occurrence["start_offset"] == 10
