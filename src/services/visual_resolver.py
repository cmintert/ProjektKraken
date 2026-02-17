"""Visual Resolver Service.

Provides a single-source-of-truth for resolving visual properties (fill color,
border color, size, border width) for any object that carries an ``attributes``
dict (Entity, Event, MapFeature).

Resolution order (cascading):

1. **User Override** – value stored in ``attributes[key]``.
2. **Theme Fallback** – ``entity_main`` / ``event_main`` from ThemeManager.
3. **Hard Fallback** – constants defined in :mod:`src.core.style_constants`.
"""

import logging
from typing import Any, Dict, Optional

from src.core.style_constants import (
    BASE_BORDER_WIDTH,
    BASE_SCALE,
    BASE_SIZE,
    DEFAULT_BORDER_COLOR,
    DEFAULT_ENTITY_COLOR,
    DEFAULT_EVENT_COLOR,
    V_BORDER,
    V_BORDER_WIDTH,
    V_FILL,
    V_SIZE_SCALE,
)

logger = logging.getLogger(__name__)


def _get_theme_color(object_type: str) -> Optional[str]:
    """Fetches the theme color for the given object type.

    Args:
        object_type: ``"entity"`` or ``"event"``.

    Returns:
        Hex color string from the current theme, or None if unavailable.
    """
    try:
        from src.core.base_theme_manager import BaseThemeManager

        manager = BaseThemeManager()
        theme = manager.get_theme()
        if object_type == "entity":
            return theme.get("entity_main")
        elif object_type == "event":
            return theme.get("event_main")
    except Exception:
        pass
    return None


class VisualResolver:
    """Stateless resolver for cascading visual properties.

    All methods are static – no instance state is required.  Each method
    inspects the object's ``attributes`` dict first, then falls back to the
    current theme, and finally to the hard-coded constants.
    """

    @staticmethod
    def resolve_fill(
        attributes: Dict[str, Any],
        object_type: str = "entity",
    ) -> str:
        """Resolves the fill / background color.

        Args:
            attributes: The object's attributes dict.
            object_type: ``"entity"`` or ``"event"``.

        Returns:
            Hex color string.
        """
        override = attributes.get(V_FILL)
        if override and isinstance(override, str):
            return override

        theme_color = _get_theme_color(object_type)
        if theme_color:
            return theme_color

        if object_type == "event":
            return DEFAULT_EVENT_COLOR
        return DEFAULT_ENTITY_COLOR

    @staticmethod
    def resolve_border_color(
        attributes: Dict[str, Any],
        object_type: str = "entity",
    ) -> str:
        """Resolves the border / outline color.

        Args:
            attributes: The object's attributes dict.
            object_type: ``"entity"`` or ``"event"``.

        Returns:
            Hex color string.
        """
        override = attributes.get(V_BORDER)
        if override and isinstance(override, str):
            return override
        return DEFAULT_BORDER_COLOR

    @staticmethod
    def resolve_size(
        attributes: Dict[str, Any],
    ) -> int:
        """Resolves the computed pixel size (``BASE_SIZE * scale``).

        Args:
            attributes: The object's attributes dict.

        Returns:
            Integer pixel size.
        """
        scale = VisualResolver.resolve_scale(attributes)
        return int(BASE_SIZE * scale)

    @staticmethod
    def resolve_scale(
        attributes: Dict[str, Any],
    ) -> float:
        """Resolves the raw scale multiplier.

        Args:
            attributes: The object's attributes dict.

        Returns:
            Float scale factor (≥ 0.1).
        """
        override = attributes.get(V_SIZE_SCALE)
        if override is not None:
            try:
                return max(0.1, float(override))
            except (TypeError, ValueError):
                pass
        return BASE_SCALE

    @staticmethod
    def resolve_border_width(
        attributes: Dict[str, Any],
    ) -> int:
        """Resolves the border width in pixels.

        Args:
            attributes: The object's attributes dict.

        Returns:
            Integer pixel width (≥ 0).
        """
        override = attributes.get(V_BORDER_WIDTH)
        if override is not None:
            try:
                return max(0, int(override))
            except (TypeError, ValueError):
                pass
        return BASE_BORDER_WIDTH
