"""UI Constants Module.

Provides standardized spacing and margin constants for consistent layout following the
8-point grid system.
"""


class Spacing:
    """Standard spacing values (8-point grid)."""

    COMPACT = 4  # Half unit
    STANDARD = 8  # Base unit
    WIDE = 12  # 1.5x base
    SECTION = 16  # 2x base
    LARGE_SECTION = 24  # 3x base
    EXTRA_LARGE = 32  # 4x base


class Margins:
    """Standard margin values (8-point grid)."""

    NONE = 0
    COMPACT = 8  # Base unit
    STANDARD = 16  # 2x base
    WIDE = 24  # 3x base
    EXTRA_WIDE = 32  # 4x base


# Raster brush: dab spacing as a fraction of brush radius.
# 0.25 means a new dab every 25 % of the radius, keeping strokes gapless
# at typical painting speeds while avoiding excessive dab overlap.
RASTER_DAB_SPACING_FACTOR: float = 0.25
