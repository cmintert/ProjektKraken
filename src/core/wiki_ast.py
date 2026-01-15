"""
Wiki Abstract Syntax Tree (AST) Module.

Provides an intermediate representation for Markdown content,
enabling precise bidirectional conversion between Markdown and HTML
with source position tracking for cursor synchronization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Optional, Tuple


class NodeType(Enum):
    """Types of nodes in the Wiki AST."""

    ROOT = auto()
    PARAGRAPH = auto()
    HEADING = auto()
    TEXT = auto()
    BOLD = auto()
    ITALIC = auto()
    BOLD_ITALIC = auto()
    WIKILINK = auto()
    LINEBREAK = auto()


@dataclass
class SourceSpan:
    """
    Tracks character positions in source text.

    Attributes:
        start: Starting character index (inclusive).
        end: Ending character index (exclusive).
    """

    start: int
    end: int

    def contains(self, pos: int) -> bool:
        """Check if position is within this span."""
        return self.start <= pos < self.end

    def offset_within(self, pos: int) -> int:
        """Get relative offset of position within this span."""
        return pos - self.start


@dataclass
class WikiNode:
    """
    A node in the Wiki AST.

    Attributes:
        node_type: The type of this node.
        children: Child nodes (for container nodes).
        text: Text content (for leaf nodes).
        attributes: Additional attributes (e.g., heading level, link target).
        md_span: Position in Markdown source.
        html_span: Position in generated HTML.
    """

    node_type: NodeType
    children: List[WikiNode] = field(default_factory=list)
    text: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    md_span: Optional[SourceSpan] = None
    html_span: Optional[SourceSpan] = None

    def add_child(self, child: WikiNode) -> None:
        """Add a child node."""
        self.children.append(child)

    def get_text_content(self) -> str:
        """Get all text content recursively."""
        if self.text:
            return self.text
        return "".join(child.get_text_content() for child in self.children)


class WikiASTParser:
    """
    Parses Markdown text into a Wiki AST with source position tracking.
    """

    # Patterns for parsing
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    BOLD_ITALIC_PATTERN = re.compile(r"\*\*\*(.+?)\*\*\*")
    BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
    ITALIC_PATTERN = re.compile(r"\*(.+?)\*")
    WIKILINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")

    def parse(self, markdown: str) -> WikiNode:
        """
        Parse Markdown text into an AST.

        Args:
            markdown: The Markdown source text.

        Returns:
            WikiNode: The root node of the AST.
        """
        root = WikiNode(
            node_type=NodeType.ROOT,
            md_span=SourceSpan(0, len(markdown)),
        )

        # Split into lines/paragraphs
        lines = markdown.split("\n")
        pos = 0

        for line in lines:
            line_start = pos
            line_end = pos + len(line)

            if not line.strip():
                # Empty line - just a linebreak
                if line:
                    node = WikiNode(
                        node_type=NodeType.LINEBREAK,
                        md_span=SourceSpan(line_start, line_end),
                    )
                    root.add_child(node)
            elif line.strip().startswith("#"):
                # Heading
                heading_node = self._parse_heading(line, line_start)
                if heading_node:
                    root.add_child(heading_node)
            else:
                # Paragraph
                para_node = self._parse_paragraph(line, line_start)
                root.add_child(para_node)

            pos = line_end + 1  # +1 for newline

        return root

    def _parse_heading(self, line: str, offset: int) -> Optional[WikiNode]:
        """Parse a heading line."""
        match = self.HEADING_PATTERN.match(line)
        if not match:
            return None

        level = len(match.group(1))
        content = match.group(2)
        content_start = offset + match.start(2)

        heading = WikiNode(
            node_type=NodeType.HEADING,
            attributes={"level": level},
            md_span=SourceSpan(offset, offset + len(line)),
        )

        # Parse inline content
        inline_children = self._parse_inline(content, content_start)
        heading.children = inline_children

        return heading

    def _parse_paragraph(self, line: str, offset: int) -> WikiNode:
        """Parse a paragraph line."""
        para = WikiNode(
            node_type=NodeType.PARAGRAPH,
            md_span=SourceSpan(offset, offset + len(line)),
        )

        # Parse inline content
        para.children = self._parse_inline(line, offset)

        return para

    def _parse_inline(self, text: str, offset: int) -> List[WikiNode]:
        """
        Parse inline formatting (bold, italic, links).

        Uses a token-based approach to handle nested formatting.
        """
        nodes: List[WikiNode] = []
        pos = 0

        while pos < len(text):
            # Try to match patterns at current position
            remaining = text[pos:]

            # WikiLink
            wikilink_match = self.WIKILINK_PATTERN.match(remaining)
            if wikilink_match:
                target = wikilink_match.group(1).strip()
                label = (
                    wikilink_match.group(2).strip()
                    if wikilink_match.group(2)
                    else target
                )
                node = WikiNode(
                    node_type=NodeType.WIKILINK,
                    text=label,
                    attributes={"target": target, "label": label},
                    md_span=SourceSpan(
                        offset + pos, offset + pos + wikilink_match.end()
                    ),
                )
                nodes.append(node)
                pos += wikilink_match.end()
                continue

            # Bold+Italic (must check before bold/italic)
            bold_italic_match = self.BOLD_ITALIC_PATTERN.match(remaining)
            if bold_italic_match:
                content = bold_italic_match.group(1)
                content_start = offset + pos + 3  # After ***
                node = WikiNode(
                    node_type=NodeType.BOLD_ITALIC,
                    md_span=SourceSpan(
                        offset + pos, offset + pos + bold_italic_match.end()
                    ),
                )
                # Recursively parse content
                node.children = self._parse_inline(content, content_start)
                nodes.append(node)
                pos += bold_italic_match.end()
                continue

            # Bold
            bold_match = self.BOLD_PATTERN.match(remaining)
            if bold_match:
                content = bold_match.group(1)
                content_start = offset + pos + 2  # After **
                node = WikiNode(
                    node_type=NodeType.BOLD,
                    md_span=SourceSpan(offset + pos, offset + pos + bold_match.end()),
                )
                # Recursively parse content
                node.children = self._parse_inline(content, content_start)
                nodes.append(node)
                pos += bold_match.end()
                continue

            # Italic
            italic_match = self.ITALIC_PATTERN.match(remaining)
            if italic_match:
                content = italic_match.group(1)
                content_start = offset + pos + 1  # After *
                node = WikiNode(
                    node_type=NodeType.ITALIC,
                    md_span=SourceSpan(offset + pos, offset + pos + italic_match.end()),
                )
                # Recursively parse content
                node.children = self._parse_inline(content, content_start)
                nodes.append(node)
                pos += italic_match.end()
                continue

            # Plain text - consume until next special char or end
            text_start = pos
            while pos < len(text):
                # Check if we're at the start of a pattern
                if text[pos] in ("*", "["):
                    # Check if it's actually a pattern
                    remaining_check = text[pos:]
                    if (
                        self.WIKILINK_PATTERN.match(remaining_check)
                        or self.BOLD_ITALIC_PATTERN.match(remaining_check)
                        or self.BOLD_PATTERN.match(remaining_check)
                        or self.ITALIC_PATTERN.match(remaining_check)
                    ):
                        break
                pos += 1

            if pos > text_start:
                plain_text = text[text_start:pos]
                node = WikiNode(
                    node_type=NodeType.TEXT,
                    text=plain_text,
                    md_span=SourceSpan(offset + text_start, offset + pos),
                )
                nodes.append(node)

        return nodes


class WikiASTSerializer:
    """
    Serializes a Wiki AST to Markdown or HTML with position tracking.
    """

    def to_markdown(self, root: WikiNode) -> Tuple[str, WikiNode]:
        """
        Serialize AST to Markdown, updating md_span for all nodes.

        Args:
            root: The root node of the AST.

        Returns:
            Tuple of (markdown_string, updated_root_with_spans).
        """
        result: List[str] = []
        pos = 0

        for child in root.children:
            md, pos = self._node_to_markdown(child, pos)
            result.append(md)
            if child.node_type not in (NodeType.LINEBREAK,):
                result.append("\n")
                pos += 1

        return "".join(result).rstrip("\n"), root

    def _node_to_markdown(self, node: WikiNode, pos: int) -> Tuple[str, int]:
        """Convert a single node to Markdown."""
        start_pos = pos

        if node.node_type == NodeType.HEADING:
            level = node.attributes.get("level", 1)
            prefix = "#" * level + " "
            content, pos = self._children_to_markdown(node.children, pos + len(prefix))
            result = prefix + content
            node.md_span = SourceSpan(start_pos, pos)
            return result, pos

        elif node.node_type == NodeType.PARAGRAPH:
            content, pos = self._children_to_markdown(node.children, pos)
            node.md_span = SourceSpan(start_pos, pos)
            return content, pos

        elif node.node_type == NodeType.TEXT:
            node.md_span = SourceSpan(pos, pos + len(node.text))
            return node.text, pos + len(node.text)

        elif node.node_type == NodeType.BOLD:
            content, inner_pos = self._children_to_markdown(node.children, pos + 2)
            result = f"**{content}**"
            node.md_span = SourceSpan(pos, inner_pos + 2)
            return result, inner_pos + 2

        elif node.node_type == NodeType.ITALIC:
            content, inner_pos = self._children_to_markdown(node.children, pos + 1)
            result = f"*{content}*"
            node.md_span = SourceSpan(pos, inner_pos + 1)
            return result, inner_pos + 1

        elif node.node_type == NodeType.BOLD_ITALIC:
            content, inner_pos = self._children_to_markdown(node.children, pos + 3)
            result = f"***{content}***"
            node.md_span = SourceSpan(pos, inner_pos + 3)
            return result, inner_pos + 3

        elif node.node_type == NodeType.WIKILINK:
            target = node.attributes.get("target", "")
            label = node.attributes.get("label", target)
            if target == label:
                result = f"[[{target}]]"
            else:
                result = f"[[{target}|{label}]]"
            node.md_span = SourceSpan(pos, pos + len(result))
            return result, pos + len(result)

        elif node.node_type == NodeType.LINEBREAK:
            node.md_span = SourceSpan(pos, pos)
            return "", pos

        return "", pos

    def _children_to_markdown(
        self, children: List[WikiNode], pos: int
    ) -> Tuple[str, int]:
        """Convert child nodes to Markdown."""
        result: List[str] = []
        for child in children:
            md, pos = self._node_to_markdown(child, pos)
            result.append(md)
        return "".join(result), pos

    def to_html(self, root: WikiNode) -> Tuple[str, WikiNode]:
        """
        Serialize AST to HTML, updating html_span for all nodes.

        Args:
            root: The root node of the AST.

        Returns:
            Tuple of (html_string, updated_root_with_spans).
        """
        result: List[str] = []
        pos = 0

        for child in root.children:
            html, pos = self._node_to_html(child, pos)
            result.append(html)

        return "".join(result), root

    def _node_to_html(self, node: WikiNode, pos: int) -> Tuple[str, int]:
        """Convert a single node to HTML."""
        start_pos = pos

        if node.node_type == NodeType.HEADING:
            level = node.attributes.get("level", 1)
            open_tag = f"<h{level}>"
            close_tag = f"</h{level}>"
            pos += len(open_tag)
            content, pos = self._children_to_html(node.children, pos)
            pos += len(close_tag)
            result = f"{open_tag}{content}{close_tag}"
            node.html_span = SourceSpan(start_pos, pos)
            return result, pos

        elif node.node_type == NodeType.PARAGRAPH:
            open_tag = "<p>"
            close_tag = "</p>"
            pos += len(open_tag)
            content, pos = self._children_to_html(node.children, pos)
            pos += len(close_tag)
            result = f"{open_tag}{content}{close_tag}"
            node.html_span = SourceSpan(start_pos, pos)
            return result, pos

        elif node.node_type == NodeType.TEXT:
            node.html_span = SourceSpan(pos, pos + len(node.text))
            return node.text, pos + len(node.text)

        elif node.node_type == NodeType.BOLD:
            open_tag = "<strong>"
            close_tag = "</strong>"
            pos += len(open_tag)
            content, pos = self._children_to_html(node.children, pos)
            pos += len(close_tag)
            result = f"{open_tag}{content}{close_tag}"
            node.html_span = SourceSpan(start_pos, pos)
            return result, pos

        elif node.node_type == NodeType.ITALIC:
            open_tag = "<em>"
            close_tag = "</em>"
            pos += len(open_tag)
            content, pos = self._children_to_html(node.children, pos)
            pos += len(close_tag)
            result = f"{open_tag}{content}{close_tag}"
            node.html_span = SourceSpan(start_pos, pos)
            return result, pos

        elif node.node_type == NodeType.BOLD_ITALIC:
            open_tag = "<strong><em>"
            close_tag = "</em></strong>"
            pos += len(open_tag)
            content, pos = self._children_to_html(node.children, pos)
            pos += len(close_tag)
            result = f"{open_tag}{content}{close_tag}"
            node.html_span = SourceSpan(start_pos, pos)
            return result, pos

        elif node.node_type == NodeType.WIKILINK:
            target = node.attributes.get("target", "")
            label = node.attributes.get("label", target)
            html = f'<a href="{target}">{label}</a>'
            node.html_span = SourceSpan(pos, pos + len(html))
            return html, pos + len(html)

        elif node.node_type == NodeType.LINEBREAK:
            br = "<br>"
            node.html_span = SourceSpan(pos, pos + len(br))
            return br, pos + len(br)

        return "", pos

    def _children_to_html(self, children: List[WikiNode], pos: int) -> Tuple[str, int]:
        """Convert child nodes to HTML."""
        result: List[str] = []
        for child in children:
            html, pos = self._node_to_html(child, pos)
            result.append(html)
        return "".join(result), pos

    def to_plaintext(self, root: WikiNode) -> Tuple[str, WikiNode]:
        """
        Serialize AST to Plain Text (mimicking QTextEdit output), updating html_span.
        We reuse html_span to store the Plain Text spans, as CursorMapper uses html_span
        to map against the "View" representation (which is Plain Text in Qt).

        Args:
            root: The root node of the AST.

        Returns:
            Tuple of (plaintext_string, updated_root_with_spans).
        """
        result: List[str] = []
        pos = 0

        for i, child in enumerate(root.children):
            text, pos = self._node_to_plaintext(child, pos)
            result.append(text)

            # Simulate block separator (newline) used by QTextEdit between blocks
            if i < len(root.children) - 1:
                result.append("\n")
                pos += 1

        return "".join(result), root

    def _node_to_plaintext(self, node: WikiNode, pos: int) -> Tuple[str, int]:
        """Convert a single node to Plain Text."""
        start_pos = pos

        # Container nodes - recurse
        if node.node_type in (
            NodeType.PARAGRAPH,
            NodeType.HEADING,
            NodeType.BOLD,
            NodeType.ITALIC,
            NodeType.BOLD_ITALIC,
        ):
            content, pos = self._children_to_plaintext(node.children, pos)
            node.html_span = SourceSpan(start_pos, pos)
            return content, pos

        elif node.node_type == NodeType.TEXT:
            node.html_span = SourceSpan(pos, pos + len(node.text))
            return node.text, pos + len(node.text)

        elif node.node_type == NodeType.WIKILINK:
            # In Rich Text, only label is visible
            target = node.attributes.get("target", "")
            label = node.attributes.get("label", target)
            node.html_span = SourceSpan(pos, pos + len(label))
            return label, pos + len(label)

        elif node.node_type == NodeType.LINEBREAK:
            # Linebreak implies empty line.
            # In MD: \n\n -> Block(Text) + Block(Empty) + Block(Text)
            # Text content of Empty Block is ""
            node.html_span = SourceSpan(pos, pos)
            return "", pos

        return "", pos

    def _children_to_plaintext(
        self, children: List[WikiNode], pos: int
    ) -> Tuple[str, int]:
        """Convert child nodes to Plain Text."""
        result: List[str] = []
        for child in children:
            text, pos = self._node_to_plaintext(child, pos)
            result.append(text)
        return "".join(result), pos


class CursorMapper:
    """
    Maps cursor positions between Markdown and HTML using the AST.
    """

    def __init__(self, ast: WikiNode) -> None:
        """
        Initialize with a parsed AST that has both md_span and html_span set.

        Args:
            ast: The root node with source mappings.
        """
        self.ast = ast
        self._leaf_nodes: List[WikiNode] = []
        self._collect_leaves(ast)

    def _collect_leaves(self, node: WikiNode) -> None:
        """Collect all leaf nodes (TEXT, WIKILINK) for mapping."""
        if node.node_type in (NodeType.TEXT, NodeType.WIKILINK):
            self._leaf_nodes.append(node)
        for child in node.children:
            self._collect_leaves(child)

    def md_to_html(self, md_pos: int) -> int:
        """
        Map a Markdown cursor position to HTML cursor position.

        Args:
            md_pos: Cursor position in Markdown source.

        Returns:
            Corresponding position in HTML.
        """
        for node in self._leaf_nodes:
            if node.md_span and node.md_span.contains(md_pos):
                # Found the node containing the cursor
                offset = node.md_span.offset_within(md_pos)
                if node.html_span:
                    # For links, we need to account for the tag
                    if node.node_type == NodeType.WIKILINK:
                        target = node.attributes.get("target", "")
                        label = node.attributes.get("label", target)

                        # Check if html_span includes tags or just text
                        span_len = node.html_span.end - node.html_span.start
                        if span_len == len(label):
                            # Plain text mapping (no tags)
                            return node.html_span.start + offset

                        # HTML mapping (with tags)
                        # Cursor is in the label portion
                        # HTML: <a href="target">label</a>
                        # The label starts after <a href="target">
                        tag_prefix = f'<a href="{target}">'
                        return node.html_span.start + len(tag_prefix) + offset

                    return node.html_span.start + offset
        # Fallback: return position clamped to end
        return md_pos

    def html_to_md(self, html_pos: int) -> int:
        """
        Map an HTML cursor position to Markdown cursor position.

        Args:
            html_pos: Cursor position in HTML.

        Returns:
            Corresponding position in Markdown.
        """
        for node in self._leaf_nodes:
            if node.html_span and node.html_span.contains(html_pos):
                offset = node.html_span.offset_within(html_pos)
                if node.md_span:
                    if node.node_type == NodeType.WIKILINK:
                        target = node.attributes.get("target", "")
                        label = node.attributes.get("label", target)

                        # Check if html_span includes tags or just text
                        span_len = node.html_span.end - node.html_span.start
                        if span_len == len(label):
                            # Plain text mapping (no tags)
                            effective_offset = offset
                        else:
                            # In HTML, cursor might be in the label
                            tag_prefix = f'<a href="{target}">'
                            effective_offset = offset - len(tag_prefix)

                        if effective_offset < 0:
                            effective_offset = 0

                        # In MD: [[target|label]] or [[target]]
                        # Label starts at position 2 + len(target) + 1 if has separator
                        if target != label:
                            label_start = 2 + len(target) + 1
                        else:
                            label_start = 2
                        return node.md_span.start + label_start + effective_offset

                    return node.md_span.start + offset
        return html_pos
