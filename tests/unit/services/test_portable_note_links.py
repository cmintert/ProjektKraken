"""Allocated note names and native IDs survive portable Markdown round trips."""

import copy

import frontmatter
import pytest

from src.commands.transfer_commands import ApplyTransferCommand
from src.core.entities import Entity
from src.core.events import Event
from src.core.markdown_content import RenderTarget, parse_content, render_content
from src.services.import_service import ImportService
from src.services.obsidian_exporter import ObsidianExporter
from src.services.portable_note_links import PortableNoteLinks, restore_note_links
from src.services.transfer_exchange import load_sources
from src.services.transfer_import import prepare_import
from src.services.transfer_worker import TransferWorker

pytestmark = pytest.mark.ci_fast


def test_folder_body_links_use_actual_allocated_notes_and_keep_originals(
    db_service, tmp_path
):
    first = Entity(name="A/ldric", type="Person")
    second = Entity(name="A:ldric", type="Person")
    twin_a = Entity(name="Twin", type="Person")
    twin_b = Entity(name="Twin", type="Person")
    event = Event(name="Coronation#1", lore_date=3.0)
    source = Entity(
        name="Story",
        type="Note",
        description=(
            f"See [[id:{first.id}|the king]], [[id:{second.id}|the other king]], "
            f"[[id:{event.id}|the ceremony]], and [[A/ldric]].\n\n"
            "[[Twin]] [[id:absent|Missing]]\n\n"
            f"| Who | When |\n| - | - |\n| [[id:{first.id}|Aldric]] | [[id:{event.id}\\|Day]] |"
        ),
    )
    for entity in (first, second, twin_a, twin_b, source):
        db_service.insert_entity(entity)
    db_service.insert_event(event)
    original = copy.deepcopy(source.to_dict())
    output = tmp_path / "notes"
    assert ObsidianExporter(db_service).export_to_folder(output).success
    notes = {frontmatter.load(path)["uid"]: path for path in output.glob("*.md")}
    assert len(notes) == 6
    assert notes[first.id].name.casefold() != notes[second.id].name.casefold()
    post = frontmatter.load(notes[source.id])
    assert f"[[{notes[first.id].stem}|the king]]" in post.content
    assert f"[[{notes[second.id].stem}|the other king]]" in post.content
    assert f"[[{notes[event.id].stem}|the ceremony]]" in post.content
    assert f"[[{notes[first.id].stem}|A/ldric]]" in post.content
    assert f"[[{notes[first.id].stem}\\|Aldric]]" in post.content
    assert "[[Twin]] [[id:absent|Missing]]" in post.content
    assert post["kraken"]["link_targets"] == {
        notes[first.id].stem: first.id,
        notes[second.id].stem: second.id,
        notes[event.id].stem: event.id,
    }
    assert post["kraken"]["record"]["description"] == original["description"]
    assert db_service.get_entity(source.id).description == original["description"]
    parsed = ImportService.parse_markdown_file(notes[source.id].read_text("utf-8"))
    assert parsed["entities"][0]["description"] == original["description"]
    assert (
        render_content(parse_content(post.content), RenderTarget.PUBLISHED).count("<td")
        == 2
    )


def test_edited_note_import_restores_ids_and_command_undo(db_service, tmp_path):
    target = Entity(name="Aldric", type="Person")
    source = Entity(
        name="Story", type="Note", description=f"Original [[id:{target.id}|ruler]]."
    )
    db_service.insert_entity(target)
    db_service.insert_entity(source)
    output = tmp_path / "notes"
    assert ObsidianExporter(db_service).export_to_folder(output).success
    path = output / "Story.md"
    post = frontmatter.load(path)
    post.content += "\n\nEdited with [[Aldric.md|another label]] and `[[Aldric]]`."
    path.write_text(frontmatter.dumps(post), "utf-8")
    data = load_sources([{"path": str(output)}])
    incoming = next(row for row in data["entities"] if row["id"] == source.id)
    assert f"[[id:{target.id}|ruler]]" in incoming["description"]
    assert f"[[id:{target.id}|another label]]" in incoming["description"]
    assert "`[[Aldric]]`" in incoming["description"]
    review = prepare_import(db_service, data, {"mode": "overwrite"})
    assert not review["errors"]
    command = ApplyTransferCommand(review)
    assert command.execute(db_service).success
    assert db_service.get_entity(source.id).description == incoming["description"]
    command.undo(db_service)
    assert db_service.get_entity(source.id).description == source.description


