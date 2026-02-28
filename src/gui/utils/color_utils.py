"""Color utilities for ProjektKraken UI."""

import hashlib

from PySide6.QtGui import QColor


def get_hashed_color(seed: str) -> QColor:
    """Generate a stable distinct color based on a seed string.

    This uses an MD5 hash of the string to deterministically
    select a hue from 0-359, while keeping saturation and lightness
    constant to ensure readability in dark mode.

    Args:
        seed: String to hash to determine hue.

    Returns:
        QColor configured with the generated color.
    """
    hash_val = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    hue = hash_val % 360

    # Fixed saturation and lightness for dark mode readability
    # Saturation: ~150/255 (moderate), Lightness: ~180/255 (bright)
    return QColor.fromHsl(hue, 150, 180)
