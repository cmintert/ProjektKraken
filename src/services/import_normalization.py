"""Import Normalization Module.

Provides utilities for normalizing names and other fields for consistent
deduplication matching during imports.
"""

from typing import Optional


def normalize_name(name: Optional[str]) -> str:
    """Normalize a name for consistent matching.

    Performs the following operations:
    1. Handles None (returns "")
    2. Strips leading/trailing whitespace
    3. Collapses multiple internal spaces to single space
    4. Converts to lowercase

    Args:
        name: The raw name string.

    Returns:
        The normalized name string.
    """
    if not name:
        return ""

    # split() without arguments splits by any whitespace and removes empty strings,
    # effectively collapsing multiple spaces and trimming.
    return " ".join(name.split()).lower()
