"""Shared HTML containment with destination-specific navigation and image rules."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

import nh3

SAFE_TAGS = {
    "a",
    "abbr",
    "b",
    "blockquote",
    "br",
    "code",
    "dd",
    "del",
    "div",
    "dl",
    "dt",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "section",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}
PROTOCOLS = {"http", "https", "mailto"}
_CODE_CLASS = re.compile(r"^language-[A-Za-z0-9_+-]{1,50}$")
_ASCII_CONTROL_LIMIT = 0x20


class _AuthoredHTML(HTMLParser):
    """Remove reserved authority before combining authored and generated HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = "".join(
            f' {name}="{html.escape(value or "", quote=True)}"'
            for name, value in attrs
            if name not in {"class", "data-target"}
        )
        self.parts.append(f"<{tag}{attributes}>")

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")


def authored_html(source: str) -> str:
    """Strip authored navigation metadata without closing inline elements."""
    parser = _AuthoredHTML()
    parser.feed(source)
    parser.close()
    return "".join(parser.parts)


def is_safe_url(value: str) -> bool:
    """Validate publication links, including disguised schemes."""
    decoded = value
    for _ in range(3):
        updated = unquote(html.unescape(decoded))
        if updated == decoded:
            break
        decoded = updated
    if not decoded or "\\" in decoded:
        return False
    if any(char.isspace() or ord(char) < _ASCII_CONTROL_LIMIT for char in decoded):
        return False
    if decoded.startswith("#"):
        return len(decoded) > 1
    if decoded.startswith("//"):
        return False
    try:
        parsed = urlsplit(decoded)
        _ = parsed.port
    except ValueError:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    scheme = parsed.scheme.lower()
    if scheme in {"http", "https"}:
        return bool(parsed.hostname)
    return scheme == "mailto" and not parsed.netloc and bool(parsed.path)


def allow_attribute(tag: str, name: str, value: str) -> bool:
    """Keep presentation attributes bounded and navigation metadata explicit."""
    if tag == "a":
        if name == "href":
            return is_safe_url(value)
        if name == "class":
            return value == "wikilink"
        return name in {"data-target", "title", "id"}
    if tag in {"td", "th"}:
        if name == "align":
            return value in {"left", "center", "right"}
        if name in {"colspan", "rowspan"}:
            return re.fullmatch(r"0*[1-9][0-9]*", value) is not None
    if tag == "code" and name == "class":
        return _CODE_CLASS.fullmatch(value) is not None
    if tag == "ol" and name == "start":
        return re.fullmatch(r"-?\d+", value) is not None
    return name == "id" or (tag == "abbr" and name == "title")


def clean_html(source: str, *, published: bool) -> str:
    """Sanitize rendered output using the destination's navigation and asset rules."""
    attributes = {
        "*": {"id"},
        "a": {"href", "title", "class", "data-target", "id"},
        "abbr": {"title"},
        "code": {"class"},
        "td": {"align", "colspan", "rowspan"},
        "th": {"align", "colspan", "rowspan"},
        "ol": {"start"},
    }
    tags = set(SAFE_TAGS)
    if not published:
        tags.add("img")
        attributes["img"] = {"src", "alt", "title", "width", "height"}

    def filter_attribute(tag: str, name: str, value: str) -> str | None:
        if not published and tag == "a" and name == "href":
            # Relative and ID links are resolved by the local destination adapter.
            if not re.match(r"[A-Za-z][\w+.-]*:", value) or value.startswith("id:"):
                return value
        if not published and tag == "img":
            return value
        return value if allow_attribute(tag, name, value) else None

    def relative_url(value: str) -> str | None:
        if not published or (value.startswith("#") and len(value) > 1):
            return value
        return None

    return nh3.clean(
        source,
        tags=tags,
        attributes=attributes,
        attribute_filter=filter_attribute,
        url_schemes=PROTOCOLS | ({"id", "file"} if not published else set()),
        url_relative=relative_url,
        strip_comments=True,
        link_rel=None,
    )
