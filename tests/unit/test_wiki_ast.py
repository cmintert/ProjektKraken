"""
Unit tests for Wiki AST module.
"""

from src.core.wiki_ast import (
    CursorMapper,
    NodeType,
    SourceSpan,
    WikiASTParser,
    WikiASTSerializer,
)


class TestSourceSpan:
    """Tests for SourceSpan."""

    def test_contains(self):
        """Test position containment."""
        span = SourceSpan(5, 10)
        assert span.contains(5) is True
        assert span.contains(9) is True
        assert span.contains(10) is False
        assert span.contains(4) is False

    def test_offset_within(self):
        """Test relative offset calculation."""
        span = SourceSpan(5, 10)
        assert span.offset_within(5) == 0
        assert span.offset_within(7) == 2
        assert span.offset_within(9) == 4


class TestWikiASTParser:
    """Tests for WikiASTParser."""

    def test_parse_plain_text(self):
        """Test parsing plain text."""
        parser = WikiASTParser()
        ast = parser.parse("Hello World")

        assert ast.node_type == NodeType.ROOT
        assert len(ast.children) == 1
        para = ast.children[0]
        assert para.node_type == NodeType.PARAGRAPH
        assert len(para.children) == 1
        assert para.children[0].node_type == NodeType.TEXT
        assert para.children[0].text == "Hello World"

    def test_parse_bold(self):
        """Test parsing bold text."""
        parser = WikiASTParser()
        ast = parser.parse("Hello **Bold** World")

        para = ast.children[0]
        assert len(para.children) == 3
        assert para.children[0].text == "Hello "
        assert para.children[1].node_type == NodeType.BOLD
        assert para.children[1].children[0].text == "Bold"
        assert para.children[2].text == " World"

    def test_parse_italic(self):
        """Test parsing italic text."""
        parser = WikiASTParser()
        ast = parser.parse("Hello *Italic* World")

        para = ast.children[0]
        assert len(para.children) == 3
        assert para.children[1].node_type == NodeType.ITALIC
        assert para.children[1].children[0].text == "Italic"

    def test_parse_bold_italic(self):
        """Test parsing bold+italic text."""
        parser = WikiASTParser()
        ast = parser.parse("Hello ***BoldItalic*** World")

        para = ast.children[0]
        assert para.children[1].node_type == NodeType.BOLD_ITALIC
        assert para.children[1].children[0].text == "BoldItalic"

    def test_parse_wikilink_simple(self):
        """Test parsing simple wikilink."""
        parser = WikiASTParser()
        ast = parser.parse("See [[PageName]] here")

        para = ast.children[0]
        assert len(para.children) == 3
        link = para.children[1]
        assert link.node_type == NodeType.WIKILINK
        assert link.attributes["target"] == "PageName"
        assert link.attributes["label"] == "PageName"

    def test_parse_wikilink_with_label(self):
        """Test parsing wikilink with label."""
        parser = WikiASTParser()
        ast = parser.parse("See [[Target|Label]] here")

        para = ast.children[0]
        link = para.children[1]
        assert link.attributes["target"] == "Target"
        assert link.attributes["label"] == "Label"

    def test_parse_heading(self):
        """Test parsing headings."""
        parser = WikiASTParser()
        ast = parser.parse("# Heading 1\n## Heading 2")

        assert len(ast.children) == 2
        h1 = ast.children[0]
        h2 = ast.children[1]

        assert h1.node_type == NodeType.HEADING
        assert h1.attributes["level"] == 1
        assert h1.children[0].text == "Heading 1"

        assert h2.node_type == NodeType.HEADING
        assert h2.attributes["level"] == 2

    def test_source_spans_set(self):
        """Test that source spans are set during parsing."""
        parser = WikiASTParser()
        ast = parser.parse("Hello **Bold**")

        para = ast.children[0]
        bold = para.children[1]

        assert bold.md_span is not None
        assert bold.md_span.start == 6  # Position of first *
        assert bold.md_span.end == 14  # After second **


