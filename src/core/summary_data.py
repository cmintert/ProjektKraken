"""Summary Data Module.

Defines data structure for storing AI-generated summaries with metadata.
"""

import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Dict, Literal

DEFAULT_SUMMARY_PROMPT = (
    "Summarize the following worldbuilding item neutrally, preserving the "
    "essential facts and original tone.\n\n"
    "Item Data:\n"
    "Type: {type}\n"
    "Name: {name}\n"
    "Description: {description}"
)

LEGACY_SUMMARY_PROMPTS = frozenset(
    {
        (
            "Summarize the following worldbuilding item neutrally, "
            "preserving all facts and the original tone. "
            "Crucially, PRESERVE any [[Wiki Links]] exactly as they appear.\n\n"
            "Item Data:\n"
            "Type: {type}\n"
            "Name: {name}\n"
            "Description: {description}"
        ),
        (
            "Summarize the following worldbuilding item neutrally, "
            "preserving all facts and the original tone. "
            "Crucially, PRESERVE any [[Wiki Links]] exactly as they appear.\n\n"
            "--- DATA: ENTITY/EVENT DETAILS ---\n"
            "Type: {type}\n"
            "Name: {name}\n"
            "Description: {description}\n"
            "--- END DATA ---"
        ),
        (
            "Summarize the following content in a clear, structured, and concise "
            "way. Focus on the essential ideas, remove filler, and present the "
            "information as a summary.\n\n"
            "Requirements:\n"
            "- Start with a short, high-level overview (2–3 sentences)\n"
            "- Follow with bullet points capturing key details, decisions, and "
            "insights\n"
            "- Preserve factual accuracy without adding new information\n"
            "- Use neutral, professional language\n"
            "- Avoid repetition and avoid quoting large sections verbatim\n\n"
            "Content Data:\n"
            "Type: {type}\n"
            "Name: {name}\n"
            "Description: {description}"
        ),
    }
)

SUMMARY_MAX_WORDS = 150
SUMMARY_SHORT_MAX_WORDS = 20
SUMMARY_TARGET_WORD_RATIO = 0.22
SUMMARY_WORD_RATIO = 0.30
SUMMARY_SHORT_SOURCE_WORDS = 50


def count_summary_words(text: str) -> int:
    """Count whitespace-delimited words in summary source or output text."""
    return len(text.split())


def calculate_summary_word_limit(description: str) -> int:
    """Return the enforced AI-summary word limit for a description."""
    source_words = count_summary_words(description)
    if source_words < SUMMARY_SHORT_SOURCE_WORDS:
        return min(SUMMARY_SHORT_MAX_WORDS, max(0, source_words - 1))
    return min(SUMMARY_MAX_WORDS, int(source_words * SUMMARY_WORD_RATIO))


def calculate_summary_target_words(description: str) -> int:
    """Return the lower prompt target used to leave room below the hard limit."""
    source_words = count_summary_words(description)
    hard_limit = calculate_summary_word_limit(description)
    if source_words < SUMMARY_SHORT_SOURCE_WORDS:
        return hard_limit
    return min(hard_limit, max(1, int(source_words * SUMMARY_TARGET_WORD_RATIO)))


def normalize_summary_prompt_template(template: str) -> str:
    """Replace obsolete bundled defaults without changing custom prompts."""
    if template.strip() in LEGACY_SUMMARY_PROMPTS:
        return DEFAULT_SUMMARY_PROMPT
    return template


def calculate_summary_source_hash(item: Any) -> str:
    """Calculate the stable hash used to detect stale item summaries."""
    content = f"{item.name}|{item.type}|{item.description}"
    if hasattr(item, "lore_date"):
        content += f"|{item.lore_date}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def is_summary_stale(item: Any) -> bool:
    """Return whether an item's cached summary is absent or out of date.

    This check depends only on the serialized item snapshot, so GUI code can
    evaluate it without holding a database-backed ``SummaryService``.

    Args:
        item: Entity or event snapshot containing an ``attributes`` mapping.

    Returns:
        ``True`` when no summary exists, its metadata is malformed, or its
        stored source hash does not match the current item content.

    """
    summary_data = item.attributes.get("_summary_data")
    if not isinstance(summary_data, dict):
        return True
    stored_hash = summary_data.get("hash")
    return stored_hash != calculate_summary_source_hash(item)


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
