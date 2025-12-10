"""
Text Parser Service.
Handles parsing of WikiLinks and other text processing tasks.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class LinkCandidate:
    """
    Represents a parsed WikiLink with metadata.

    Attributes:
        raw_text: The full [[...]] text including brackets.
        name: The target name (before pipe if present).
        modifier: The label/modifier (after pipe if present), or None.
        span: Tuple of (start_offset, end_offset) in the source text.
    """

    raw_text: str
    name: str
    modifier: str | None
    span: Tuple[int, int]


class WikiLinkParser:
    """
    Parser for extracting WikiLinks from text.
    Links are expected to be in the format [[Name]] or [[Name|Label]].
    """

    # Regex to capture [[Name]] or [[Name|Label]]
    # Group 1: name (target), Group 2: modifier/label (optional)
    WIKILINK_RE = re.compile(r"\[\[([^[\]|]+)(?:\|([^\]]+))?\]\]")

    @staticmethod
    def extract_links(text: str) -> List[LinkCandidate]:
        """
        Extracts WikiLinks from text as ordered LinkCandidate objects.

        Each link includes the name, optional modifier, and position offsets.
        Duplicates are preserved in order of appearance.

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
            name = match.group(1).strip()
            modifier = match.group(2).strip() if match.group(2) else None
            span = (match.start(), match.end())

            candidates.append(
                LinkCandidate(
                    raw_text=raw_text, name=name, modifier=modifier, span=span
                )
            )

        return candidates
