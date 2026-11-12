"""Narrow Kraken wikilink and legacy abbreviation rules for markdown-it."""

from __future__ import annotations

import re
from html import unescape

from markdown_it import MarkdownIt
from markdown_it.rules_core import StateCore
from markdown_it.rules_inline import StateInline
from markdown_it.rules_inline.backticks import backtick
from markdown_it.token import Token
from markdown_it.utils import EnvType

WIKI_PATTERN = re.compile(r"\[\[([^\[\]\n|]+?)(?:\\?\|([^\]\n]+))?\]\]")
_ABBREVIATION = re.compile(r"^\*\[([^\]\n]+)\]:\s*(.+)$")
_DELIMITER = re.compile(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+\|?\s*$")


def _inside_literal_html(tokens: list[Token]) -> bool:
    literal = False
    for token in tokens:
        if token.type == "html_inline":
            if re.match(r"<(?:code|pre|script|style)(?:\s|>)", token.content, re.I):
                literal = True
            elif re.match(r"</(?:code|pre|script|style)\s*>", token.content, re.I):
                literal = False
    return literal


def wikilink(state: StateInline, silent: bool) -> bool:
    """Recognize an identity-bearing link outside code and authored HTML."""
    if (
        not state.src.startswith("[[", state.pos)
        or (state.pos > 0 and state.src[state.pos - 1] == "!")
        or _inside_literal_html(state.tokens)
    ):
        return False
    match = WIKI_PATTERN.match(state.src, state.pos)
    if match is None:
        return False
    target = match[1].strip()
    if not target:
        return False
    if not silent:
        token = state.push("kraken_wikilink", "a", 0)
        token.content = unescape(match[2] if match[2] is not None else target)
        token.meta["target"] = unescape(target)
        token.meta["start"] = state.pos
        token.meta["end"] = match.end()
    state.pos = match.end()
    return True


def _record_code_span(state: StateInline, silent: bool) -> bool:
    start, count = state.pos, len(state.tokens)
    matched = backtick(state, silent)
    if len(state.tokens) > count and state.tokens[-1].type == "code_inline":
        state.env.setdefault("code_spans", []).append((start, state.pos))
    return matched


def _escape_aliases(line: str, parser: MarkdownIt) -> str:
    """Escape legacy table aliases in the parser buffer, leaving code intact."""
    environment: EnvType = {}
    parser.inline.parse(line, parser, environment, [])
    spans = environment.get("code_spans", [])
    for match in reversed(list(WIKI_PATTERN.finditer(line))):
        prefix = line[: match.start()]
        escaped = (len(prefix) - len(prefix.rstrip("\\"))) % 2
        literal = any(start <= match.start() < end for start, end in spans)
        if match[2] is not None and "\\|" not in match[0] and not (escaped or literal):
            line = (
                line[: match.start()]
                + match[0].replace("|", "\\|")
                + line[match.end() :]
            )
    return line


def prepare_compatibility(state: StateCore) -> None:
    """Keep compatibility rewrites separate from the canonical stored source."""
    lines = state.src.split("\n")
    # CommonMark block classification excludes fenced/indented code and raw HTML.
    parser = MarkdownIt("commonmark")
    parser.inline.ruler.at("backticks", _record_code_span)
    blocks = parser.parse(state.src)
    abbreviations: dict[str, str] = {}
    for token in blocks:
        if token.type != "inline" or token.map is None:
            continue
        start, end = token.map
        table = False
        for line in range(start, end):
            definition = _ABBREVIATION.match(lines[line])
            if definition:
                abbreviations[definition[1]] = definition[2]
                lines[line] = ""
            if line + 1 < end and _DELIMITER.fullmatch(lines[line + 1]):
                table = True
            if table:
                lines[line] = _escape_aliases(lines[line], parser)
    state.env["kraken_abbreviations"] = abbreviations
    state.src = "\n".join(lines)


def expand_abbreviations(state: StateCore) -> None:
    """Render the abbreviations understood by the previous Extra extension."""
    abbreviations = state.env.get("kraken_abbreviations", {})
    if not abbreviations:
        return
    pattern = re.compile(
        r"(?<!\w)(" + "|".join(re.escape(key) for key in abbreviations) + r")(?!\w)"
    )
    for parent in state.tokens:
        if parent.children is not None:
            parent.children = _abbreviated_children(
                parent.children, pattern, abbreviations
            )


def _abbreviated_children(
    children: list[Token], pattern: re.Pattern[str], abbreviations: dict[str, str]
) -> list[Token]:
    result: list[Token] = []
    for child in children:
        if child.type != "text" or _inside_literal_html(result):
            result.append(child)
            continue
        position = 0
        for match in pattern.finditer(child.content):
            result.append(
                Token("text", "", 0, content=child.content[position : match.start()])
            )
            result.append(
                Token("abbr_open", "abbr", 1, attrs={"title": abbreviations[match[0]]})
            )
            result.append(Token("text", "", 0, content=match[0]))
            result.append(Token("abbr_close", "abbr", -1))
            position = match.end()
        result.append(Token("text", "", 0, content=child.content[position:]))
    return result
