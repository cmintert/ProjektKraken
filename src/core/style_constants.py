"""Visual Style Constants Module.

Defines the single-source-of-truth keys and default values for the unified
visual styling system.  Both the Map (MarkerItem) and Graph (GraphBuilder)
layers resolve visual properties through these constants via the
:class:`~src.services.visual_resolver.VisualResolver`.

Attribute keys use a ``_v_`` prefix to distinguish visual overrides from
user-defined custom attributes in the ``attributes`` dict.
"""

# ---------------------------------------------------------------------------
# Attribute keys stored in Entity / Event / MapFeature ``attributes`` dicts
# ---------------------------------------------------------------------------

V_FILL: str = "_v_fill"
"""Hex color for fill / background (e.g. ``"#E02A2A"``)."""

V_BORDER: str = "_v_border"
"""Hex color for the border / outline."""

V_SIZE_SCALE: str = "_v_size_scale"
"""General visual scale multiplier for consumers outside map-marker sizing."""

V_BORDER_WIDTH: str = "_v_border_width"
"""Integer pixel width of the border / outline."""

V_ICON: str = "_v_icon"
"""Icon filename (e.g. ``"castle.svg"``)."""

# ---------------------------------------------------------------------------
# Hard-coded fallback defaults (used when neither attributes nor theme apply)
# ---------------------------------------------------------------------------

BASE_SIZE: int = 24
"""Default marker / node diameter in pixels."""

BASE_BORDER_WIDTH: int = 2
"""Default border width in pixels."""

BASE_SCALE: float = 1.0
"""Default size multiplier (1.0 = 100 %)."""

DEFAULT_ENTITY_COLOR: str = "#4DA6FF"
"""Fallback fill color for entities (blue)."""

DEFAULT_EVENT_COLOR: str = "#FF9900"
"""Fallback fill color for events (orange)."""

DEFAULT_BORDER_COLOR: str = "#FFFFFF"
"""Fallback border color (white)."""

# ---------------------------------------------------------------------------
# UI dialog constraints
# ---------------------------------------------------------------------------

MIN_SCALE: float = 0.5
"""Minimum allowed size scale in the UI."""

MAX_SCALE: float = 3.0
"""Maximum allowed size scale in the UI."""

MIN_BORDER_WIDTH: int = 0
"""Minimum border width in the UI (pixels)."""

MAX_BORDER_WIDTH: int = 10
"""Maximum border width in the UI (pixels)."""
