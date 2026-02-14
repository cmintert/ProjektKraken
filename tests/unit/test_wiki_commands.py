from unittest.mock import MagicMock

from src.commands.wiki_commands import ProcessWikiLinksCommand


class TestProcessWikiLinksCommand:
    def test_creates_relations(self):
        """Test that the command actually creates 'mentions' relations in the DB."""
        # Setup
        cmd = ProcessWikiLinksCommand("source_1", "Check [[Target Entity]] here.")

        mock_db = MagicMock()

        # Mock entities
        source_entity = MagicMock()
        source_entity.id = "source_1"
        source_entity.name = "Source Entity"

        target_entity = MagicMock()
        target_entity.id = "target_1"
        target_entity.name = "Target Entity"
        target_entity.attributes = {}

        # Mock DB returns
        mock_db.get_entity.side_effect = lambda eid: (
            source_entity if eid == "source_1" else None
        )
        # returning a list for get_all_entities is easier for the name map logic
        mock_db.get_all_entities.return_value = [source_entity, target_entity]
        mock_db.get_all_events.return_value = []
        mock_db.get_relations.return_value = []  # No existing relations

        # Execute
        result = cmd.execute(mock_db)

        assert result.success
        assert result.data["valid_count"] == 1

        # Verify relation creation
        # Expected: insert_relation(source_id=..., target_id=..., rel_type=..., attributes=...)
        mock_db.insert_relation.assert_called_once()
        args, kwargs = mock_db.insert_relation.call_args

        # Since implementation uses kwargs, check kwargs
        assert kwargs["source_id"] == "source_1"
        assert kwargs["target_id"] == "target_1"
        assert kwargs["rel_type"] == "mentions"
        assert "start_offset" in kwargs["attributes"]

    def test_undo_removes_relations(self):
        """Test that undo removes the created relations."""
        cmd = ProcessWikiLinksCommand("source_1", "Check [[Target Entity]]")
        mock_db = MagicMock()

        # Pre-populate _created_relations as if execute() ran
        # The exact format depends on how we implement it, likely storing relation IDs or target IDs
        # For now let's assume implementation stores target IDs or similar.
        # Actually simplest is to store the full relation ID if add_relation returns it,
        # but add_relation usually returns void or ID.
        # Let's assume we implement it to store IDs.

        # For the TEST, we need to know how we WILL implement it.
        # I'll implement it to call remove_relation(rel_id) or remove_relation(source, target, type).
        # DB service usually supports removing by ID or criteria.
        # Let's check DB Service signature later, but for now test intent.

        cmd._created_relations = ["rel_123"]  # Simulating created relation ID

        cmd.undo(mock_db)

        mock_db.delete_relation.assert_called_with("rel_123")
