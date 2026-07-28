"""Regression coverage for canonical, reconciled wikilink relations."""

from src.commands.wiki_commands import ProcessWikiLinksCommand
from src.core.entities import Entity


def _insert_pair(db_service):
    source = Entity(name="Landfall", type="Place")
    target = Entity(name="Foggenburg", type="Place")
    db_service.insert_entity(source)
    db_service.insert_entity(target)
    return source, target


def test_multiple_occurrences_create_one_canonical_relation(db_service):
    source, target = _insert_pair(db_service)
    text = (
        f"[[id:{target.id}|Foggenburg]] borders "
        f"[[id:{target.id}|the old city]]."
    )

    result = ProcessWikiLinksCommand(source.id, text).execute(db_service)

    assert result.success is True
    relations = db_service.get_relations(source.id)
    assert len(relations) == 1
    assert relations[0]["target_id"] == target.id
    assert relations[0]["target_id"] != f"id:{target.id}"
    assert relations[0]["attributes"]["is_auto_generated"] is True
    assert relations[0]["attributes"]["generator"] == "wikilink"
    occurrences = relations[0]["attributes"]["occurrences"]
    assert len(occurrences) == 2
    assert {item["field"] for item in occurrences} == {"description"}


def test_reconcile_updates_retained_relation_and_removes_stale_target(db_service):
    source = Entity(name="Landfall", type="Place")
    retained = Entity(name="Foggenburg", type="Place")
    stale = Entity(name="Old Harbour", type="Place")
    for entity in (source, retained, stale):
        db_service.insert_entity(entity)

    first_text = (
        f"[[id:{retained.id}|Foggenburg]] and "
        f"[[id:{stale.id}|Old Harbour]]."
    )
    first = ProcessWikiLinksCommand(source.id, first_text)
    assert first.execute(db_service).success is True
    first_relations = db_service.get_relations(source.id)
    retained_id = next(
        relation["id"]
        for relation in first_relations
        if relation["target_id"] == retained.id
    )

    moved_text = f"A sentence inserted first. [[id:{retained.id}|Foggenburg]]."
    second = ProcessWikiLinksCommand(source.id, moved_text)
    result = second.execute(db_service)

    assert result.success is True
    relations = db_service.get_relations(source.id)
    assert len(relations) == 1
    assert relations[0]["id"] == retained_id
    assert relations[0]["target_id"] == retained.id
    assert relations[0]["attributes"]["occurrences"][0]["start_offset"] == 27
    assert result.data["updated_count"] == 1
    assert result.data["deleted_count"] == 1


def test_empty_text_removes_reconciled_mentions(db_service):
    source, target = _insert_pair(db_service)
    command = ProcessWikiLinksCommand(
        source.id,
        f"[[id:{target.id}|Foggenburg]]",
    )
    assert command.execute(db_service).success is True

    result = ProcessWikiLinksCommand(source.id, "").execute(db_service)

    assert result.success is True
    assert db_service.get_relations(source.id) == []
    assert result.data["deleted_count"] == 1


def test_undo_restores_exact_previous_mentions(db_service):
    source, target = _insert_pair(db_service)
    first = ProcessWikiLinksCommand(
        source.id,
        f"First [[id:{target.id}|Foggenburg]].",
    )
    assert first.execute(db_service).success is True
    before = db_service.get_relations(source.id)

    second = ProcessWikiLinksCommand(
        source.id,
        f"Moved later in the text: [[id:{target.id}|Foggenburg]].",
    )
    assert second.execute(db_service).success is True
    assert db_service.get_relations(source.id) != before

    second.undo(db_service)

    assert db_service.get_relations(source.id) == before
