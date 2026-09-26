"""Exact-source fallback for Markdown beyond the rich serializer vocabulary."""

import pytest

from src.core.entities import Entity
from src.core.wiki_markdown_grammar import requires_source_mode
from src.gui.widgets.wiki_text_edit import WikiTextEdit
from src.services.obsidian_exporter import ObsidianExporter


@pytest.mark.parametrize(
    "source",
    [
        "- first\n- second",
        "1. first\n2. second",
        "> a quotation",
        "| A | B |\n| --- | --- |\n| 1 | 2 |",
        "`inline code`",
        "```python\nprint(1)\n```",
        "[site](https://example.org)",
        "![image](media.png)",
        "\\*literal asterisk\\*",
        "<b>raw HTML</b>",
        "__underscore emphasis__",
        "#### Fourth-level heading",
    ],
)
def test_richer_markdown_stays_exact_source(qtbot, source):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    assert requires_source_mode(source)

    widget.set_wiki_text(source)
    assert widget.editor._view_mode == "source"
    assert widget.get_wiki_text() == source
    widget.toggle_view_mode()
    assert widget.editor._view_mode == "source"
    assert widget.get_wiki_text() == source

    reopened = WikiTextEdit()
    qtbot.addWidget(reopened)
    reopened.set_wiki_text(widget.get_wiki_text())
    assert reopened.get_wiki_text() == source


@pytest.mark.parametrize(
    "source",
    [
        "Plain prose",
        "# Heading\n\nA paragraph",
        "**bold** and *italic*",
        "See [[id:entity-1|Alpha]]",
    ],
)
def test_supported_vocabulary_opens_in_rich_mode(qtbot, source):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    assert not requires_source_mode(source)
    widget.set_wiki_text(source)
    assert widget.editor._view_mode == "rich"


@pytest.mark.parametrize(
    "source",
    [
        "Ordinary prose with [[Missing Place]] and **bold** text.",
        "- first\n- second\n\n`literal [[link]]`",
    ],
)
def test_markdown_survives_view_save_reopen_and_export(
    qtbot, db_service, tmp_path, source
):
    writer = WikiTextEdit()
    qtbot.addWidget(writer)
    writer.set_wiki_text(source)
    writer.toggle_view_mode()
    writer.toggle_view_mode()
    saved = writer.get_wiki_text()
    assert saved == source

    entity = Entity(name="Draft", type="Concept", description=saved)
    db_service.insert_entity(entity)
    reopened_entity = db_service.get_entity(entity.id)
    assert reopened_entity is not None
    reader = WikiTextEdit()
    qtbot.addWidget(reader)
    reader.set_wiki_text(reopened_entity.description)
    assert reader.get_wiki_text() == source

    exported = ObsidianExporter(db_service).export_single_item(
        reopened_entity, tmp_path
    )
    assert exported is not None
    assert source in exported.read_text(encoding="utf-8")
