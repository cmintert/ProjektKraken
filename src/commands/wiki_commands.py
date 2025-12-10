"""
Wiki Commands Module.
Commands for processing WikiLinks and updating relations.
"""

import logging
from typing import List

from src.commands.base_command import BaseCommand, CommandResult
from src.services.db_service import DatabaseService
from src.services.text_parser import WikiLinkParser

logger = logging.getLogger(__name__)


class ProcessWikiLinksCommand(BaseCommand):
    """
    Command to process text content, extract WikiLinks, and create relations.
    """

    def __init__(self, source_id: str, text_content: str):
        """
        Initializes the command.

        Args:
            source_id (str): The ID of the source entity or event.
            text_content (str): The text content to parse.
        """
        super().__init__()
        self.source_id = source_id
        self.text_content = text_content
        self._created_relations: List[str] = []

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the link processing.
        Extracts links, finds matching entities, and creates 'mentioned' relations.

        Args:
            db_service (DatabaseService): Database service instance.

        Returns:
            CommandResult: Result of the operation.
        """
        try:
            logger.info(f"Processing WikiLinks for source {self.source_id}")

            # 1. Parse Links
            target_names = WikiLinkParser.extract_links(self.text_content)
            if not target_names:
                return CommandResult(
                    success=True,
                    message="No links found.",
                    command_name="ProcessWikiLinksCommand",
                )

            # 2. Resolve Targets (Naive name matching for now)
            # In a real app, we might want a cache or optimized lookup
            all_entities = db_service.get_all_entities()
            name_map = {e.name.lower(): e for e in all_entities}

            created_count = 0

            for name in target_names:
                target_entity = name_map.get(name.lower())

                if target_entity:
                    # Check if relation exists to avoid duplicates
                    existing_rels = db_service.get_relations(self.source_id)
                    # existing_rels gives dicts, but we usually access by key.
                    # Wait, get_relations returns list of dicts.
                    # Let's check keys: 'target_id'
                    already_linked = any(
                        r["target_id"] == target_entity.id for r in existing_rels
                    )

                    if not already_linked and target_entity.id != self.source_id:
                        # Create Relation
                        # Using service directly
                        rel_id = db_service.insert_relation(
                            source_id=self.source_id,
                            target_id=target_entity.id,
                            rel_type="mentioned",
                        )
                        self._created_relations.append(rel_id)
                        created_count += 1
                        logger.info(
                            f"Auto-linked {self.source_id} -> {target_entity.name}"
                        )

            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Processed links. Created {created_count} new relations.",
                command_name="ProcessWikiLinksCommand",
            )

        except Exception as e:
            logger.error(f"Failed to process wiki links: {e}")
            return CommandResult(
                success=False,
                message=f"Error processing links: {e}",
                command_name="ProcessWikiLinksCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """
        Undoes the relation creation.
        """
        if self._is_executed and self._created_relations:
            logger.info(f"Undoing WikiLink processing for {self.source_id}")
            for rel_id in self._created_relations:
                db_service.delete_relation(rel_id)
            self._created_relations.clear()
            self._is_executed = False
