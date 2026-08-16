"""Typography configuration for Kraken's wiki writing surface."""

from dataclasses import dataclass
from typing import Any, Mapping

from src.gui.constants import WIKI_EDITOR_MAX_LINE_LENGTH

_POINTS_TO_PIXELS = 96 / 72
_HEX_COLOR_LENGTH = 6
_HEADING_LEVEL_TWO = 2
_HEADING_LEVEL_THREE = 3


def _number(value: Any, fallback: float) -> float:
    """Return a numeric theme token, accepting values such as ``"11.25pt"``."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        for suffix in ("pt", "px", "em"):
            normalized = normalized.removesuffix(suffix).strip()
        try:
            return float(normalized)
        except ValueError:
            return fallback
    return fallback


def _blend_hex(foreground: str, background: str, amount: float) -> str:
    """Blend two hex colors without introducing a Qt dependency."""

    def _channels(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        if len(value) != _HEX_COLOR_LENGTH:
            return (0, 0, 0)
        try:
            return (
                int(value[0:2], 16),
                int(value[2:4], 16),
                int(value[4:6], 16),
            )
        except ValueError:
            return (0, 0, 0)

    foreground_channels = _channels(foreground)
    background_channels = _channels(background)
    channels = (
        round(foreground_channel * amount + background_channel * (1 - amount))
        for foreground_channel, background_channel in zip(
            foreground_channels, background_channels, strict=True
        )
    )
    return "#" + "".join(f"{channel:02x}" for channel in channels)


@dataclass(frozen=True)
class EditorTypography:
    """Resolved editor-specific typography and color tokens."""

    font_family: str
    body_size: float
    line_height: float
    paragraph_spacing: float
    h1_size: float
    h2_size: float
    h3_size: float
    h1_margin_top: float
    h1_margin_bottom: float
    h2_margin_top: float
    h2_margin_bottom: float
    h3_margin_top: float
    h3_margin_bottom: float
    document_margin: float
    line_length: int
    text_color: str
    link_color: str
    link_hover_color: str
    broken_link_color: str
    show_section_gutter: bool

    @classmethod
    def from_theme(cls, theme: Mapping[str, Any]) -> "EditorTypography":
        """Resolve editor tokens without inheriting general application text sizes."""
        text_color = str(theme.get("text_main", "#E0E0E0"))
        accent_color = str(theme.get("accent_secondary", "#2980b9"))
        error_color = str(theme.get("error", "#CF6679"))
        return cls(
            font_family=str(
                theme.get(
                    "editor_font_family",
                    "Segoe UI, Roboto, Helvetica Neue, Helvetica, Arial, sans-serif",
                )
            ),
            body_size=_number(theme.get("editor_body_size"), 11.25),
            line_height=_number(theme.get("editor_line_height"), 1.38),
            paragraph_spacing=_number(
                theme.get("editor_paragraph_spacing"), 0.6
            ),
            h1_size=_number(theme.get("editor_h1_size"), 20.0),
            h2_size=_number(theme.get("editor_h2_size"), 16.0),
            h3_size=_number(theme.get("editor_h3_size"), 13.0),
            h1_margin_top=_number(theme.get("editor_h1_margin_top"), 1.4),
            h1_margin_bottom=_number(
                theme.get("editor_h1_margin_bottom"), 0.45
            ),
            h2_margin_top=_number(theme.get("editor_h2_margin_top"), 1.2),
            h2_margin_bottom=_number(
                theme.get("editor_h2_margin_bottom"), 0.4
            ),
            h3_margin_top=_number(theme.get("editor_h3_margin_top"), 1.0),
            h3_margin_bottom=_number(
                theme.get("editor_h3_margin_bottom"), 0.3
            ),
            document_margin=_number(theme.get("editor_document_margin"), 34.0),
            line_length=round(
                _number(
                    theme.get("editor_line_length"), WIKI_EDITOR_MAX_LINE_LENGTH
                )
            ),
            text_color=text_color,
            link_color=str(
                theme.get(
                    "editor_link_color", _blend_hex(accent_color, text_color, 0.6)
                )
            ),
            link_hover_color=str(
                theme.get("editor_link_hover_color", accent_color)
            ),
            broken_link_color=str(
                theme.get(
                    "editor_broken_link_color",
                    _blend_hex(error_color, text_color, 0.68),
                )
            ),
            show_section_gutter=bool(theme.get("editor_show_section_gutter", False)),
        )

    @property
    def primary_font_family(self) -> str:
        """Return the first family in the CSS-style fallback stack."""
        return self.font_family.split(",", maxsplit=1)[0].strip().strip('"\'')

    @property
    def line_height_percent(self) -> int:
        """Return Qt's proportional line-height value."""
        return round(self.line_height * 100)

    def point_size(self, heading_level: int) -> float:
        """Return the configured point size for a semantic heading level."""
        return {
            1: self.h1_size,
            2: self.h2_size,
            3: self.h3_size,
        }.get(heading_level, self.body_size)

    def block_margins(self, heading_level: int) -> tuple[float, float]:
        """Return top and bottom block margins in device-independent pixels."""
        if heading_level == 1:
            em_size = self.h1_size * _POINTS_TO_PIXELS
            return (
                round(self.h1_margin_top * em_size, 2),
                round(self.h1_margin_bottom * em_size, 2),
            )
        if heading_level == _HEADING_LEVEL_TWO:
            em_size = self.h2_size * _POINTS_TO_PIXELS
            return (
                round(self.h2_margin_top * em_size, 2),
                round(self.h2_margin_bottom * em_size, 2),
            )
        if heading_level == _HEADING_LEVEL_THREE:
            em_size = self.h3_size * _POINTS_TO_PIXELS
            return (
                round(self.h3_margin_top * em_size, 2),
                round(self.h3_margin_bottom * em_size, 2),
            )
        return (
            0.0,
            round(self.paragraph_spacing * self.body_size * _POINTS_TO_PIXELS, 2),
        )
