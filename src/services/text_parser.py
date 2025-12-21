"""
Text Parser Service.
Handles parsing of WikiLinks and other text processing tasks.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class LinkCandidate:
    """
    Represents a parsed WikiLink with metadata.

    Supports both legacy name-based and ID-based link formats:
    - Legacy: [[Name]] or [[Name|Label]]
    - ID-based: [[id:UUID|DisplayName]]

    Attributes:
        raw_text: The full [[...]] text including brackets.
        name: The target name (before pipe if present) or None if ID-based.
        modifier: The label/modifier (after pipe if present), or None.
        span: Tuple of (start_offset, end_offset) in the source text.
        target_id: The UUID if this is an ID-based link, None otherwise.
        is_id_based: True if this link uses the id:UUID format.
    """

    raw_text: str
    name: Optional[str]
    modifier: Optional[str]
    span: Tuple[int, int]
    target_id: Optional[str] = None
    is_id_based: bool = False


class WikiLinkParser:
    """
    Parser for extracting WikiLinks from text.

    Supports both legacy and ID-based link formats:
    - Legacy: [[Name]] or [[Name|Label]]
    - ID-based: [[id:UUID|DisplayName]]

    The ID-based format ensures links remain valid when names change.
    """

    # Regex to capture [[Name]] or [[Name|Label]] or [[id:UUID|DisplayName]]
    # Group 1: full target (could be "id:UUID" or "Name")
    # Group 2: modifier/label (optional, after pipe)
    WIKILINK_RE = re.compile(r"\[\[([^[\]|]+)(?:\|([^\]]+))?\]\]")

    # Regex to detect ID-based format: "id:UUID"
    ID_PREFIX_RE = re.compile(r"^id:([a-f0-9-]{36})$", re.IGNORECASE)

    @staticmethod
    def extract_links(text: str) -> List[LinkCandidate]:
        """
        Extracts WikiLinks from text as ordered LinkCandidate objects.

        Each link includes the name or ID, optional modifier, and position offsets.
        Duplicates are preserved in order of appearance.

        Supports both formats:
        - [[EntityName]] or [[EntityName|DisplayLabel]]
        - [[id:550e8400-e29b-41d4-a716-446655440000|Gandalf]]

        Args:
            text: The text to parse for WikiLinks.

        Returns:
            List[LinkCandidate]: Ordered list of parsed links with metadata.
        """
        if not text:
            return []

        candidates = []
        for match in WikiLinkParser.WIKILINK_RE.finditer(text):
            raw_text = match.group(0)  # Full [[...]] text
            target = match.group(1).strip()
            modifier = match.group(2).strip() if match.group(2) else None
            span = (match.start(), match.end())

            # Check if this is an ID-based link
            id_match = WikiLinkParser.ID_PREFIX_RE.match(target)
            if id_match:
                # ID-based link: [[id:UUID|DisplayName]]
                target_id = id_match.group(1)
                candidates.append(
                    LinkCandidate(
                        raw_text=raw_text,
                        name=None,  # Name is in modifier for ID-based links
                        modifier=modifier,
                        span=span,
                        target_id=target_id,
                        is_id_based=True,
                    )
                )
            else:
                # Legacy name-based link: [[Name]] or [[Name|Label]]
                candidates.append(
                    LinkCandidate(
                        raw_text=raw_text,
                        name=target,
                        modifier=modifier,
                        span=span,
                        target_id=None,
                        is_id_based=False,
                    )
                )

        return candidates

    @staticmethod
    def format_id_link(target_id: str, display_name: str) -> str:
        """
        Creates an ID-based wiki link string.

        Args:
            target_id: The UUID of the target entity/event.
            display_name: The human-readable name to display.

        Returns:
            str: Formatted link like "[[id:UUID|DisplayName]]"
        """
        return f"[[id:{target_id}|{display_name}]]"

    @staticmethod
    def format_name_link(name: str, display_label: Optional[str] = None) -> str:
        """
        Creates a legacy name-based wiki link string.

        Args:
            name: The target name.
            display_label: Optional display label (after pipe).

        Returns:
            str: Formatted link like "[[Name]]" or "[[Name|Label]]"
        """
        if display_label:
            return f"[[{name}|{display_label}]]"
        return f"[[{name}]]"
