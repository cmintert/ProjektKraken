from unittest.mock import MagicMock

from src.commands.composite_command import CompositeCommand
from src.commands.event_commands import UpdateEventCommand
from src.commands.wiki_commands import ProcessWikiLinksCommand
from src.core.events import Event


class TestCompositePersistentUndo:
    def test_composite_persistent_undo_with_wiki_links(self):
        """Test that ProcessWikiLinksCommand retains state across serialization
        for undo within a CompositeCommand."""

        # Setup Mock DB
        mock_db = MagicMock()

        # Target entity to link to
        target_entity = MagicMock()
        target_entity.id = "target_1"
        target_entity.name = "Target Entity"

        # Mock DB returns for processing
        mock_db.get_all_entities.return_value = [target_entity]
        mock_db.get_all_events.return_value = []
        mock_db.get_relations.return_value = []

        # When creating relation, return a fake relation ID
        mock_db.insert_relation.return_value = "rel_123"

        # Fake existing event to update
        existing_event = Event(id="event_1", name="Test Event", lore_date=0.0)
        mock_db.get_event.return_value = existing_event

        # 1. Create commands
        update_cmd = UpdateEventCommand(
            event_id="event_1", update_data={"description": "Link to [[Target Entity]]"}
        )
        wiki_cmd = ProcessWikiLinksCommand(
            source_id="event_1", text_content="Link to [[Target Entity]]"
        )

        composite = CompositeCommand(
            [update_cmd, wiki_cmd], description="Update Event and Process Links"
        )

        # 2. Execute
        result = composite.execute(mock_db)
        assert result.success

        # Verify relation was created
        mock_db.insert_relation.assert_called_once()
        assert "rel_123" in wiki_cmd._created_relations

        # 3. Serialize to map (simulate saving to DB and app restart)
        cmd_dict = composite.to_dict()

        # Reset mock calls to be sure undo acts independently
        mock_db.reset_mock()

        # 4. Deserialize
        reconstructed_composite = CompositeCommand.from_dict(cmd_dict)

        # Verify state is restored
        assert len(reconstructed_composite.commands) == 2
        recon_wiki_cmd = reconstructed_composite.commands[1]
        assert isinstance(recon_wiki_cmd, ProcessWikiLinksCommand)

        # This will fail before the fix because _created_relations isn't serialized
        assert "rel_123" in recon_wiki_cmd._created_relations

        # 5. Undo the reconstructed command
        reconstructed_composite.undo(mock_db)

        # Verify relation deletion was attempted
        mock_db.delete_relation.assert_called_once_with("rel_123")
