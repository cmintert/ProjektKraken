"""Kraken Markdown profile and pure parsing/rendering entry points."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum
from html import escape
from typing import Any, cast

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.rules_block.table import escapedSplit
from markdown_it.token import Token
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.footnote import footnote_plugin

from src.core.markdown_extensions import (
    expand_abbreviations,
    prepare_compatibility,
    wikilink,
)
from src.core.markdown_html import authored_html, clean_html, is_safe_url
from src.core.wiki_ast import WikiASTParser, WikiASTSerializer

PROFILE_VERSION = 1
WikiLinkResolver = Callable[[str, str], str | None]


class _ContentParser(MarkdownIt):
    """Leave destination acceptance to the shared output sanitizer."""

    def validateLink(self, url: str) -> bool:  # noqa: N802
        """Parse even rejected destinations so output retains only their labels."""
        return True


class RenderTarget(Enum):
    """Destinations sharing syntax while owning their navigation conventions."""

    EDITOR = "editor"
    DESKTOP = "desktop"
    PUBLISHED = "published"
    EXPORT = "export"


@dataclass(frozen=True)
class ParsedMarkdownContent:
    """An owned parse result with its exact canonical source."""

    source: str
    tokens: tuple[Token, ...]
    rich_editable: bool
    source_reasons: tuple[str, ...]
    environment: dict[str, Any] = field(repr=False)


def _parser() -> MarkdownIt:
    parser = _ContentParser(
        "commonmark", {"breaks": True, "html": True, "linkify": True}
    )
    parser.enable(["table", "strikethrough", "linkify"])
    # Parse destinations first. Each rendering destination applies its URL policy.
    parser.use(footnote_plugin).use(deflist_plugin)
    parser.inline.ruler.before("link", "kraken_wikilink", wikilink)
    parser.core.ruler.before("block", "kraken_compatibility", prepare_compatibility)
    parser.core.ruler.after("inline", "kraken_abbreviations", expand_abbreviations)
    return parser


def _walk(tokens: Iterable[Token]) -> Iterable[Token]:
    for token in tokens:
        yield token
        yield from _walk(token.children or ())


def _projection_text(tokens: list[Token]) -> str:
    blocks = []
    for token in tokens:
        if token.type == "inline":
            fragments = []
            for child in token.children or ():
                fragments.append(
                    "\n" if child.type in {"softbreak", "hardbreak"} else child.content
                )
            blocks.append("".join(fragments))
    return "\n".join(blocks)


def resolve_wikilinks_in_source(source: str, resolver: WikiLinkResolver) -> str:
    """Prepare portable document links without rewriting literal examples."""
    parser = _parser()
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    replacements: dict[int, tuple[int, str]] = {}
    for block in MarkdownIt("commonmark").parse(source):
        if block.type != "inline" or block.map is None:
            continue
        start, end = (offsets[line] for line in block.map)
        children: list[Token] = []
        parser.inline.parse(source[start:end], parser, {}, children)
        for token in children:
            if token.type != "kraken_wikilink":
                continue
            href = resolver(str(token.meta["target"]), token.content)
            label = token.content.replace("[", "\\[").replace("]", "\\]")
            replacement = f"[{label}]({href})" if href else label
            replacements[start + token.meta["start"]] = (
                start + token.meta["end"],
                replacement,
            )
    for start, (end, replacement) in sorted(replacements.items(), reverse=True):
        source = source[:start] + replacement + source[end:]
    return source


def _unrepresentable_links(tokens: Iterable[Token]) -> bool:
    """Reject navigation whose semantics the editable projection cannot retain."""
    for token in _walk(tokens):
        target = (
            str(token.meta["target"])
            if token.type == "kraken_wikilink"
            else str(token.attrGet("href") or "")
            if token.type == "link_open"
            else ""
        )
        if re.match(r"[A-Za-z][\w+.-]*:", target) and not target.startswith("id:"):
            if token.type == "kraken_wikilink" or not is_safe_url(target):
                return True
    return False


def _table_shape_safe(source: str, ranges: list[list[int]]) -> bool:
    """Keep overfull rows in Source rather than dropping parser-ignored cells."""
    lines = source.splitlines()
    for start, end in ranges:
        width = 0
        for index in [start, *range(start + 2, end)]:
            cells = escapedSplit(lines[index].strip())
            if cells and not cells[0]:
                cells.pop(0)
            if cells and not cells[-1]:
                cells.pop()
            if index == start:
                width = len(cells)
            elif len(cells) > width:
                return False
    return True


def parse_content(source: str) -> ParsedMarkdownContent:
    """Parse locally and identify content outside the conservative Rich subset."""
    environment: dict[str, Any] = {}
    tokens = _parser().parse(source, environment)
    supported = {
        "paragraph_open",
        "paragraph_close",
        "heading_open",
        "heading_close",
        "inline",
        "text",
        "strong_open",
        "strong_close",
        "em_open",
        "em_close",
        "softbreak",
        "hardbreak",
        "kraken_wikilink",
    }
    table_tokens = {
        "table_open",
        "table_close",
        "thead_open",
        "thead_close",
        "tbody_open",
        "tbody_close",
        "tr_open",
        "tr_close",
        "th_open",
        "th_close",
        "td_open",
        "td_close",
    }
    cell_tokens = supported | {
        "s_open",
        "s_close",
        "code_inline",
        "link_open",
        "link_close",
    }
    reasons: set[str] = set()
    in_table = False
    table_ranges = []
    for token in tokens:
        if token.type == "table_open":
            in_table = True
            if token.map:
                table_ranges.append(token.map)
        allowed = cell_tokens | table_tokens if in_table else supported
        reasons.update(
            child.type for child in _walk([token]) if child.type not in allowed
        )
        if token.type == "table_close":
            in_table = False
    if any(token.tag in {"h4", "h5", "h6"} for token in tokens):
        reasons.add("heading_level")
    if environment.get("references") or environment.get("kraken_abbreviations"):
        reasons.add("definitions")
    if _unrepresentable_links(tokens):
        reasons.add("unrepresentable_link")
    if table_ranges:
        if not _table_shape_safe(
            str(environment["kraken_source_buffer"]), table_ranges
        ):
            reasons.add("overfull_table")
        lines = source.splitlines(keepends=True)
        for start, end in table_ranges:
            lines[start:end] = ["\n"] * (end - start)
        reasons.update(parse_content("".join(lines)).source_reasons)
    elif not reasons:
        mapped_text, _ = WikiASTSerializer().to_plaintext(WikiASTParser().parse(source))
        if mapped_text != _projection_text(tokens):
            reasons.add("cursor_mapping")
    return ParsedMarkdownContent(
        source, tuple(tokens), not reasons, tuple(sorted(reasons)), environment
    )


def render_content(
    parsed: ParsedMarkdownContent,
    target: RenderTarget,
    link_resolver: WikiLinkResolver | None = None,
) -> str:
    """Render one parse result with bounded HTML and destination-owned links."""
    parser = _parser()
    published = target == RenderTarget.PUBLISHED

    def wiki_rule(
        renderer: RendererHTML, tokens: list[Token], index: int, options: Any, env: Any
    ) -> str:
        token = tokens[index]
        destination = str(token.meta["target"])
        label = escape(token.content)
        if published:
            return f'<a class="wikilink" data-target="{escape(destination, quote=True)}">{label}</a>'
        href = (
            link_resolver(destination, token.content) if link_resolver else destination
        )
        if href is None:
            return label
        return f'<a href="{escape(href, quote=True)}">{label}</a>'

    def html_rule(
        renderer: RendererHTML, tokens: list[Token], index: int, options: Any, env: Any
    ) -> str:
        return authored_html(tokens[index].content)

    def cell_rule(
        renderer: RendererHTML, tokens: list[Token], index: int, options: Any, env: Any
    ) -> str:
        token = tokens[index]
        alignment = re.fullmatch(
            r"text-align:(left|center|right)", str(token.attrGet("style") or "")
        )
        attribute = f' align="{alignment[1]}"' if alignment else ""
        return f"<{token.tag}{attribute}>"

    renderer = cast(RendererHTML, parser.renderer)
    parser.add_render_rule("kraken_wikilink", wiki_rule)
    parser.add_render_rule("html_block", html_rule)
    parser.add_render_rule("html_inline", html_rule)
    parser.add_render_rule("td_open", cell_rule)
    parser.add_render_rule("th_open", cell_rule)
    rendered = renderer.render(list(parsed.tokens), parser.options, parsed.environment)
    return clean_html(rendered, published=published)
