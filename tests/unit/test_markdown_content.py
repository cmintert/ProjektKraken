"""Executable Kraken Markdown profile shared by authoring and publication."""

import socket
import zipfile

import pytest
from PySide6.QtGui import QTextCursor

from scripts.markdown_licenses import collect_markdown_licenses
from src.app.markdown_package_probe import MARKDOWN_NOTICES, probe_markdown
from src.core.markdown_content import (
    RenderTarget,
    parse_content,
    render_content,
    resolve_wikilinks_in_source,
)
from src.gui.widgets.longform.content import LongformContentWidget
from src.gui.widgets.wiki_text_edit import WikiTextEdit
from src.services.transfer_document import document_snapshot, write_docx
from src.webserver.markdown_renderer import render_longform_markdown

pytestmark = pytest.mark.ci_fast

VOCABULARY = (
    "# Northern Tongue\n\n"
    "| Word | Meaning | Notes |\n| :--- | ---: | :---: |\n"
    "| þorn | **thorn** | [[id:entity-1|Aldric]] |\n"
    "| ð | | ~~old~~ |\n\n"
    "> Quoted words\n\n- First\n- Second\n\n"
    "See https://example.org.\nNext line."
)


@pytest.mark.parametrize("target", list(RenderTarget))
def test_profile_structures_and_unicode_are_shared(target):
    parsed = parse_content(VOCABULARY)
    assert parsed.source == VOCABULARY
    assert not parsed.rich_editable
    rendered = render_content(parsed, target)
    for fragment in (
        "<table>",
        "<strong>thorn</strong>",
        "þorn",
        "ð",
        "<s>old</s>",
        '<td align="right"></td>',
        '<th align="center">Notes</th>',
        "<blockquote>",
        "<ul>",
        '<a href="https://example.org">',
        "<br>",
    ):
        assert fragment in rendered
    assert rendered.count("<td") == 6
    assert "Aldric" in rendered


@pytest.mark.parametrize("alias", ["[[Target|Label]]", r"[[Target\|Label]]"])
def test_table_aliases_preserve_column_relationships(alias):
    source = f"| A | B |\n| - | - |\n| {alias} | End |"
    result = render_content(parse_content(source), RenderTarget.DESKTOP)
    assert result.count("<td>") == 2
    assert '<a href="Target">Label</a>' in result
    assert "<td>End</td>" in result


def test_code_escaped_examples_embeds_and_html_attributes_stay_literal():
    source = (
        "`[[Code]]` and \\[[Escaped]] and ![[embed.png]]\n\n"
        "```text\n[[Fenced|literal]]\n```\n\n"
        '<code>[[HTML code]]</code> <a title="[[attribute]]">label</a>\n\n'
        "[[Real|Label]]"
    )
    rendered = render_longform_markdown(source)
    assert rendered.count('class="wikilink"') == 1
    assert 'data-target="Real"' in rendered
    assert "[[Code]]" in rendered and "[[Fenced|literal]]" in rendered
    rewritten = resolve_wikilinks_in_source(source, lambda target, label: "#real")
    assert "[Label](#real)" in rewritten
    assert "`[[Code]]`" in rewritten
    assert "[[Fenced|literal]]" in rewritten
    assert "<code>[[HTML code]]</code>" in rewritten


@pytest.mark.parametrize("target", list(RenderTarget))
def test_reading_compatibility_extensions(target):
    source = (
        "HTML needs a note[^n].\n\n*[HTML]: Hypertext Markup Language\n\n"
        "Term\n: Definition\n\n<code>HTML</code>\n\n[^n]: Footnote text."
    )
    rendered = render_content(parse_content(source), target)
    assert '<abbr title="Hypertext Markup Language">HTML</abbr>' in rendered
    assert "<dl>" in rendered and "Definition" in rendered
    assert 'href="#fn1"' in rendered and 'id="fn1"' in rendered
    assert "Footnote text." in rendered
    assert "<code>HTML</code>" in rendered


def test_parsing_and_rendering_do_not_connect_to_network(monkeypatch):
    def reject_connection(*args, **kwargs):
        raise AssertionError("Markdown processing attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", reject_connection)
    parsed = parse_content(VOCABULARY)
    for target in RenderTarget:
        assert "<table>" in render_content(parsed, target)


