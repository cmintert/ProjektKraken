"""Obsidian Exporter Service.

Exports entities and events as Obsidian-compatible markdown files with YAML frontmatter.
Creates flat folder structure with duplicate name handling.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.core.entities import Entity
from src.core.events import Event

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    """Result of an Obsidian export operation."""

    success: bool
    files_created: int
    output_dir: Path
    errors: List[str]


class ObsidianExporter:
    """Exports entities and events as Obsidian-compatible markdown files.

    Creates individual .md files with YAML frontmatter for each entity and event.
    Handles duplicate filenames with counter suffix (e.g., "Name (2).md"). Adds "##
    Related" section with wiki-links to related items.
    """

    # Characters not allowed in filenames
    INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
    MAX_FILENAME_LENGTH = 200  # Leave room for counter and .md extension

    def __init__(self, db_service: Any) -> None:
        """Initialize the exporter.

        Args:
            db_service: Database service for fetching entities, events, relations.

        """
        self._db = db_service

    def export_to_folder(
        self,
        output_dir: Path,
        include_relations: bool = True,
    ) -> ExportResult:
        """Export all entities and events to a folder as Obsidian-compatible .md files.

        Args:
            output_dir: Directory to write files to.
            include_relations: Whether to include "## Related" section.

        Returns:
            ExportResult with statistics and any errors encountered.

        """
        errors: List[str] = []
        files_created = 0

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Fetch all data
        entities = self._db.get_all_entities()
        events = self._db.get_all_events()

        # Build ID-to-name map for wiki-link resolution
        id_to_name: Dict[str, str] = {}
        for entity in entities:
            # entities are objects, not dicts
            id_to_name[entity.id] = entity.name
        for event in events:
            # events are objects, not dicts
            id_to_name[event.id] = event.name

        # Track used filenames to handle duplicates
        used_filenames: Dict[str, int] = {}

        # Export entities
        for entity in entities:
            try:
                # entity is already an object
                relations = (
                    self._get_relations_for_item(entity.id, id_to_name)
                    if include_relations
                    else []
                )
                content = self._build_entity_markdown(entity, relations)
                filename = self._get_unique_filename(entity.name, used_filenames)
                filepath = output_dir / filename

                filepath.write_text(content, encoding="utf-8")
                files_created += 1
            except Exception as e:
                # Use getattr for safety in error logging if object is malformed
                name = getattr(entity, "name", "Unknown Entity")
                errors.append(f"Failed to export entity '{name}': {e}")
                logger.error(f"Entity export error: {e}")

        # Export events
        for event in events:
            try:
                # event is already an object
                relations = (
                    self._get_relations_for_item(event.id, id_to_name)
                    if include_relations
                    else []
                )
                content = self._build_event_markdown(event, relations)
                filename = self._get_unique_filename(event.name, used_filenames)
                filepath = output_dir / filename

                filepath.write_text(content, encoding="utf-8")
                files_created += 1
            except Exception as e:
                name = getattr(event, "name", "Unknown Event")
                errors.append(f"Failed to export event '{name}': {e}")
                logger.error(f"Event export error: {e}")

        return ExportResult(
            success=len(errors) == 0,
            files_created=files_created,
            output_dir=output_dir,
            errors=errors,
        )

    def _get_unique_filename(self, name: str, used_filenames: Dict[str, int]) -> str:
        """Generate a unique filename, adding counter for duplicates.

        Args:
            name: The desired base name.
            used_filenames: Dict tracking used names and their counts.

        Returns:
            Unique filename like "Name.md" or "Name (2).md".

        """
        sanitized = self._sanitize_filename(name)
        base_name = sanitized[: self.MAX_FILENAME_LENGTH]

        if base_name not in used_filenames:
            used_filenames[base_name] = 1
            return f"{base_name}.md"

        # Increment counter for duplicates
        used_filenames[base_name] += 1
        count = used_filenames[base_name]
        return f"{base_name} ({count}).md"

    def _sanitize_filename(self, name: str) -> str:
        """Remove invalid characters from filename.

        Args:
            name: Original name.

        Returns:
            Sanitized filename safe for all filesystems.

        """
        sanitized = self.INVALID_FILENAME_CHARS.sub("", name)
        sanitized = sanitized.strip(". ")  # Remove leading/trailing dots and spaces
        return sanitized if sanitized else "Untitled"

    def _get_relations_for_item(
        self, item_id: str, id_to_name: Dict[str, str]
    ) -> List[Dict[str, str]]:
        """Get related items for an entity or event.

        Args:
            item_id: ID of the source item.
            id_to_name: Mapping of IDs to names for wiki-link resolution.

        Returns:
            List of dicts with 'name' and 'rel_type' for each related item.

        """
        relations = []
        try:
            rel_dicts = self._db.get_relations(item_id)
            for rel in rel_dicts:
                target_id = rel.get("target_id")
                if target_id and target_id in id_to_name:
                    relations.append(
                        {
                            "name": id_to_name[target_id],
                            "rel_type": rel.get("rel_type", "related"),
                        }
                    )
        except Exception as e:
            logger.warning(f"Failed to get relations for {item_id}: {e}")
        return relations

    def _build_entity_markdown(
        self, entity: Entity, relations: List[Dict[str, str]]
    ) -> str:
        """Build complete markdown content for an entity.

        Args:
            entity: The entity to export.
            relations: List of related items.

        Returns:
            Complete markdown string with frontmatter and content.

        """
        lines = []

        # YAML frontmatter
        lines.append("---")
        lines.append(f'title: "{self._escape_yaml_string(entity.name)}"')
        lines.append(f"type: {entity.type}")

        tags = entity.tags
        if tags:
            lines.append("tags:")
            for tag in tags:
                lines.append(f"  - {tag}")

        lines.append(f'uid: "{entity.id}"')
        lines.append(f"created: {self._format_timestamp(entity.created_at)}")
        lines.append(f"modified: {self._format_timestamp(entity.modified_at)}")
        lines.append("source: ProjektKraken")
        lines.append("---")
        lines.append("")

        # Body content
        if entity.description:
            lines.append(entity.description.strip())
            lines.append("")

        # Related section
        if relations:
            lines.append("## Related")
            lines.append("")
            for rel in relations:
                lines.append(f"- {rel['rel_type']}: [[{rel['name']}]]")
            lines.append("")

        return "\n".join(lines)

    def _build_event_markdown(
        self, event: Event, relations: List[Dict[str, str]]
    ) -> str:
        """Build complete markdown content for an event.

        Args:
            event: The event to export.
            relations: List of related items.

        Returns:
            Complete markdown string with frontmatter and content.

        """
        lines = []

        # YAML frontmatter
        lines.append("---")
        lines.append(f'title: "{self._escape_yaml_string(event.name)}"')
        lines.append(f"type: {event.type}")

        tags = event.tags
        if tags:
            lines.append("tags:")
            for tag in tags:
                lines.append(f"  - {tag}")

        lines.append(f"lore_date: {event.lore_date}")
        if event.lore_duration > 0:
            lines.append(f"lore_duration: {event.lore_duration}")

        lines.append(f'uid: "{event.id}"')
        lines.append(f"created: {self._format_timestamp(event.created_at)}")
        lines.append(f"modified: {self._format_timestamp(event.modified_at)}")
        lines.append("source: ProjektKraken")
        lines.append("---")
        lines.append("")

        # Body content
        if event.description:
            lines.append(event.description.strip())
            lines.append("")

        # Related section
        if relations:
            lines.append("## Related")
            lines.append("")
            for rel in relations:
                lines.append(f"- {rel['rel_type']}: [[{rel['name']}]]")
            lines.append("")

        return "\n".join(lines)

    def _escape_yaml_string(self, value: str) -> str:
        """Escape quotes in YAML string values."""
        return value.replace('"', '\\"')

    def _format_timestamp(self, timestamp: float) -> str:
        """Convert Unix timestamp to ISO date string."""
        try:
            return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            return "unknown"
