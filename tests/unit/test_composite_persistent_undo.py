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

        before_relations = [
            {
                "id": "rel_before",
                "source_id": "event_1",
                "target_id": "old_target",
                "rel_type": "mentions",
                "attributes": {"is_auto_generated": True, "occurrences": []},
                "created_at": 1.0,
            }
        ]
        after_relations = [
            {
                "id": "rel_after",
                "source_id": "event_1",
                "target_id": "target_1",
                "rel_type": "mentions",
                "attributes": {"is_auto_generated": True, "occurrences": []},
                "created_at": 2.0,
            }
        ]
        mock_db.reconcile_mentions.return_value = {
            "before": before_relations,
            "after": after_relations,
            "created_count": 1,
            "updated_count": 0,
            "deleted_count": 1,
        }

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

        mock_db.reconcile_mentions.assert_called_once()
        assert wiki_cmd._before_relations == before_relations
        assert wiki_cmd._after_relations == after_relations

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

        assert recon_wiki_cmd._before_relations == before_relations
        assert recon_wiki_cmd._after_relations == after_relations

        # 5. Undo the reconstructed command
        reconstructed_composite.undo(mock_db)

        mock_db.restore_mentions.assert_called_once_with(
            "event_1",
            before_relations,
        )