@pytest.mark.parametrize(
    "literal",
    [
        "`[[id:a|Literal]]`",
        "```md\n[[id:a|Literal]]\n```",
        "    [[id:a|Literal]]",
        r"\[[id:a|Literal]]",
        '<span title="[[id:a|Literal]]">attribute</span>',
        "<code>[[id:a|Literal]]</code>",
        "![[id:a|Literal]]",
    ],
)
def test_literal_examples_and_embeds_are_not_rewritten(literal):
    links = PortableNoteLinks(
        [Entity(id="a", name="Aldric", type="Person")], {"a": "Aldric.md"}
    )
    source = literal + "\n\nActual [[id:a|King]]."
    projected, mapping = links.project(source)
    assert projected == literal + "\n\nActual [[Aldric|King]]."
    assert mapping == {"Aldric": "a"}


def test_table_pipe_aliases_and_case_variants_roundtrip():
    links = PortableNoteLinks(
        [Entity(id="a", name="Aldric", type="Person")], {"a": "Aldric (2).md"}
    )
    source = "| A | B |\n| - | - |\n| [[id:a|King]] | [[Unknown|Label]] |"
    projected, mapping = links.project(source)
    assert "[[Aldric (2)\\|King]]" in projected
    assert "[[Unknown\\|Label]]" in projected
    edited = projected.replace("Aldric (2)", "ALDRIC (2).md")
    restored = restore_note_links(edited, mapping)
    assert "[[id:a\\|King]]" in restored
    assert "[[Unknown\\|Label]]" in restored
    assert (
        render_content(parse_content(restored), RenderTarget.PUBLISHED).count("<td")
        == 2
    )


def test_single_note_only_converts_known_exported_self_target(db_service, tmp_path):
    target = Entity(name="Aldric", type="Person")
    item = Event(name="Coronation", lore_date=0.0)
    item.description = f"[[id:{item.id}|This event]] and [[id:{target.id}|King]]."
    db_service.insert_entity(target)
    db_service.insert_event(item)
    path = ObsidianExporter(db_service).export_single_item(item, tmp_path)
    post = frontmatter.load(path)
    assert "[[Coronation|This event]]" in post.content
    assert f"[[id:{target.id}|King]]" in post.content
    assert post["kraken"]["link_targets"] == {"Coronation": item.id}


def test_note_name_with_md_suffix_uses_full_allocated_filename():
    links = PortableNoteLinks([], {"a": "Chronicle.md.md"})
    projected, mapping = links.project("[[id:a|Chronicle]]")
    assert projected == "[[Chronicle.md.md|Chronicle]]"
    assert restore_note_links(projected, mapping) == "[[id:a|Chronicle]]"


def test_ambiguous_authored_name_does_not_capture_explicit_id_links(
    db_service, tmp_path
):
    first = Entity(name="Twin", type="Person")
    second = Entity(name="Twin", type="Person")
    source = Entity(
        name="Story",
        type="Note",
        description=f"[[id:{first.id}|Twin]] and [[Twin|Twin]].",
    )
    for entity in (first, second, source):
        db_service.insert_entity(entity)
    output = tmp_path / "notes"
    assert ObsidianExporter(db_service).export_to_folder(output).success
    files = {frontmatter.load(path)["uid"]: path for path in output.glob("*.md")}
    post = frontmatter.load(files[source.id])
    assert f"[[{files[first.id].name}|Twin]]" in post.content
    assert "[[Twin|Twin]]" in post.content
    assert post["kraken"]["unresolved_link_targets"] == ["Twin"]
    post.content += "\n\nEdited."
    parsed = ImportService.parse_markdown_file(frontmatter.dumps(post))
    description = parsed["entities"][0]["description"]
    assert f"[[id:{first.id}|Twin]] and [[Twin|Twin]]" in description


def test_unresolved_md_spelling_is_not_captured_by_extension_normalization():
    links = PortableNoteLinks(
        [Entity(id="a", name="Aldric", type="Person")], {"a": "Aldric.md"}
    )
    source = "[[id:a|King]] and [[Aldric.md|Unresolved]]."
    projected, mapping = links.project(source)
    result = restore_note_links(
        projected + " Edited.", mapping, links.unresolved_targets(source)
    )
    assert result == "[[id:a|King]] and [[Aldric.md|Unresolved]]. Edited."


def test_unavoidable_ambiguous_target_collision_fails_explicitly():
    links = PortableNoteLinks([], {"a": "Twin.md"})
    with pytest.raises(ValueError, match="conflict with unresolved targets"):
        links.project("[[id:a|Twin]] [[Twin]] [[Twin.md]]")