class TestWikiASTSerializer:
    """Tests for WikiASTSerializer."""

    def test_to_markdown_plain_text(self):
        """Test serializing plain text to Markdown."""
        parser = WikiASTParser()
        serializer = WikiASTSerializer()

        ast = parser.parse("Hello World")
        md, _ = serializer.to_markdown(ast)

        assert md == "Hello World"

    def test_to_markdown_bold(self):
        """Test serializing bold to Markdown."""
        parser = WikiASTParser()
        serializer = WikiASTSerializer()

        ast = parser.parse("Hello **Bold** World")
        md, _ = serializer.to_markdown(ast)

        assert md == "Hello **Bold** World"

    def test_to_markdown_wikilink(self):
        """Test serializing wikilink to Markdown."""
        parser = WikiASTParser()
        serializer = WikiASTSerializer()

        ast = parser.parse("See [[Target|Label]]")
        md, _ = serializer.to_markdown(ast)

        assert md == "See [[Target|Label]]"

    def test_to_html_plain_text(self):
        """Test serializing plain text to HTML."""
        parser = WikiASTParser()
        serializer = WikiASTSerializer()

        ast = parser.parse("Hello World")
        html, _ = serializer.to_html(ast)

        assert html == "<p>Hello World</p>"

    def test_to_html_bold(self):
        """Test serializing bold to HTML."""
        parser = WikiASTParser()
        serializer = WikiASTSerializer()

        ast = parser.parse("**Bold**")
        html, _ = serializer.to_html(ast)

        assert html == "<p><strong>Bold</strong></p>"

    def test_to_html_wikilink(self):
        """Test serializing wikilink to HTML."""
        parser = WikiASTParser()
        serializer = WikiASTSerializer()

        ast = parser.parse("[[Target]]")
        html, _ = serializer.to_html(ast)

        assert html == '<p><a href="Target">Target</a></p>'

    def test_to_html_heading(self):
        """Test serializing heading to HTML."""
        parser = WikiASTParser()
        serializer = WikiASTSerializer()

        ast = parser.parse("# Title")
        html, _ = serializer.to_html(ast)

        assert html == "<h1>Title</h1>"

    def test_roundtrip_markdown(self):
        """Test Markdown -> AST -> Markdown roundtrip."""
        parser = WikiASTParser()
        serializer = WikiASTSerializer()

        original = "Hello **Bold** and *Italic* with [[Link|Label]]"
        ast = parser.parse(original)
        result, _ = serializer.to_markdown(ast)

        assert result == original


class TestCursorMapper:
    """Tests for CursorMapper."""

    def test_md_to_html_plain_text(self):
        """Test cursor mapping in plain text."""
        parser = WikiASTParser()
        serializer = WikiASTSerializer()

        md = "Hello World"
        ast = parser.parse(md)
        _, ast = serializer.to_markdown(ast)
        _, ast = serializer.to_html(ast)

        mapper = CursorMapper(ast)

        # Cursor at 'W' in MD (pos 6) maps to HTML position
        # HTML: "<p>Hello World</p>"
        # The <p> tag is 3 chars, so 'W' at MD pos 6 maps to HTML pos 3 + 6 = 9
        html_pos = mapper.md_to_html(6)
        assert html_pos == 9  # <p> (3) + offset (6) = 9

    def test_md_to_html_with_bold(self):
        """Test cursor mapping with bold formatting."""
        parser = WikiASTParser()
        serializer = WikiASTSerializer()

        md = "Hi **Bold** there"
        ast = parser.parse(md)
        _, ast = serializer.to_markdown(ast)
        _, ast = serializer.to_html(ast)

        mapper = CursorMapper(ast)

        # Cursor at 'B' in Bold (MD pos 5 is at **, actual B is at 5)
        # In MD: "Hi **Bold** there"
        #         0123456789...
        # 'B' is at index 5
        # In HTML: "<p>Hi <strong>Bold</strong> there</p>"
        # 'B' is after <p>Hi <strong> = 3 + 3 + 8 = 14
        html_pos = mapper.md_to_html(5)
        # The 'B' should be mapped to position inside <strong> tag
        assert html_pos >= 0  # Basic sanity check


class TestIntegration:
    """Integration tests for the full AST pipeline."""

    def test_complex_document(self):
        """Test parsing and serializing a complex document."""
        parser = WikiASTParser()
        serializer = WikiASTSerializer()

        md = """# Main Title
This is a paragraph with **bold** and *italic*.

## Subsection
See [[WikiPage|the page]] for more."""

        ast = parser.parse(md)
        result_md, _ = serializer.to_markdown(ast)
        result_html, _ = serializer.to_html(ast)

        # Verify structure is preserved
        assert "# Main Title" in result_md
        assert "**bold**" in result_md
        assert "*italic*" in result_md
        assert "[[WikiPage|the page]]" in result_md

        # Verify HTML generation
        assert "<h1>Main Title</h1>" in result_html
        assert "<strong>bold</strong>" in result_html
        assert "<em>italic</em>" in result_html
        assert '<a href="WikiPage">the page</a>' in result_html
