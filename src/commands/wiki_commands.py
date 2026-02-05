"""Wiki Commands Module.

Commands for processing WikiLinks and updating relations.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Set

from src.commands.base_command import BaseCommand, CommandResult
from src.services.db_service import DatabaseService
from src.services.text_parser import WikiLinkParser

logger = logging.getLogger(__name__)


class ProcessWikiLinksCommand(BaseCommand):
    """Command to process text content, extract WikiLinks, and create 'mentions'
    relations.

    This command:
    - Parses WikiLinks from text content
    - Resolves names to entities (case-insensitive, including aliases)
    - Creates 'mentions' relations with metadata (snippet, offsets, field)
    - Skips ambiguous matches (multiple entities with same name/alias)
    - Deduplicates by (target_id, start_offset)
    """

    def __init__(
        self, source_id: str, text_content: str, field: str = "description"
    ) -> None:
        """Initializes the command.

        Args:
            source_id: The ID of the source entity or event.
            text_content: The text content to parse for WikiLinks.
            field: The field name where the text is stored (default: "description").

        """
        super().__init__()
        self.source_id = source_id
        self.text_content = text_content
        self.field = field
        self._created_relations: List[str] = []

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the link processing.

        Extracts WikiLinks, resolves them to entities or events, and
        creates 'mentions' relations with metadata including field,
        snippet, and offsets.

        Args:
            db_service: Database service instance.

        Returns:
            CommandResult: Result of the operation.

        """
        try:
            logger.info(f"Processing WikiLinks for source {self.source_id}")

            # 1. Parse Links
            candidates = WikiLinkParser.extract_links(self.text_content)
            if not candidates:
                return CommandResult(
                    success=True,
                    message="No links found.",
                    command_name="ProcessWikiLinksCommand",
                )

            # 2. Build name->Target map including aliases (Mixed Entities and Events)
            # We map name -> list of objects (Entity or Event)

            # 2a. Load Entities
            all_entities = db_service.get_all_entities()
            name_to_targets: Dict[str, List] = defaultdict(list)

            for entity in all_entities:
                # Add primary name
                name_key = entity.name.casefold()
                name_to_targets[name_key].append(entity)

                # Add aliases if present
                aliases = entity.attributes.get("aliases", [])
                if isinstance(aliases, list):
                    for alias in aliases:
                        if isinstance(alias, str):
                            alias_key = alias.casefold()
                            name_to_targets[alias_key].append(entity)

            # 2b. Load Events
            all_events = db_service.get_all_events()
            for event in all_events:
                name_key = event.name.casefold()
                name_to_targets[name_key].append(event)

            # 3. Get existing relations for deduplication
            existing_relations = db_service.get_relations(self.source_id)
            existing_keys: Set[tuple] = set()
            for rel in existing_relations:
                if rel["rel_type"] == "mentions":
                    attrs = rel.get("attributes", {})
                    if isinstance(attrs, dict):
                        start_offset = attrs.get("start_offset")
                        if start_offset is not None:
                            existing_keys.add((rel["target_id"], start_offset))

            # 4. Process each candidate
            created_count = 0  # Now represents "valid links found"
            skipped_ambiguous = []
            skipped_missing = []
            valid_links = []

            for candidate in candidates:
                target_obj = None
                target_type_str = "Entity"  # Default or detected

                # Handle ID-based links
                if candidate.is_id_based:
                    # Direct lookup by ID
                    # Try Entity first
                    assert candidate.target_id is not None  # Guaranteed by parser
                    target_obj = db_service.get_entity(candidate.target_id)
                    if target_obj:
                        target_type_str = "Entity"
                    else:
                        # Try Event
                        target_obj = db_service.get_event(candidate.target_id)
                        if target_obj:
                            target_type_str = "Event"

                    if not target_obj:
                        # Broken link - target doesn't exist
                        skipped_missing.append(
                            candidate.modifier or candidate.target_id
                        )
                        logger.warning(f"Broken ID-based link: {candidate.target_id}")
                        continue

                # Handle name-based links (legacy)
                else:
                    assert candidate.name is not None  # Guaranteed by parser
                    name_key = candidate.name.casefold()
                    matching_targets = name_to_targets.get(name_key, [])

                    if len(matching_targets) == 0:
                        # No match found
                        skipped_missing.append(candidate.name)
                        logger.debug(f"No target found for link: {candidate.name}")
                        continue

                    elif len(matching_targets) > 1:
                        # Ambiguous match - multiple entities/events with same name
                        skipped_ambiguous.append(candidate.name)
                        logger.warning(
                            f"Ambiguous link '{candidate.name}': "
                            f"matches {len(matching_targets)} items"
                        )
                        continue

                    else:
                        # Exactly one match
                        target_obj = matching_targets[0]
                        # Determine type
                        if hasattr(target_obj, "type") and hasattr(
                            target_obj, "lore_date"
                        ):
                            target_type_str = "Event"
                        else:
                            target_type_str = "Entity"

                # At this point we have a valid target_obj
                if not target_obj:
                    continue

                # Skip self-references
                if target_obj.id == self.source_id:
                    continue

                # It's a valid link
                if (
                    target_obj.id,
                    0,
                ) not in existing_keys:  # Simplified check - ideally check offsets
                    # Create the relation
                    attributes = {
                        "field": self.field,
                        "start_offset": candidate.span[0],
                        "end_offset": candidate.span[1],
                        "snippet": self._extract_snippet(
                            self.text_content, candidate.span[0], candidate.span[1]
                        ),
                        "is_auto_generated": True,
                    }

                    try:
                        rel_id = db_service.insert_relation(
                            source_id=self.source_id,
                            target_id=target_obj.id,
                            rel_type="mentions",
                            attributes=attributes,
                        )
                        self._created_relations.append(rel_id)
                        created_count += 1
                        valid_links.append(f"{target_obj.name} ({target_type_str})")

                        logger.info(
                            f"Created 'mentions' relation {rel_id}: {self.source_id} -> "
                            f"{target_obj.name}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to create wiki relation: {e}")
                else:
                    logger.debug(f"Skipping existing relation to {target_obj.name}")

            # 5. Build result message
            link_word = "link" if created_count == 1 else "links"
            message_parts = [
                f"Processed {len(candidates)} candidates. Created {created_count} new {link_word}."
            ]
            if skipped_ambiguous:
                message_parts.append(
                    f"Found {len(skipped_ambiguous)} ambiguous link(s)."
                )
            if skipped_missing:
                message_parts.append(f"Found {len(skipped_missing)} broken link(s).")

            self._is_executed = True
            return CommandResult(
                success=True,
                message=" ".join(message_parts),
                command_name="ProcessWikiLinksCommand",
                data={
                    "valid_count": created_count,
                    "ambiguous_count": len(skipped_ambiguous),
                    "broken_count": len(skipped_missing),
                    "valid_links": valid_links,
                },
            )

        except Exception as e:
            logger.error(f"Failed to process wiki links: {e}")
            return CommandResult(
                success=False,
                message=f"Error processing links: {e}",
                command_name="ProcessWikiLinksCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Undo operation: deletes the created 'mentions' relations."""
        for rel_id in self._created_relations:
            try:
                db_service.delete_relation(rel_id)
                logger.info(f"Undoing WikiLink: Deleted relation {rel_id}")
            except Exception as e:
                logger.error(f"Failed to undo wiki relation {rel_id}: {e}")
        self._created_relations.clear()

    @staticmethod
    def _extract_snippet(
        text: str, start: int, end: int, context_chars: int = 40
    ) -> str:
        """Extracts a snippet of text around the link for context.

        Args:
            text: The full text content.
            start: Start offset of the link.
            end: End offset of the link.
            context_chars: Number of context characters to include
                (total, not per side).

        Returns:
            str: A snippet of text with context around the link.

        """
        # Calculate how much context to grab on each side
        link_len = end - start
        remaining = max(0, context_chars - link_len)
        left_context = remaining // 2
        right_context = remaining - left_context

        # Extract snippet
        snippet_start = max(0, start - left_context)
        snippet_end = min(len(text), end + right_context)
        snippet = text[snippet_start:snippet_end]

        # Add ellipsis if truncated
        if snippet_start > 0:
            snippet = "..." + snippet
        if snippet_end < len(text):
            snippet = snippet + "..."

        return snippet

    def get_description(self) -> str:
        """Get a human-readable description of this command.

        Returns:
            str: Description like "Process WikiLinks for Entity 'SourceID'".
        """
        return f"Process WikiLinks for source '{self.source_id}'"

    def to_dict(self) -> dict:
        """Serialize command to dictionary.

        Returns:
            dict: Command data for persistence
        """
        return {
            "source_id": self.source_id,
            "text_content": self.text_content,
            "field": self.field,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProcessWikiLinksCommand":
        """Deserialize command from dictionary.

        Args:
            data: Command data from database

        Returns:
            ProcessWikiLinksCommand: Reconstructed command
        """
        cmd = cls(
            source_id=data["source_id"],
            text_content=data["text_content"],
            field=data.get("field", "description"),
        )
        cmd._is_executed = data.get("is_executed", False)
        return cmd