@pytest.mark.parametrize("name", ["Title#Heading", "[Place]^Block", "A%%comment"])
def test_export_filenames_avoid_obsidian_target_syntax(db_service, name):
    exporter = ObsidianExporter(db_service)
    filename = exporter._get_unique_filename(name, {})
    assert not any(character in filename for character in "#^[]%")


def test_selected_export_keeps_world_wide_name_ambiguity(db_service, tmp_path):
    first = Entity(name="Twin", type="Person")
    second = Entity(name="Twin", type="Person")
    source = Entity(
        name="Story", type="Note", description=f"[[id:{first.id}|Twin]] and [[Twin]]."
    )
    for entity in (first, second, source):
        db_service.insert_entity(entity)
    worker = TransferWorker(lambda: db_service)
    request = {
        "format": "notes",
        "scope": "selected",
        "selected": [first.id, source.id],
        "include_endpoints": False,
        "world": {"path": str(tmp_path)},
    }
    connection = db_service.get_connection()
    prepared = worker._prepare_export(connection, request)
    assert prepared["note_name_candidates"]["twin"] == sorted([first.id, second.id])
    output = tmp_path / "selected"
    worker._export(
        connection, {**request, "prepared": prepared, "destination": str(output)}
    )
    assert len(list(output.glob("*.md"))) == 2
    post = frontmatter.load(output / "Story.md")
    assert "[[Twin.md|Twin]] and [[Twin]]" in post.content
    assert post["kraken"]["link_targets"] == {"Twin.md": first.id}


@pytest.mark.parametrize("name", ["CON", "nul.txt", "COM1", "LPT9.md"])
def test_windows_device_names_are_regular_exported_files(db_service, tmp_path, name):
    item = Entity(name=name, type="Note")
    path = ObsidianExporter(db_service).export_single_item(item, tmp_path)
    assert path.is_file()
    assert path.name.startswith("_")


def test_unicode_alias_entities_survive_portable_projection():
    item = Entity(id="a", name="Þorn & ð", type="Language")
    links = PortableNoteLinks([item], {"a": "Þorn & ð.md"})
    source = "[[id:a|Þorn &amp; ð]]"
    projected, mapping = links.project(source)
    assert projected == "[[Þorn & ð|Þorn &amp; ð]]"
    assert restore_note_links(projected + "!", mapping) == source + "!"


def test_links_in_footnotes_quotes_and_lists_use_the_shared_syntax():
    links = PortableNoteLinks([], {"a": "Aldric.md"})
    source = (
        "See note[^n].\n\n[^n]: [[id:a|King]]\n\n> [[id:a|Ruler]]\n\n- [[id:a|Person]]"
    )
    projected, mapping = links.project(source)
    assert "[^n]: [[Aldric|King]]" in projected
    assert "> [[Aldric|Ruler]]" in projected
    assert "- [[Aldric|Person]]" in projected
    assert restore_note_links(projected, mapping) == source


def test_alias_with_literal_pipe_does_not_split_portable_table_cells():
    links = PortableNoteLinks([], {"a": "Aldric.md"})
    source = "| A | B |\n| - | - |\n| [[id:a\\|King\\|Ruler]] | next |"
    projected, mapping = links.project(source)
    assert "[[Aldric\\|King\\|Ruler]]" in projected
    rendered = render_content(parse_content(projected), RenderTarget.PUBLISHED)
    assert rendered.count("<td") == 2
    assert ">King|Ruler</a>" in rendered
    restored = restore_note_links(projected + "\n\nEdited.", mapping)
    assert "[[id:a\\|King\\|Ruler]]" in restored


def test_rewriting_preserves_original_newlines_and_unicode_separators():
    links = PortableNoteLinks([], {"a": "Aldric.md"})
    source = "Prefix\u2028text [[id:a|A]].\r\n\r\nTail [[id:a|B]].\r\n"
    projected, mapping = links.project(source)
    assert projected == source.replace("[[id:a|", "[[Aldric|")
    assert restore_note_links(projected, mapping) == source


@pytest.mark.parametrize(
    "mapping", [None, [], {"Note": 3}, {"Note": ""}, {"Note": "a", "note": "b"}]
)
def test_invalid_native_link_provenance_fails_explicitly(mapping):
    with pytest.raises(ValueError, match="Native note link targets"):
        restore_note_links("[[Note]]", mapping)
