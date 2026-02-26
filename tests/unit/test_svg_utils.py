"""Tests for SVG Styling Utilities.

Validates the svg_utils module functions for inline style injection,
Base64 data URI styling, and SVG file reading.
"""

import base64

from src.gui.utils.svg_utils import (
    apply_svg_inline_styles,
    apply_svg_styling_to_data_uri,
    svg_file_to_string,
)

SIMPLE_SVG = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
PHOSPHOR_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"'
    ' fill="#000000" viewBox="0 0 256 256">'
    '<path d="M160,40a32,32,0,1,0-32,32A32,32,0,0,0,160,40Z"></path>'
    "</svg>"
)
MULTI_PATH_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg">'
    '<path d="M1"/>'
    '<circle r="5"/>'
    '<rect width="10"/>'
    "</svg>"
)


class TestApplySvgInlineStyles:
    """Tests for apply_svg_inline_styles function."""

    def test_injects_fill_color(self):
        """Fill color is injected as inline style on shape elements."""
        result = apply_svg_inline_styles(SIMPLE_SVG, fill_color="#00FF00")
        assert 'style="fill:#00FF00"' in result

    def test_injects_stroke_color(self):
        """Stroke color is injected as inline style."""
        result = apply_svg_inline_styles(SIMPLE_SVG, stroke_color="#FF0000")
        assert "stroke:#FF0000" in result

    def test_injects_stroke_width(self):
        """Stroke width is injected as inline style."""
        result = apply_svg_inline_styles(SIMPLE_SVG, stroke_width=5)
        assert "stroke-width:5px" in result

    def test_injects_scale_transform(self):
        """Scale transform is added to root svg element."""
        result = apply_svg_inline_styles(SIMPLE_SVG, scale=2.0)
        assert 'transform="scale(2.0)"' in result

    def test_does_not_add_scale_for_1_0(self):
        """Scale of 1.0 is a no-op (no transform added)."""
        result = apply_svg_inline_styles(SIMPLE_SVG, scale=1.0)
        assert "transform" not in result

    def test_removes_fill_presentation_attribute(self):
        """Existing fill presentation attribute is removed when fill_color is set."""
        result = apply_svg_inline_styles(PHOSPHOR_SVG, fill_color="#FF0000")
        # Root svg fill="#000000" should be removed
        assert 'fill="#000000"' not in result
        # Inline style should be present on path
        assert "fill:#FF0000" in result

    def test_multiple_shape_elements(self):
        """All shape elements receive inline styles."""
        result = apply_svg_inline_styles(
            MULTI_PATH_SVG, fill_color="#00FF00", stroke_color="#FF0000"
        )
        # Each element should have the style
        assert result.count("fill:#00FF00") == 3
        assert result.count("stroke:#FF0000") == 3

    def test_no_changes_when_no_args(self):
        """SVG passes through unchanged when no styling args given."""
        result = apply_svg_inline_styles(SIMPLE_SVG)
        assert result == SIMPLE_SVG

    def test_combined_styles(self):
        """Fill, stroke, and stroke-width are combined in one style attribute."""
        result = apply_svg_inline_styles(
            SIMPLE_SVG,
            fill_color="#00FF00",
            stroke_color="#FF0000",
            stroke_width=3,
        )
        assert "fill:#00FF00" in result
        assert "stroke:#FF0000" in result
        assert "stroke-width:3px" in result

    def test_fill_none_injects_transparent(self):
        """fill_color='none' injects fill:none for transparent."""
        result = apply_svg_inline_styles(SIMPLE_SVG, fill_color="none")
        assert "fill:none" in result

    def test_stroke_none_injects_transparent(self):
        """stroke_color='none' injects stroke:none for no border."""
        result = apply_svg_inline_styles(SIMPLE_SVG, stroke_color="none")
        assert "stroke:none" in result


class TestApplySvgStylingToDataUri:
    """Tests for apply_svg_styling_to_data_uri function."""

    def _make_data_uri(self, svg_content: str) -> str:
        encoded = base64.b64encode(svg_content.encode()).decode()
        return f"data:image/svg+xml;base64,{encoded}"

    def _decode_data_uri(self, data_uri: str) -> str:
        return base64.b64decode(data_uri.split(",")[1]).decode()

    def test_injects_fill_into_svg_data_uri(self):
        """Fill color is injected into SVG data URI."""
        data_uri = self._make_data_uri(SIMPLE_SVG)
        result = apply_svg_styling_to_data_uri(data_uri, fill_color="#00FF00")
        decoded = self._decode_data_uri(result)
        assert "fill:#00FF00" in decoded

    def test_png_data_uri_unchanged(self):
        """PNG data URIs pass through unchanged."""
        png_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"
        result = apply_svg_styling_to_data_uri(
            png_uri, fill_color="#FF0000", stroke_color="#00FF00"
        )
        assert result == png_uri

    def test_injects_stroke_into_svg_data_uri(self):
        """Stroke color and width are injected into SVG data URI."""
        data_uri = self._make_data_uri(SIMPLE_SVG)
        result = apply_svg_styling_to_data_uri(
            data_uri, stroke_color="#FF0000", stroke_width=3
        )
        decoded = self._decode_data_uri(result)
        assert "stroke:#FF0000" in decoded
        assert "stroke-width:3px" in decoded

    def test_injects_scale_into_svg_data_uri(self):
        """Scale transform is injected into SVG data URI."""
        data_uri = self._make_data_uri(SIMPLE_SVG)
        result = apply_svg_styling_to_data_uri(data_uri, scale=1.5)
        decoded = self._decode_data_uri(result)
        assert 'transform="scale(1.5)"' in decoded


class TestSvgFileToString:
    """Tests for svg_file_to_string function."""

    def test_reads_svg_file(self, tmp_path):
        """SVG file content is read correctly."""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text(SIMPLE_SVG, encoding="utf-8")
        result = svg_file_to_string(svg_file)
        assert result == SIMPLE_SVG

    def test_nonexistent_file_returns_empty(self, tmp_path):
        """Nonexistent file returns empty string."""
        result = svg_file_to_string(tmp_path / "nonexistent.svg")
        assert result == ""
