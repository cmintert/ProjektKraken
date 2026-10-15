"""Sphinx extension emitting resolved manual content for Qt rich text."""

from __future__ import annotations

import html
import json
import posixpath
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from docutils import nodes
from sphinx import addnodes
from sphinx.application import Sphinx
from sphinx.builders import Builder
from sphinx.errors import SphinxError

from src.core.help_bundle import file_hash

TAGS = {
    "paragraph": "p",
    "bullet_list": "ul",
    "enumerated_list": "ol",
    "list_item": "li",
    "emphasis": "em",
    "strong": "strong",
    "literal": "code",
    "literal_block": "pre",
    "block_quote": "blockquote",
    "table": "table",
    "thead": "thead",
    "tbody": "tbody",
    "row": "tr",
    "entry": "td",
    "definition_list": "dl",
    "definition_list_item": "div",
    "term": "dt",
    "definition": "dd",
    "superscript": "sup",
    "subscript": "sub",
    "inline": "span",
    "caption": "p",
    "rubric": "h3",
    "footnote": "div",
    "label": "b",
    "footnote_reference": "sup",
    "attribution": "p",
}
CONTAINERS = {
    "document",
    "section",
    "container",
    "compound",
    "compact_paragraph",
    "tgroup",
    "figure",
    "description",
    "field_body",
}
IGNORED = {"comment", "colspec", "index"}
ADMONITIONS = {"admonition", "note", "warning", "tip", "important", "caution"}


def fail(node: nodes.Node, message: str) -> None:
    """Fail generation with the canonical source location."""
    raise SphinxError(f"{node.source}:{node.line}: {message}")


class QtRenderer:
    """Serialize an explicit safe subset instead of silently dropping constructs."""

    def __init__(self, builder: HelpBuilder, docname: str) -> None:
        """Bind one resolved page to the output bundle."""
        self.builder = builder
        self.docname = docname
        self.anchors: set[str] = set()

    def render(self, node: nodes.Node) -> str:
        """Render a node, rejecting unsupported semantic or executable content."""
        if isinstance(node, nodes.Text):
            return html.escape(str(node))
        if not isinstance(node, nodes.Element):
            fail(node, "Unsupported non-element node")
        name = node.tagname
        anchors = self._anchors(node)
        if name in IGNORED:
            return ""
        if name == "image":
            return anchors + self._image(node)
        if name == "reference":
            return anchors + self._reference(node)
        if isinstance(node, addnodes.toctree):
            resolved = self.builder.env.resolve_toctree(
                self.docname, self.builder, node, includehidden=True
            )
            return anchors + (self.render(resolved) if resolved else "")
        body = "".join(self.render(child) for child in node.children)
        if name == "section" and body.startswith("<h"):
            opening, remaining = body.split(">", 1)
            return opening + ">" + anchors + remaining
        if name in CONTAINERS or name == "target":
            return anchors + body
        if name == "title":
            depth = 0
            parent = node.parent
            while parent is not None:
                depth += isinstance(parent, nodes.section)
                parent = parent.parent
            tag = f"h{min(max(depth, 1), 6)}"
            return f"<{tag}>{anchors}{body}</{tag}>"
        if name == "transition":
            return anchors + "<hr>"
        if name in ADMONITIONS:
            return f"{anchors}<blockquote>{body}</blockquote>"
        if name not in TAGS:
            fail(node, f"Unsupported Help construct: {name}")
        tag = TAGS[name]
        attributes = self._attributes(node)
        return f"<{tag}{attributes}>{anchors}{body}</{tag}>"

    def _anchors(self, node: nodes.Element) -> str:
        ids = node.get("ids", [])
        self.anchors.update(ids)
        # Qt collapses adjacent empty anchors; an invisible character retains each.
        return "".join(
            f'<a name="{html.escape(a, quote=True)}">&#8203;</a>' for a in ids
        )

    def _attributes(self, node: nodes.Element) -> str:
        attrs: dict[str, object] = {}
        if node.tagname == "enumerated_list":
            attrs["start"] = node.get("start", 1)
            attrs["type"] = {
                "arabic": "1",
                "loweralpha": "a",
                "upperalpha": "A",
                "lowerroman": "i",
                "upperroman": "I",
            }.get(node.get("enumtype", "arabic"), "1")
        if node.tagname == "entry":
            attrs["colspan"] = node.get("morecols", 0) + 1
            attrs["rowspan"] = node.get("morerows", 0) + 1
        if node.tagname == "table":
            attrs.update(border=1, cellspacing=0, cellpadding=4)
        return "".join(
            f' {k}="{html.escape(str(v), quote=True)}"' for k, v in attrs.items()
        )

    def _reference(self, node: nodes.Element) -> str:
        body = "".join(self.render(child) for child in node.children)
        uri = node.get("refuri", "#" + node.get("refid", ""))
        parsed = urlsplit(uri)
        if parsed.scheme or parsed.netloc:
            return f"<span>{body} ({html.escape(uri)})</span>"
        return f'<a href="{html.escape(uri, quote=True)}">{body}</a>'

    def _image(self, node: nodes.Element) -> str:
        uri = str(node["uri"])
        if urlsplit(uri).scheme or urlsplit(uri).netloc:
            fail(node, "Remote images are not allowed in offline Help")
        source = (Path(self.builder.srcdir) / unquote(uri)).resolve()
        if not source.is_relative_to(Path(self.builder.srcdir).resolve()):
            fail(node, "Image escapes the canonical manual")
        if not source.is_file():
            fail(node, f"Missing image: {uri}")
        if source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            fail(node, "Help images must use a Qt-readable raster format")
        target = "assets/" + file_hash(source) + source.suffix.lower()
        dest = Path(self.builder.outdir) / target
        dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(source.read_bytes())
        alt = html.escape(str(node.get("alt", "")), quote=True)
        relative = posixpath.relpath(target, posixpath.dirname(self.docname) or ".")
        return f'<img src="{relative}" alt="{alt}">'


