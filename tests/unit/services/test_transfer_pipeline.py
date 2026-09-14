"""Behavioral coverage for reviewed, reversible transfer operations."""

import json
import sqlite3
import zipfile

import pytest

from src.commands.transfer_commands import ApplyTransferCommand
from src.core.calendar import CalendarConfig
from src.core.date_parser import DateParser
from src.core.entities import Entity
from src.core.transfer import LORE_JSON_EXAMPLE_TEXT
from src.services.repositories.transfer_repository import snapshot
from src.services.transfer_document import document_snapshot, write_docx, write_pdf
from src.services.transfer_exchange import csv_text, load_sources, parse_json
from src.services.transfer_files import staged_output
from src.services.transfer_import import prepare_import
from src.services.transfer_worker import TransferWorker
from src.services.world_transfer import export_world, import_world, inspect_package


def batch(**kwargs):
    return {"entities": [], "events": [], "relations": [], **kwargs}


def test_review_does_not_write_and_persistent_undo_restores_tags(db_service):
    original = Entity(
        id="00000000-0000-4000-8000-000000000001",
        name="Existing",
        type="person",
        attributes={"_tags": ["00000000-0000-4000-8000-000000000001"]},
    )
    db_service.insert_entity(original)
    db_service.assign_tag_to_entity(
        "00000000-0000-4000-8000-000000000001", "00000000-0000-4000-8000-000000000001"
    )
    before = snapshot(db_service.get_connection())
    data = batch(
        entities=[
            {
                "id": "00000000-0000-4000-8000-000000000001",
                "name": "Existing",
                "description": "00000000-0000-4000-8000-000000000002",
                "tags": ["00000000-0000-4000-8000-000000000002"],
            },
            {
                "id": "00000000-0000-4000-8000-000000000002",
                "name": "New",
                "type": "person",
            },
        ],
        relations=[
            {
                "id": "00000000-0000-4000-8000-000000000003",
                "source_id": "00000000-0000-4000-8000-000000000001",
                "target_id": "00000000-0000-4000-8000-000000000002",
                "rel_type": "knows",
            }
        ],
    )
    review = prepare_import(db_service, data, {"mode": "update"})
    assert not review["errors"]
    assert snapshot(db_service.get_connection()) == before
    command = ApplyTransferCommand(review)
    assert command.execute(db_service).success
    after = snapshot(db_service.get_connection())
    assert db_service.get_entity("00000000-0000-4000-8000-000000000002") is not None
    assert {
        t["name"]
        for t in db_service.get_tags_for_entity("00000000-0000-4000-8000-000000000001")
    } == {
        "00000000-0000-4000-8000-000000000001",
        "00000000-0000-4000-8000-000000000002",
    }
    restored = ApplyTransferCommand.from_dict(command.to_dict())
    assert restored.undo(db_service).success
    assert snapshot(db_service.get_connection()) == before
    assert restored.execute(db_service).success
    assert snapshot(db_service.get_connection()) == after


def test_skip_and_repeated_json_import_do_not_change_records(db_service):
    data = batch(
        entities=[
            {
                "id": "00000000-0000-4000-8000-000000000004",
                "name": "Alpha",
                "type": "person",
            },
            {
                "id": "00000000-0000-4000-8000-000000000005",
                "name": "Beta",
                "type": "person",
            },
        ],
        relations=[
            {
                "id": "00000000-0000-4000-8000-000000000006",
                "source_id": "00000000-0000-4000-8000-000000000004",
                "target_id": "00000000-0000-4000-8000-000000000005",
                "rel_type": "knows",
            }
        ],
    )
    first = prepare_import(db_service, data, {"mode": "skip"})
    assert ApplyTransferCommand(first).execute(db_service).success
    second = prepare_import(db_service, data, {"mode": "skip"})
    assert second["delta"] == []
    assert (
        db_service.get_all_relations()[0]["id"]
        == "00000000-0000-4000-8000-000000000006"
    )


def test_reject_stale_world_and_changed_source(db_service, tmp_path):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(batch(entities=[{"name": "Test", "type": "person"}])))
    review = prepare_import(
        db_service, load_sources([{"path": str(path)}]), {"mode": "skip"}
    )
    path.write_text("{}")
    assert not ApplyTransferCommand(review).execute(db_service).success
    review["source_hashes"] = {}
    db_service.insert_entity(Entity(name="Other", type="person"))
    assert not ApplyTransferCommand(review).execute(db_service).success
    assert len(db_service.get_all_entities()) == 1


def test_bad_late_row_and_invalid_date_leave_database_unchanged(db_service):
    before = snapshot(db_service.get_connection())
    review = prepare_import(
        db_service,
        batch(
            entities=[
                {"name": "Good", "type": "person"},
                {"name": "", "type": "person"},
            ],
            events=[{"name": "Bad date", "lore_date": "nonsense"}],
        ),
        {"mode": "skip"},
    )
    assert review["errors"]
    assert snapshot(db_service.get_connection()) == before


def test_complete_date_range_is_reviewed_and_imported(db_service):
    parser = DateParser(CalendarConfig.create_default())
    expected_start = parser.calculate_timestamp(parser.parse_date("23 AUG 1895"))
    review = prepare_import(
        db_service,
        batch(
            events=[
                {
                    "id": "complete-range",
                    "name": "Complete Date Range",
                    "lore_date": "23 AUG 1895 - 30 AUG 1895",
                    "type": "outbreak",
                }
            ]
        ),
        {"mode": "skip"},
    )

    assert not review["errors"]
    assert ApplyTransferCommand(review).execute(db_service).success
    imported_event = db_service.get_event("complete-range")
    assert imported_event is not None
    assert imported_event.lore_date == expected_start
    assert imported_event.lore_duration == 7.0


