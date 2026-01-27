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
            pixmap = QPixmap()
            success = pixmap.loadFromData(QByteArray(svg_content.encode("utf-8")))
            if success:
                return QIcon(pixmap)

            import logging

            logging.getLogger(__name__).warning(
                f"Failed to load SVG from data for {relative_path}. "
                f"Supported formats: {QPixmap().activeFormats()}"
            )
        except Exception as e:
            import logging

            logging.getLogger(__name__).error(
                f"Error loading SVG data for {relative_path}: {e}"
            )

    # Fallback to loading directly from file
    return QIcon(full_path)
