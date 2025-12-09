"""
Text Parser Service.
Handles parsing of WikiLinks and other text processing tasks.
"""

import re
from typing import List, Set


class WikiLinkParser:
    """
    Parser for extracting WikiLinks from text.
    Links are expected to be in the format [[Name]] or [[Name|Label]].
    """

    # Regex to capture [[Target]] or [[Target|Label]]
    # Capture group 1 is the full content inside brackets.
    LINK_PATTERN = re.compile(r"\[\[(.*?)\]\]")

    @staticmethod
    def extract_links(text: str) -> Set[str]:
        """
        Extracts unique link targets from the given text.
        Handles pipe naming (Target|Label) by returning 'Target'.

        Args:
            text (str): The text to parse.

        Returns:
            Set[str]: A set of unique target names found in the text.
        """
        if not text:
            return set()

        matches = WikiLinkParser.LINK_PATTERN.findall(text)
        targets = set()

        for match in matches:
            # Handle [[Target|Label]] format
            if "|" in match:
                target, _ = match.split("|", 1)
                targets.add(target.strip())
            else:
                targets.add(match.strip())

        return targets
