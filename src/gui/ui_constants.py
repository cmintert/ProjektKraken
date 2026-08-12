"""Standard GUI spacing and interaction constants."""


class Spacing:
    """Standard spacing values on an eight-point grid."""

    COMPACT = 4
    STANDARD = 8
    WIDE = 12
    SECTION = 16
    LARGE_SECTION = 24
    EXTRA_LARGE = 32


class Margins:
    """Standard margin values on an eight-point grid."""

    NONE = 0
    COMPACT = 8
    STANDARD = 16
    WIDE = 24
    EXTRA_WIDE = 32


# A new raster dab every quarter-radius keeps typical strokes gapless without
# generating excessive overlapping samples.
RASTER_DAB_SPACING_FACTOR: float = 0.25
