"""Icon Loader Module.

Provides utilities for loading and recoloring SVG icons.
"""

import os
from collections import OrderedDict

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from src.core.paths import get_resource_path

# GUI-thread owned: QPixmap-backed icons must never be created in a worker.
_ICON_CACHE_LIMIT = 256
_icon_cache: OrderedDict[tuple[str, str | None], QIcon] = OrderedDict()


def load_icon(relative_path: str, color: str | None = None) -> QIcon:
    """Loads an SVG icon and optionally recolors it (replacing 'currentColor').

    Args:
        relative_path: Path relative to project root (e.g. 'default_assets/icons/...')
        color: Hex color string to replace 'currentColor' with.

    Returns:
        QIcon: The loaded (and potentially recolored) icon.
    """
    full_path = get_resource_path(relative_path)
    key = (os.path.normcase(os.path.abspath(full_path)), color)
    if key in _icon_cache:
        _icon_cache.move_to_end(key)
        return QIcon(_icon_cache[key])
    if not os.path.exists(full_path):
        import logging

        logging.getLogger(__name__).warning(
            f"Icon path not found: {relative_path} (Resolved: {full_path})"
        )
        return QIcon()

    # For SVGs, always try to load from data in memory.
    # This is more reliable in bundled builds (onedir/onefile)
    # as it bypasses Qt's internal file engine for icons.
    if full_path.lower().endswith(".svg"):
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                svg_content = f.read()

            if color:
                # Replace currentColor with the hex color
                svg_content = svg_content.replace("currentColor", color)

            # Create icon from data
            renderer = QSvgRenderer(QByteArray(svg_content.encode("utf-8")))
            if renderer.isValid():
                pixmap = QPixmap(renderer.defaultSize())
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                icon = QIcon(pixmap)
                _icon_cache[key] = icon
                if len(_icon_cache) > _ICON_CACHE_LIMIT:
                    _icon_cache.popitem(last=False)
                return QIcon(icon)

            import logging

            logging.getLogger(__name__).warning(
                f"Failed to render SVG data for {relative_path}."
            )
        except Exception as e:
            import logging

            logging.getLogger(__name__).error(
                f"Error loading SVG data for {relative_path}: {e}"
            )

    # Fallback to loading directly from file
    return QIcon(full_path)
