"""Decide when Markdown must stay in exact, editable source form."""

import re
from html.parser import HTMLParser

from src.core.markdown_content import parse_content

_BLOCK_CONSTRUCT = re.compile(
    r"(?m)^(?:[ \t]{4,}|[ \t]{0,3}(?:[-+*] |\d+[.)] |> |```|~~~|"
    r"#{4,6} |\| |: |(?:---|\*\*\*|___)\s*$))"
)
_RICH_INLINE_CONSTRUCT = re.compile(
    r"`|\\[\\`*_{}\[\]()#+.!<>-]|!?\[[^\]\n]+\]\([^\n)]*\)|"
    r"\[[^\]\n]+\]\[[^\]\n]*\]|<[/!A-Za-z][^>]*>|~~|__|"
    r"(?<!\w)_[^_\n]+_(?!\w)|!\[\[|(?m:^[ \t]{0,3}\[[^\]\n]+\]:)"
)

_RICH_HTML_TAGS = frozenset(
    {
        "html",
        "head",
        "body",
        "meta",
        "style",
        "title",
        "p",
        "div",
        "br",
        "h1",
        "h2",
        "h3",
        "b",
        "strong",
        "i",
        "em",
        "span",
        "a",
    }
)
_UNSUPPORTED_CSS = re.compile(
    r"line-through|text-decoration[^;]*underline|white-space\s*:\s*pre|"
    r"mso-list\s*:",
    re.IGNORECASE,
)


class _ClipboardHTML(HTMLParser):
    """Recognize markup outside the current rich serializer's vocabulary."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.requires_source = False
        self._in_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        styles = dict(attrs).get("style") or ""
        self._in_style = tag == "style"
        if tag not in _RICH_HTML_TAGS or _UNSUPPORTED_CSS.search(styles):
            self.requires_source = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self._in_style = False

    def handle_data(self, data: str) -> None:
        if self._in_style and _UNSUPPORTED_CSS.search(data):
            self.requires_source = True


def clipboard_html_requires_source(html: str) -> bool:
    """Preserve unsupported clipboard structures as editable HTML source."""
    parser = _ClipboardHTML()
    parser.feed(html)
    parser.close()
    return parser.requires_source


def requires_source_mode(source: str) -> bool:
    """Keep constructs outside the rich serializer's vocabulary verbatim."""
    parsed = parse_content(source)
    if any(token.type == "table_open" for token in parsed.tokens):
        return not parsed.rich_editable
    return bool(
        not parsed.rich_editable
        or _BLOCK_CONSTRUCT.search(source)
        or _RICH_INLINE_CONSTRUCT.search(source)
        or re.search(r"(?m)^.+\|.+\n[ \t]*\|?[ \t]*:?-{3,}", source)
    )