def test_safe_html_keeps_tables_and_cannot_forge_navigation():
    source = (
        '<table><tr><td colspan="2">Wide</td></tr>'
        "<tr><td>A</td><td></td></tr></table>\n\n"
        '<a class="wikilink" data-target="Forged" href="javascript:alert(1)">Fake</a>\n\n'
        "[[Real]]"
    )
    rendered = render_longform_markdown(source)
    assert '<td colspan="2">Wide</td>' in rendered
    assert rendered.count('class="wikilink"') == 1
    assert "Forged" not in rendered and "javascript" not in rendered


@pytest.mark.parametrize("source", ["# Heading\n\n\nBody\n\n", "A &amp; B", "\n\n"])
def test_unedited_source_is_exact_through_view_changes(qtbot, source):
    writing = WikiTextEdit()
    qtbot.addWidget(writing)
    writing.set_wiki_text(source)
    assert writing.get_wiki_text() == source
    writing.toggle_view_mode()
    writing.toggle_view_mode()
    assert writing.get_wiki_text() == source


def test_edit_and_undo_restore_original_source_baseline(qtbot):
    writing = WikiTextEdit()
    qtbot.addWidget(writing)
    source = "Before\n\n\nAfter"
    writing.set_wiki_text(source)
    cursor = writing.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    writing.setTextCursor(cursor)
    writing.editor.insertPlainText(" edited")
    assert writing.get_wiki_text().endswith("After edited")
    writing.toggle_view_mode()
    writing.editor.undo()
    assert writing.get_wiki_text() == source


def test_desktop_adapter_uses_shared_profile(qtbot):
    widget = LongformContentWidget()
    qtbot.addWidget(widget)
    assert "<s>old</s>" in widget._render_markdown_fragment("~~old~~")


def test_document_export_retains_strike_alignment_and_literal_code(qapp, tmp_path):
    item = {
        "id": "entity-1",
        "name": "Chapter",
        "table": "entities",
        "meta": {},
        "heading_level": 1,
        "content": "| A | B |\n| --- | ---: |\n| ~~old~~ | right |\n\n`[[Chapter]]`",
    }
    snapshot = document_snapshot([item], {"title": "Book"}, str(tmp_path))
    assert "<s>old</s>" in snapshot["html"]
    assert 'align="right"' in snapshot["html"]
    assert "`[[Chapter]]`" in snapshot["markdown"]
    destination = tmp_path / "book.docx"
    write_docx(snapshot, destination)
    with zipfile.ZipFile(destination) as archive:
        document = archive.read("word/document.xml").decode()
    assert "w:strike" in document
    assert 'w:val="right"' in document


def test_packaged_parser_features_and_complete_notices(tmp_path):
    directory = collect_markdown_licenses(tmp_path / "notices")
    evidence = probe_markdown(directory)
    assert len(evidence["licence_files"]) == len(MARKDOWN_NOTICES)
    mdurl = (directory / "mdurl.txt").read_text(encoding="utf-8")
    assert "Joyent" in mdurl
    (directory / "mdurl.txt").unlink()
    with pytest.raises(OSError):
        probe_markdown(directory)


@pytest.mark.parametrize("target", ["custom:destination", "https://example.org"])
def test_unrepresentable_link_uses_exact_source(qtbot, target):
    writing = WikiTextEdit()
    qtbot.addWidget(writing)
    source = f"[[{target}|Label]]"
    writing.set_wiki_text(source)
    assert writing.editor._view_mode == "source"
    assert writing.get_wiki_text() == source


def test_source_fallback_selection_uses_original_blank_line_offsets(qtbot):
    from PySide6.QtCore import QMimeData

    writing = WikiTextEdit()
    qtbot.addWidget(writing)
    source = "First\n\n\nSecond\n\nThird"
    writing.set_wiki_text(source)
    writing.setTextCursor(writing.document().find("Third"))
    clipboard = QMimeData()
    clipboard.setText("`replacement`")
    writing.editor.insertFromMimeData(clipboard)
    assert writing.get_wiki_text() == "First\n\n\nSecond\n\n`replacement`"


@pytest.mark.parametrize(
    "source", ["Title\n=====", "  # Heading", "A &amp; B", "## Title ##"]
)
def test_spelling_outside_legacy_cursor_mapping_remains_exact_source(qtbot, source):
    writing = WikiTextEdit()
    qtbot.addWidget(writing)
    writing.set_wiki_text(source)
    assert writing.editor._view_mode == "source"
    assert writing.get_wiki_text() == source
