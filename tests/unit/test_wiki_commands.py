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
    mock_db.insert_relation.return_value = "new-rel-id"
    return mock_db


def _make_entity(entity_id: str, name: str) -> MagicMock:
    entity = MagicMock()
    entity.id = entity_id
    entity.name = name
    entity.attributes = {}
    return entity


class TestProcessWikiLinksCommand:
    def test_creates_relations(self):
        """Test that the command actually creates 'mentions' relations in the DB."""
        cmd = ProcessWikiLinksCommand("source_1", "Check [[Target Entity]] here.")

        source_entity = _make_entity("source_1", "Source Entity")
        target_entity = _make_entity("target_1", "Target Entity")

        mock_db = _make_mock_db(entities=[source_entity, target_entity])

        result = cmd.execute(mock_db)

        assert result.success
        assert result.data["valid_count"] == 1

        mock_db.insert_relation.assert_called_once()
        _, kwargs = mock_db.insert_relation.call_args

        assert kwargs["source_id"] == "source_1"
        assert kwargs["target_id"] == "target_1"
        assert kwargs["rel_type"] == "mentions"
        assert "start_offset" in kwargs["attributes"]

    def test_undo_removes_relations(self):
        """Test that undo removes the created relations."""
        cmd = ProcessWikiLinksCommand("source_1", "Check [[Target Entity]]")
        mock_db = MagicMock()

        cmd._created_relations = ["rel_123"]
        cmd._is_executed = True

        cmd.undo(mock_db)

        mock_db.delete_relation.assert_called_with("rel_123")

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

        # Simulate the DB now returning the relation created above.
        # The start_offset for [[Frodo]] in the text above is 9.
        mock_db.get_relations.return_value = [
            {
                "target_id": "frodo-id",
                "rel_type": "mentions",
                "attributes": {"start_offset": 9},
            }
        ]

        # Second execution should skip the already-existing relation.
        result2 = cmd2.execute(mock_db)
        assert result2.success
        assert result2.data["valid_count"] == 0
        # insert_relation was called only once (by cmd1), not again by cmd2.
        assert mock_db.insert_relation.call_count == 1

    def test_two_links_same_target_different_offsets_both_created(self):
        """Two wikilinks to the same target at different character positions
        should each create their own 'mentions' relation.
        """
        text = "[[Frodo]] went to [[Frodo]]'s house."
        cmd = ProcessWikiLinksCommand("source_1", text)

        target = _make_entity("frodo-id", "Frodo")
        source = _make_entity("source_1", "Source")

        mock_db = _make_mock_db(entities=[source, target])

        result = cmd.execute(mock_db)

        assert result.success
        # Two distinct [[Frodo]] spans → two relations
        assert result.data["valid_count"] == 2
        assert mock_db.insert_relation.call_count == 2

        # Verify the two inserts used different start_offsets
        calls = mock_db.insert_relation.call_args_list
        offsets = {c[1]["attributes"]["start_offset"] for c in calls}
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

        # Simulate a pre-existing 'mentions' relation at offset 0 (e.g. from
        # a different field/run that happened to land at byte 0).
        mock_db = _make_mock_db(
            entities=[source, target],
            existing_relations=[
                {
                    "target_id": "frodo-id",
                    "rel_type": "mentions",
                    "attributes": {"start_offset": 0},
                }
            ],
        )

        result = cmd.execute(mock_db)

        assert result.success
        # The link at offset 10 should still be created even though offset 0 exists.
        assert result.data["valid_count"] == 1
