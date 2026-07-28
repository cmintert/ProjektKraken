"""Regression tests for relation integrity and legacy wikilink cleanup."""

import json
import sqlite3
import time
import uuid

import pytest

from src.core.entities import Entity
from src.services.db_service import DatabaseService


def test_relation_insert_rejects_noncanonical_or_missing_endpoints(db_service):
    source = Entity(name="Source", type="Place")
    target = Entity(name="Target", type="Place")
    db_service.insert_entity(source)
    db_service.insert_entity(target)

    with pytest.raises(ValueError, match="canonical UUID"):
        db_service.insert_relation(source.id, f"id:{target.id}", "related")

    with pytest.raises(ValueError, match="does not exist"):
        db_service.insert_relation(
            source.id,
            str(uuid.uuid4()),
            "related",
        )


def test_database_rejects_duplicate_mentions_rows(db_service):
    source = Entity(name="Source", type="Place")
    target = Entity(name="Target", type="Place")
    db_service.insert_entity(source)
    db_service.insert_entity(target)
    attributes = {
        "is_auto_generated": True,
        "generator": "wikilink",
        "occurrences": [
            {
                "field": "description",
                "start_offset": 0,
                "end_offset": 10,
                "snippet": "[[Target]]",
            }
        ],
    }
    db_service._relation_repo.insert(
        str(uuid.uuid4()),
        source.id,
        target.id,
        "mentions",
        attributes,
        time.time(),
    )

    with pytest.raises(sqlite3.IntegrityError):
        db_service._relation_repo.insert(
            str(uuid.uuid4()),
            source.id,
            target.id,
            "mentions",
            attributes,
            time.time(),
        )


def test_legacy_world_relations_are_normalized_and_rebuilt(tmp_path):
    db_path = tmp_path / "legacy.kraken"
    source = Entity(name="Landfall", type="Place")
    target = Entity(name="Foggenburg", type="Place")
    stale = Entity(name="Old Harbour", type="Place")
    source.description = (
        f"[[id:{target.id}|Foggenburg]] borders "
        f"[[id:{target.id}|the old city]]."
    )

    initial = DatabaseService(str(db_path))
    initial.connect()
    for entity in (source, target, stale):
        initial.insert_entity(entity)
    initial.close()

    now = time.time()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "DELETE FROM system_meta "
            "WHERE key = 'wikilink_relations_schema_version'"
        )
        connection.execute("DROP INDEX IF EXISTS uq_mentions_src_tgt")
        for trigger_name in (
            "validate_relation_endpoints_insert",
            "validate_relation_endpoints_update",
            "validate_mentions_attributes_insert",
            "validate_mentions_attributes_update",
            "cleanup_entity_relations",
            "cleanup_event_relations",
        ):
            connection.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
        relation_rows = [
            (
                str(uuid.uuid4()),
                source.id,
                f"id:{target.id}",
                "mentions",
                "{}",
                now,
            ),
            (
                str(uuid.uuid4()),
                source.id,
                target.name,
                "mentions",
                "{}",
                now + 1,
            ),
            (
                str(uuid.uuid4()),
                source.id,
                target.id,
                "mentions",
                json.dumps(
                    {
                        "field": "description",
                        "start_offset": 0,
                        "end_offset": 10,
                        "snippet": "stale offset",
                        "is_auto_generated": True,
                    }
                ),
                now + 2,
            ),
            (
                str(uuid.uuid4()),
                source.id,
                stale.id,
                "mentions",
                json.dumps(
                    {
                        "field": "description",
                        "start_offset": 99,
                        "end_offset": 110,
                        "snippet": "removed link",
                        "is_auto_generated": True,
                    }
                ),
                now + 3,
            ),
            (
                str(uuid.uuid4()),
                source.id,
                "Missing Place",
                "related",
                "{}",
                now + 4,
            ),
            (
                str(uuid.uuid4()),
                source.id,
                target.id,
                "ally",
                json.dumps({"weight": 1}),
                now + 5,
            ),
            (
                str(uuid.uuid4()),
                source.id,
                target.id,
                "ally",
                json.dumps({"weight": 1}),
                now + 6,
            ),
        ]
        connection.executemany(
            """
            INSERT INTO relations (
                id, source_id, target_id, rel_type, attributes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            relation_rows,
        )
        connection.execute(
            """
            INSERT INTO command_history (
                world_id, session_id, command_type, command_data,
                description, timestamp, is_executed
            )
            VALUES ('world', 'session', 'AddRelationCommand', '{}',
                    'legacy history', ?, 1)
            """,
            (now,),
        )
        connection.execute(
            """
            INSERT INTO edit_sessions (session_id, world_id, started_at)
            VALUES ('session', 'world', ?)
            """,
            (now,),
        )

    artifact = db_path.parent / "assets" / ".history" / "legacy-command" / "file"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("obsolete undo artifact", encoding="utf-8")

    migrated = DatabaseService(str(db_path))
    migrated.connect()
    relations = migrated.get_relations(source.id)

    mentions = [row for row in relations if row["rel_type"] == "mentions"]
    assert len(mentions) == 1
    assert mentions[0]["target_id"] == target.id
    assert len(mentions[0]["attributes"]["occurrences"]) == 2
    assert all(
        not row["target_id"].startswith("id:") for row in migrated.get_all_relations()
    )
    assert all(
        row["target_id"] != "Missing Place" for row in migrated.get_all_relations()
    )
    assert len([row for row in relations if row["rel_type"] == "ally"]) == 1

    connection = migrated.get_connection()
    assert connection is not None
    assert connection.execute("SELECT COUNT(*) FROM command_history").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM edit_sessions").fetchone()[0] == 0
    assert not (db_path.parent / "assets" / ".history").exists()
    assert (
        connection.execute(
            "SELECT value FROM system_meta "
            "WHERE key = 'wikilink_relations_schema_version'"
        ).fetchone()[0]
        == "2"
    )
    indexes = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        ).fetchall()
    }
    assert "uq_mentions_src_tgt" in indexes
    assert "uq_mentions_src_tgt_offset" not in indexes
    migrated.close()
