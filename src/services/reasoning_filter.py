"""Reasoning Filter Module.

Provides robust filtering of reasoning/thinking tags from LLM output.
Handles complete tag pairs, unclosed/truncated tags, pipe-delimited tags,
and various model-specific formats.

Supported tag formats:
    - Standard XML:     <think>...</think>
    - Pipe-delimited:   <|think|>...<|/think|>
    - With attributes:  <think type="internal">...</think>
    - Unclosed/truncated: <think>... (no closing tag)
"""

import logging
import re
from typing import List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tag names that are treated as reasoning / internal monologue.
# Order does not matter — they are combined into alternation groups.
# ---------------------------------------------------------------------------
REASONING_TAG_NAMES: List[str] = [
    "think",
    "thinking",
    "thought",
    "reasoning",
    "scratchpad",
    "reflection",
    "inner_monologue",
    "internal",
]

_TAG_NAMES_ALT = "|".join(REASONING_TAG_NAMES)

# ---------------------------------------------------------------------------
# Pattern 1 — Standard XML-style complete pairs
#   <think>...</think>   <thinking>...</thinking>   etc.
#   Also tolerates optional attributes:  <think type="x">
#   Also tolerates whitespace around the tag name:  < think >
# ---------------------------------------------------------------------------
_PATTERN_STANDARD = re.compile(
    rf"<\s*({_TAG_NAMES_ALT})\b[^>]*>.*?<\s*/\s*\1\s*>",
    re.DOTALL | re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Pattern 2 — Pipe-delimited complete pairs  (Qwen-3, etc.)
#   <|think|>...<|/think|>
# ---------------------------------------------------------------------------
_PATTERN_PIPE = re.compile(
    rf"<\|\s*({_TAG_NAMES_ALT})\s*\|>.*?<\|\s*/\s*\1\s*\|>",
    re.DOTALL | re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Pattern 3 — Unclosed / truncated standard tags
#   <think>...  (runs to the end of the string with no closing tag)
# ---------------------------------------------------------------------------
_PATTERN_UNCLOSED_STANDARD = re.compile(
    rf"<\s*({_TAG_NAMES_ALT})\b[^>]*>.*",
    re.DOTALL | re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Pattern 4 — Unclosed / truncated pipe-delimited tags
#   <|think|>...  (runs to the end of the string with no closing tag)
# ---------------------------------------------------------------------------
_PATTERN_UNCLOSED_PIPE = re.compile(
    rf"<\|\s*({_TAG_NAMES_ALT})\s*\|>.*",
    re.DOTALL | re.IGNORECASE,
)


def filter_reasoning_tags(text: str) -> str:
    """Remove reasoning/thinking tags and their content from LLM output.

    Applies multiple filter passes in order of specificity:
    1. Complete standard XML tag pairs  ``<think>...</think>``
    2. Complete pipe-delimited tag pairs ``<|think|>...<|/think|>``
    3. Unclosed / truncated standard tags ``<think>... (to end of string)``
    4. Unclosed / truncated pipe-delimited tags ``<|think|>... (to end)``

    Unclosed-tag patterns are applied **after** complete-pair patterns so
    that a properly closed block is always preferred over a greedy
    "to end of string" match.

    Args:
        text: Raw LLM output text.

    Returns:
        Cleaned text with reasoning blocks removed and whitespace normalised.

    """
    if not text:
        return text

    result = text

    # --- Pass 1 & 2: remove complete pairs first ---
    result = _PATTERN_STANDARD.sub("", result)
    result = _PATTERN_PIPE.sub("", result)

    # --- Pass 3 & 4: remove unclosed / truncated blocks ---
    result = _PATTERN_UNCLOSED_STANDARD.sub("", result)
    result = _PATTERN_UNCLOSED_PIPE.sub("", result)

    # --- Tidy up whitespace artefacts left by removal ---
    result = _normalise_whitespace(result)

    chars_removed = len(text) - len(result)
    if chars_removed > 0:
        logger.debug(
            "Reasoning filter removed %d characters from %d-char input",
            chars_removed,
            len(text),
        )

    return result


def _normalise_whitespace(text: str) -> str:
    """Collapse runs of 3+ newlines into 2 and strip leading/trailing space.

    Args:
        text: Text that may contain excessive blank lines after tag removal.

    Returns:
        Cleaned text.

    """
    # Collapse 3+ consecutive newlines (possibly with whitespace between)
    # into exactly two newlines (one blank line).
    text = re.sub(r"(\s*\n){3,}", "\n\n", text)
    return text.strip()
