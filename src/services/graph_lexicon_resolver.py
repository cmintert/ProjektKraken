"""Resolve graph-lexicon image references without GUI dependencies."""

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any, Callable

from src.services.marker_icon_catalog import MarkerIconCatalog

logger = logging.getLogger(__name__)


def image_to_base64(file_path: Path) -> str:
    """Convert an image file to an embeddable Base64 data URI.

    Args:
        file_path: Absolute image path.

    Returns:
        Data URI, or an empty string when the image cannot be read.

    """
    if not file_path.exists():
        logger.warning("Image file not found for Base64 encoding: %s", file_path)
        return ""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    try:
        encoded = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    except OSError:
        logger.exception("Failed to read image for Base64 encoding")
        return ""
    return f"data:{mime_type or 'application/octet-stream'};base64,{encoded}"


def resolve_lexicon_images(
    lexicon: dict[str, Any],
    world_root: Path,
    image_encoder: Callable[[Path], str] = image_to_base64,
) -> dict[str, Any]:
    """Resolve node icon IDs to Base64 data URIs.

    Args:
        lexicon: Raw graph visual lexicon.
        world_root: Root directory of the active portable world.

    Returns:
        Copy of the lexicon with resolved ``image`` fields.

    """
    resolved_nodes: dict[str, Any] = {}
    catalog = MarkerIconCatalog.load(world_root)
    for type_name, style in lexicon.get("nodes", {}).items():
        resolved_style = dict(style)
        resolved_style.pop("icon", None)
        icon_id = style.get("icon_id")
        if icon_id:
            definition = catalog.resolve_id(icon_id)
            if definition is None:
                logger.warning("Unknown Visual Lexicon icon ID: %s", icon_id)
            elif (full_path := catalog.asset_file(definition)) is not None:
                if data_uri := image_encoder(full_path):
                    resolved_style["image"] = data_uri
        resolved_nodes[type_name] = resolved_style
    return {
        "nodes": resolved_nodes,
        "edges": lexicon.get("edges", {}),
    }
