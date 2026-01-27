import os

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QIcon, QPixmap

from src.core.paths import get_resource_path


def load_icon(relative_path: str, color: str = None) -> QIcon:
    """Loads an SVG icon and optionally recolors it (replacing 'currentColor').

    Args:
        relative_path: Path relative to project root (e.g. 'default_assets/icons/...')
        color: Hex color string to replace 'currentColor' with.

    Returns:
        QIcon: The loaded (and potentially recolored) icon.
    """
    full_path = get_resource_path(relative_path)
    if not os.path.exists(full_path):
        return QIcon()

    if color:
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                svg_content = f.read()

            # Replace currentColor with the hex color
            svg_content = svg_content.replace("currentColor", color)

            # Create icon from data
            pixmap = QPixmap()
            # loadFromData returns boolean, we load into the pixmap
            pixmap.loadFromData(QByteArray(svg_content.encode("utf-8")))
            return QIcon(pixmap)
        except Exception:
            return QIcon(full_path)
    else:
        return QIcon(full_path)
