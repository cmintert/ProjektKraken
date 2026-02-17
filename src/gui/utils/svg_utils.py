"""SVG Styling Utilities.

Provides shared functions for injecting inline styles into SVG content.
Uses inline ``style`` attributes on SVG elements for compatibility with
both web browsers (Vis.js graph) and Qt's ``QSvgRenderer`` (map markers),
which only supports SVG Tiny 1.2.
"""

import base64
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# SVG shape elements that can receive inline styles
_SVG_SHAPE_ELEMENTS = (
    "path",
    "circle",
    "rect",
    "ellipse",
    "line",
    "polyline",
    "polygon",
    "text",
    "use",
)

_SHAPE_TAG_PATTERN = re.compile(
    rf"(<(?:{'|'.join(_SVG_SHAPE_ELEMENTS)})\b)([^>]*?)(/?>)",
    re.IGNORECASE,
)


def apply_svg_inline_styles(
    svg_content: str,
    fill_color: Optional[str] = None,
    stroke_color: Optional[str] = None,
    stroke_width: Optional[int] = None,
    scale: Optional[float] = None,
) -> str:
    """Injects inline styles into SVG shape elements.

    Adds or updates the ``style`` attribute on all SVG shape elements
    (path, circle, rect, etc.) with the specified fill, stroke, and
    stroke-width values. Also adds a ``transform="scale()"`` attribute
    to the root ``<svg>`` element if a scale factor is provided.

    Uses inline styles because Qt's ``QSvgRenderer`` has limited support
    for ``<style>`` tags (SVG Tiny 1.2 spec).

    Args:
        svg_content: Raw SVG XML string.
        fill_color: Hex color for fill (e.g., ``"#00FF00"``).
        stroke_color: Hex color for stroke (e.g., ``"#FF0000"``).
        stroke_width: Stroke width in pixels.
        scale: Scale factor (e.g., 1.5 for 150%).

    Returns:
        Modified SVG string with injected inline styles.

    """
    # Build inline style string
    style_parts = []
    if fill_color:
        style_parts.append(f"fill:{fill_color}")
    if stroke_color:
        style_parts.append(f"stroke:{stroke_color}")
    if stroke_width is not None:
        style_parts.append(f"stroke-width:{stroke_width}px")

    # Inject inline styles on shape elements
    if style_parts:
        new_style = ";".join(style_parts)

        def _inject_style(match: re.Match) -> str:
            tag_open = match.group(1)
            attrs = match.group(2)
            tag_close = match.group(3)

            # Remove existing fill/stroke presentation attributes
            # so inline styles take effect
            if fill_color:
                attrs = re.sub(r'\s+fill="[^"]*"', "", attrs)
            if stroke_color:
                attrs = re.sub(r'\s+stroke="[^"]*"', "", attrs)
            if stroke_width is not None:
                attrs = re.sub(r'\s+stroke-width="[^"]*"', "", attrs)

            # Add or merge inline style attribute
            if 'style="' in attrs:
                attrs = re.sub(
                    r'style="([^"]*)"',
                    rf'style="\1;{new_style}"',
                    attrs,
                )
            else:
                attrs += f' style="{new_style}"'

            return f"{tag_open}{attrs}{tag_close}"

        svg_content = _SHAPE_TAG_PATTERN.sub(_inject_style, svg_content)

        # Also remove fill attribute from root <svg> element
        if fill_color:
            svg_content = re.sub(
                r"(<svg\b[^>]*?)\s+fill=\"[^\"]*\"",
                r"\1",
                svg_content,
                count=1,
            )

    # Apply scale transform to root <svg> element
    if scale is not None and scale != 1.0:

        def _add_scale(match: re.Match) -> str:
            svg_tag = match.group(1)
            if "transform=" in svg_tag:
                svg_tag = re.sub(
                    r'transform="([^"]*)"',
                    rf'transform="\1 scale({scale})"',
                    svg_tag,
                )
            else:
                svg_tag = svg_tag.rstrip(">") + f' transform="scale({scale})">'
            return svg_tag

        svg_content = re.sub(r"(<svg[^>]*>)", _add_scale, svg_content, count=1)

    return svg_content


def apply_svg_styling_to_data_uri(
    data_uri: str,
    fill_color: Optional[str] = None,
    stroke_color: Optional[str] = None,
    stroke_width: Optional[int] = None,
    scale: Optional[float] = None,
) -> str:
    """Applies inline SVG styling to a Base64 data URI.

    Decodes an SVG data URI, applies inline styles, and re-encodes.
    Non-SVG data URIs (PNG, JPG) pass through unchanged.

    Args:
        data_uri: Base64 data URI string.
        fill_color: Hex color for fill.
        stroke_color: Hex color for stroke.
        stroke_width: Stroke width in pixels.
        scale: Scale factor.

    Returns:
        Modified data URI, or original if not SVG.

    """
    if not data_uri.startswith("data:image/svg+xml;base64,"):
        return data_uri

    try:
        encoded_part = data_uri.split(",", 1)[1]
        svg_bytes = base64.b64decode(encoded_part)
        svg_str = svg_bytes.decode("utf-8")
    except (IndexError, ValueError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to decode SVG data URI: {e}")
        return data_uri

    styled = apply_svg_inline_styles(
        svg_str,
        fill_color=fill_color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        scale=scale,
    )

    try:
        new_encoded = base64.b64encode(styled.encode("utf-8")).decode("utf-8")
        return f"data:image/svg+xml;base64,{new_encoded}"
    except (ValueError, UnicodeEncodeError) as e:
        logger.warning(f"Failed to re-encode styled SVG: {e}")
        return data_uri


def svg_file_to_string(file_path: Path) -> str:
    """Reads an SVG file and returns its contents as a string.

    Args:
        file_path: Path to the SVG file.

    Returns:
        SVG content string, or empty string on error.

    """
    try:
        return file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to read SVG file {file_path}: {e}")
        return ""