class HelpBuilder(Builder):
    """Build renderer-compatible pages and section search records."""

    name = "kraken_help"
    format = "html"
    math_renderer_name = "mathjax"
    allow_parallel = False
    supported_image_types = ["image/png", "image/jpeg", "image/gif", "image/webp"]
    # Keep URIs intact so Sphinx's downloader/converter does not fetch them.
    # QtRenderer rejects remote and data resources with a source diagnostic.
    supported_remote_images = True
    supported_data_uri_images = True

    def init(self) -> None:
        """Initialize fresh build output records."""
        self.pages: list[dict[str, Any]] = []
        self.search: list[dict[str, Any]] = []
        self.excerpts: dict[str, str] = {}
        self.inspection_topics: dict[str, list[str]] = {}
        registry = json.loads(
            (Path(self.confdir) / "help-topics.json").read_text("utf-8")
        )
        self.excerpt_targets = {
            topic["control_excerpt_target"]
            for topic in registry["topics"]
            if topic.get("control_excerpt_target")
        }
        inspection_path = Path(self.confdir) / "help-inspection.json"
        if inspection_path.is_file():
            inventory = json.loads(inspection_path.read_text("utf-8"))
            self.excerpt_targets.update(
                binding["target"] for binding in inventory["bindings"]
            )
            self.excerpt_targets.update(inventory.get("shared_targets", []))
            for binding in inventory["bindings"]:
                self.inspection_topics.setdefault(binding["target"], []).append(
                    binding["topic_id"]
                )

    def get_outdated_docs(self) -> str:
        """Always regenerate from the resolved canonical manual."""
        return "all documents"

    def get_target_uri(self, docname: str, typ: str | None = None) -> str:
        """Return the stable generated relative page path."""
        return docname + ".html"

    def prepare_writing(self, docnames: set[str]) -> None:
        """No website templates or runtime styling are needed."""

    def write_doc(self, docname: str, doctree: nodes.document) -> None:
        """Write HTML and search text from the same resolved doctree."""
        renderer = QtRenderer(self, docname)
        body = renderer.render(doctree)
        page = docname + ".html"
        title = self.env.titles[docname].astext()
        path = Path(self.outdir) / page
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '<html><head><meta charset="utf-8"><title>'
            + html.escape(title)
            + "</title></head><body>"
            + body
            + "</body></html>\n",
            encoding="utf-8",
        )
        self.pages.append(
            {"path": page, "title": title, "anchors": sorted(renderer.anchors)}
        )
        for element in doctree.findall(nodes.Element):
            for target in set(element.get("ids", [])).intersection(
                self.excerpt_targets
            ):
                self.excerpts[page + "#" + target] = QtRenderer(self, docname).render(
                    element
                )
                self._search_excerpt(page, target, element)
        sections = list(doctree.findall(nodes.section))
        for section in sections:
            heading = next(iter(section.findall(nodes.title)), None)
            text = "\n".join(
                child.astext()
                for child in section.children
                if not isinstance(child, nodes.section)
                and not set(child.get("ids", [])).intersection(self.inspection_topics)
            )

            anchors = set(section["ids"])
            for child in section.children:
                if not isinstance(child, nodes.section):
                    for element in child.findall(nodes.Element):
                        anchors.update(element.get("ids", []))
            self.search.append(
                {
                    "page": page,
                    "fragment": section["ids"][0],
                    "title": heading.astext() if heading else title,
                    "text": text,
                    "topic_ids": [],
                    "anchors": sorted(anchors),
                }
            )

    def _search_excerpt(self, page: str, target: str, element: nodes.Element) -> None:
        """Index each control at its real anchor using its canonical prose."""
        topic_ids = self.inspection_topics.get(target)
        if topic_ids is None:
            return
        title = next(iter(element.findall(nodes.strong)), None)
        self.search.append(
            {
                "page": page,
                "fragment": target,
                "title": title.astext() if title is not None else "Control explanation",
                "text": element.astext(),
                "topic_ids": sorted(set(topic_ids)),
                "anchors": [target],
            }
        )

    def finish(self) -> None:
        """Persist deterministic intermediate records for bundle validation."""
        for name, records in (("pages.json", self.pages), ("search.json", self.search)):
            (Path(self.outdir) / name).write_text(
                json.dumps(
                    sorted(
                        records,
                        key=lambda r: (
                            r.get("path", r.get("page")),
                            r.get("fragment", ""),
                        ),
                    ),
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        (Path(self.outdir) / "excerpts.json").write_text(
            json.dumps(self.excerpts, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n",
            encoding="utf-8",
        )


def setup(app: Sphinx) -> dict[str, Any]:
    """Register the build-only Help extension."""
    app.add_builder(HelpBuilder)
    return {"version": "1", "parallel_read_safe": True}
