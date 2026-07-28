"""Wiki Commands Module.

Commands for processing WikiLinks and updating relations.
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List

from src.commands.base_command import BaseCommand, CommandResult
from src.services.db_service import DatabaseService
from src.services.text_parser import WikiLinkParser

logger = logging.getLogger(__name__)


class ProcessWikiLinksCommand(BaseCommand):
    """Reconcile derived ``mentions`` relations with the current wikilink text.

    This command:
    - Parses WikiLinks from text content
    - Resolves names to entities (case-insensitive, including aliases)
    - Stores one relation per source-target with occurrence metadata
    - Skips ambiguous matches (multiple entities with same name/alias)
    - Creates, updates, and deletes derived relations to match the current field
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
        self._before_relations: List[Dict[str, Any]] = []
        self._after_relations: List[Dict[str, Any]] = []
        self._has_reconciled_state = False
        self._is_executed: bool = False

    def execute(self, db_service: DatabaseService) -> CommandResult:  # noqa: C901
        """Resolve the current text and atomically reconcile its mentions."""
        try:
            logger.info(f"Processing WikiLinks for source {self.source_id}")

            if self._has_reconciled_state and not self._is_executed:
                db_service.restore_mentions(self.source_id, self._after_relations)
                self._is_executed = True
                return CommandResult(
                    success=True,
                    message="Restored reconciled wikilink relations.",
                    command_name="ProcessWikiLinksCommand",
                    data={
                        "valid_count": len(self._after_relations),
                        "occurrence_count": sum(
                            len(
                                relation.get("attributes", {}).get(
                                    "occurrences", []
                                )
                            )
                            for relation in self._after_relations
                        ),
                        "created_count": 0,
                        "updated_count": 0,
                        "deleted_count": 0,
                        "ambiguous_count": 0,
                        "broken_count": 0,
                        "valid_links": [],
                    },
                )

            candidates = WikiLinkParser.extract_links(self.text_content)
            all_entities = db_service.get_all_entities()
            name_to_targets: Dict[str, List] = defaultdict(list)

            for entity in all_entities:
                name_key = entity.name.casefold()
                name_to_targets[name_key].append(entity)

                aliases = entity.attributes.get("aliases", [])
                if isinstance(aliases, list):
                    for alias in aliases:
                        if isinstance(alias, str):
                            alias_key = alias.casefold()
                            name_to_targets[alias_key].append(entity)

            all_events = db_service.get_all_events()
            for event in all_events:
                name_key = event.name.casefold()
                name_to_targets[name_key].append(event)

            occurrences_by_target: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            skipped_ambiguous: List[str] = []
            skipped_missing: List[str] = []
            valid_links_by_target: Dict[str, str] = {}

            for candidate in candidates:
                target_obj: Any = None
                target_type_str = "Entity"

                if candidate.is_id_based:
                    assert candidate.target_id is not None
                    target_obj = db_service.get_entity(candidate.target_id)
                    if target_obj:
                        target_type_str = "Entity"
                    else:
                        target_obj = db_service.get_event(candidate.target_id)
                        if target_obj:
                            target_type_str = "Event"

                    if not target_obj:
                        skipped_missing.append(
                            candidate.modifier or candidate.target_id
                        )
                        logger.warning(f"Broken ID-based link: {candidate.target_id}")
                        continue

                else:
                    assert candidate.name is not None
                    name_key = candidate.name.casefold()
                    matching_targets = name_to_targets.get(name_key, [])

                    if len(matching_targets) == 0:
                        skipped_missing.append(candidate.name)
                        logger.debug(f"No target found for link: {candidate.name}")
                        continue

                    elif len(matching_targets) > 1:
                        skipped_ambiguous.append(candidate.name)
                        logger.warning(
                            f"Ambiguous link '{candidate.name}': "
                            f"matches {len(matching_targets)} items"
                        )
                        continue

                    else:
                        target_obj = matching_targets[0]
                        if hasattr(target_obj, "type") and hasattr(
                            target_obj, "lore_date"
                        ):
                            target_type_str = "Event"
                        else:
                            target_type_str = "Entity"

                if not target_obj:
                    continue

                if target_obj.id == self.source_id:
                    continue

                occurrences_by_target[target_obj.id].append(
                    {
                        "field": self.field,
                        "start_offset": candidate.span[0],
                        "end_offset": candidate.span[1],
                        "snippet": WikiLinkParser.extract_snippet(
                            self.text_content, candidate.span[0], candidate.span[1]
                        ),
                    }
                )
                valid_links_by_target[target_obj.id] = (
                    f"{target_obj.name} ({target_type_str})"
                )

            reconciliation = db_service.reconcile_mentions(
                self.source_id,
                self.field,
                dict(occurrences_by_target),
            )
            self._before_relations = reconciliation["before"]
            self._after_relations = reconciliation["after"]
            self._has_reconciled_state = True
            self._is_executed = True

            occurrence_count = sum(map(len, occurrences_by_target.values()))
            target_count = len(occurrences_by_target)
            message_parts = [
                f"Processed {len(candidates)} candidates and reconciled "
                f"{target_count} mention relation(s)."
            ]
            if skipped_ambiguous:
                message_parts.append(
                    f"Found {len(skipped_ambiguous)} ambiguous link(s)."
                )
            if skipped_missing:
                message_parts.append(f"Found {len(skipped_missing)} broken link(s).")

            return CommandResult(
                success=True,
                message=" ".join(message_parts),
                command_name="ProcessWikiLinksCommand",
                data={
                    "valid_count": target_count,
                    "occurrence_count": occurrence_count,
                    "created_count": reconciliation["created_count"],
                    "updated_count": reconciliation["updated_count"],
                    "deleted_count": reconciliation["deleted_count"],
                    "ambiguous_count": len(skipped_ambiguous),
                    "broken_count": len(skipped_missing),
                    "valid_links": list(valid_links_by_target.values()),
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
        """Restore the exact mentions snapshot that preceded reconciliation."""
        if not self._is_executed:
            return

        db_service.restore_mentions(self.source_id, self._before_relations)
        self._is_executed = False

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
            "before_relations": self._before_relations,
            "after_relations": self._after_relations,
            "has_reconciled_state": self._has_reconciled_state,
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
        cmd._before_relations = data.get("before_relations", [])
        cmd._after_relations = data.get("after_relations", [])
        cmd._has_reconciled_state = data.get("has_reconciled_state", False)
        cmd._is_executed = data.get("is_executed", False)
        return cmd
