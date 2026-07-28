"""Summary Data Module.

Defines data structure for storing AI-generated summaries with metadata.
"""

import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Dict, Literal

DEFAULT_SUMMARY_PROMPT = (
    "Summarize the following worldbuilding item neutrally, preserving the "
    "essential facts and original tone. Preserve any [[Wiki Links]] exactly "
    "as they appear.\n\n"
    "Item Data:\n"
    "Type: {type}\n"
    "Name: {name}\n"
    "Description: {description}"
)

SUMMARY_MAX_WORDS = 150
SUMMARY_WORD_RATIO = 0.30
SUMMARY_SHORT_SOURCE_WORDS = 50


def count_summary_words(text: str) -> int:
    """Count whitespace-delimited words in summary source or output text."""
    return len(text.split())


def calculate_summary_word_limit(description: str) -> int:
    """Return the enforced AI-summary word limit for a description."""
    source_words = count_summary_words(description)
    return min(SUMMARY_MAX_WORDS, int(source_words * SUMMARY_WORD_RATIO))


def calculate_summary_source_hash(item: Any) -> str:
    """Calculate the stable hash used to detect stale item summaries."""
    content = f"{item.name}|{item.type}|{item.description}"
    if hasattr(item, "lore_date"):
        content += f"|{item.lore_date}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class SummaryData:
    """Data structure for storing item summaries and metadata."""

    text: str
    hash: str
    timestamp: float
    model: str
    detail_level: str = "standard"
    origin: Literal["ai", "manual"] = "ai"

    def to_dict(self) -> Dict[str, Any]:
        """Converts to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation of the summary data.

        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SummaryData":
        """Creates SummaryData from a dictionary.

        Args:
            data: Dictionary containing summary data fields.

        Returns:
            SummaryData: New instance populated with the provided data.

        """
        return cls(**data)