def test_numeric_csv_date_and_multiline_tags_round_trip(db_service, tmp_path):
    rows = [
        {
            "id": "event",
            "name": "Évent, one",
            "type": "generic",
            "lore_date": 2.5,
            "description": "first\nsecond",
            "attributes": {"_tags": ["a,b"], "custom": 7},
        }
    ]
    path = tmp_path / "events.csv"
    path.write_text(csv_text("events", rows), encoding="utf-8-sig")
    data = load_sources([{"path": str(path), "kind": "events"}])
    review = prepare_import(db_service, data, {"mode": "skip"})
    assert not review["errors"]
    assert ApplyTransferCommand(review).execute(db_service).success
    event = db_service.get_event("event")
    assert event.lore_date == 2.5
    assert event.description == "first\nsecond"
    assert event.tags == ["a,b"]
    assert event.attributes["custom"] == 7


def test_mixed_batch_retains_all_files_and_markdown_title(tmp_path):
    one = tmp_path / "one.json"
    two = tmp_path / "two.json"
    md = tmp_path / "Fallback title.md"
    one.write_text(json.dumps(batch(entities=[{"name": "One", "type": "person"}])))
    two.write_text(json.dumps(batch(entities=[{"name": "Two", "type": "person"}])))
    md.write_text("Narrative only.")
    data = load_sources([{"path": str(p)} for p in (one, two, md)])
    assert {r["name"] for r in data["entities"]} == {"One", "Two", "Fallback title"}
    assert len(data["source_hashes"]) == 3


@pytest.mark.parametrize(
    "text", ["[]", '{"palette": []}', '{"exchange_version": 99, "entities": []}']
)
def test_reject_unrelated_json(text):
    with pytest.raises(ValueError):
        parse_json(text)


def test_complete_paste_example_is_directly_importable(db_service):
    review = prepare_import(
        db_service, parse_json(LORE_JSON_EXAMPLE_TEXT), {"mode": "skip"}
    )

    assert not review["errors"]
    assert ApplyTransferCommand(review).execute(db_service).success
    assert len(db_service.get_all_entities()) == 1
    assert len(db_service.get_events()) == 1
    assert len(db_service.get_all_relations()) == 1


def test_staging_preserves_existing_output_on_failure(tmp_path):
    path = tmp_path / "output.json"
    path.write_text("original")
    with pytest.raises(RuntimeError), staged_output(path) as stage:
        stage.write_text("partial")
        raise RuntimeError("failed")
    assert path.read_text() == "original"


def test_world_package_roundtrip_and_duplicate_folder(db_service, tmp_path):
    root = tmp_path / "source"
    (root / "assets").mkdir(parents=True)
    (root / "assets" / "image.png").write_bytes(b"image")
    db_service.insert_entity(Entity(id="entity", name="Entity", type="person"))
    world = {
        "path": str(root),
        "manifest": {
            "id": "original",
            "name": "World",
            "storage_mode": "external_database",
            "db_filename": "C:/external/world.kraken",
        },
    }
    path = tmp_path / "world.krakenworld"
    export_world(db_service.get_connection(), world, path, lambda: False)
    assert inspect_package(path)["manifest"]["storage_mode"] == "self_contained"
    new = import_world(path, tmp_path / "worlds", "New World", lambda: False)
    assert json.loads((new / "world.json").read_text())["id"] != "original"
    assert (new / "assets" / "image.png").read_bytes() == b"image"
    with sqlite3.connect(new / "world.kraken") as database:
        assert database.execute("SELECT id FROM entities").fetchone()[0] == "entity"
    with pytest.raises(ValueError, match="already exists"):
        import_world(path, tmp_path / "worlds", "New World", lambda: False)


def test_package_rejects_traversal(tmp_path):
    path = tmp_path / "bad.krakenworld"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("../outside", "bad")
    with pytest.raises(ValueError, match="Unsafe"):
        inspect_package(path)
    assert not (tmp_path / "outside").exists()


def test_docx_and_pdf_publish_shared_content(qapp, tmp_path):
    sequence = [
        {
            "id": "one",
            "name": "Chapter É",
            "meta": {},
            "heading_level": 1,
            "content": (
                "A **bold** paragraph.\n\n| One | Two |\n|---|---|\n"
                "| A | B |\n\n[[Chapter É]]"
            ),
        }
    ]
    doc = document_snapshot(
        sequence, {"title": "Book", "contents": True}, str(tmp_path)
    )
    docx = tmp_path / "book.docx"
    pdf = tmp_path / "book.pdf"
    write_docx(doc, docx)
    write_pdf(doc, pdf)
    with zipfile.ZipFile(docx) as archive:
        xml = archive.read("word/document.xml").decode()
        assert "Chapter É" in xml and "w:tbl" in xml and "w:hyperlink" in xml
    assert pdf.read_bytes().startswith(b"%PDF")
    assert len(pdf.read_bytes()) > 1000


def test_export_selection_reports_omitted_relationships(db_service):
    db_service.insert_entity(
        Entity(id="00000000-0000-4000-8000-000000000004", name="A", type="person")
    )
    db_service.insert_entity(
        Entity(id="00000000-0000-4000-8000-000000000005", name="B", type="person")
    )
    db_service.insert_relation(
        "00000000-0000-4000-8000-000000000004",
        "00000000-0000-4000-8000-000000000005",
        "knows",
    )
    worker = TransferWorker(lambda: db_service)
    result = worker._run(
        {
            "operation": "prepare_export",
            "db_path": db_service.db_path,
            "format": "json",
            "scope": "selected",
            "selected": ["00000000-0000-4000-8000-000000000004"],
        }
    )
    assert len(result["data"]["entities"]) == 1
    assert result["data"]["relations"] == []
    assert result["warnings"]
