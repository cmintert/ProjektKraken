"""Canonical relation migration; the runner owns transactions and recovery."""

import json
import logging
import sqlite3
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional

from src.services.migrations.errors import MigrationError
from src.services.text_parser import WikiLinkParser

logger = logging.getLogger(__name__)


def install_relation_integrity(conn: sqlite3.Connection) -> None:
    """Install indexes and triggers that protect relation invariants."""
    conn.execute("DROP INDEX IF EXISTS uq_mentions_src_tgt_offset")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mentions_src_tgt
        ON relations(source_id, target_id)
        WHERE rel_type = 'mentions'
        """
    )

    trigger_names = (
        "validate_relation_endpoints_insert",
        "validate_relation_endpoints_update",
        "validate_mentions_attributes_insert",
        "validate_mentions_attributes_update",
        "cleanup_entity_relations",
        "cleanup_event_relations",
    )
    for trigger_name in trigger_names:
        conn.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")

    conn.execute(
        """
        CREATE TRIGGER validate_relation_endpoints_insert
        BEFORE INSERT ON relations
        WHEN (
            NOT EXISTS (SELECT 1 FROM entities WHERE id = NEW.source_id)
            AND NOT EXISTS (SELECT 1 FROM events WHERE id = NEW.source_id)
        ) OR (
            NOT EXISTS (SELECT 1 FROM entities WHERE id = NEW.target_id)
            AND NOT EXISTS (SELECT 1 FROM events WHERE id = NEW.target_id)
        )
        BEGIN
            SELECT RAISE(ABORT, 'relation endpoint does not exist');
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER validate_relation_endpoints_update
        BEFORE UPDATE OF source_id, target_id ON relations
        WHEN (
            NOT EXISTS (SELECT 1 FROM entities WHERE id = NEW.source_id)
            AND NOT EXISTS (SELECT 1 FROM events WHERE id = NEW.source_id)
        ) OR (
            NOT EXISTS (SELECT 1 FROM entities WHERE id = NEW.target_id)
            AND NOT EXISTS (SELECT 1 FROM events WHERE id = NEW.target_id)
        )
        BEGIN
            SELECT RAISE(ABORT, 'relation endpoint does not exist');
        END
        """
    )
    mentions_validation = """
        CASE
            WHEN json_valid(NEW.attributes) = 0 THEN 1
            WHEN json_extract(
                NEW.attributes, '$.is_auto_generated'
            ) IS NOT 1 THEN 1
            WHEN json_extract(
                NEW.attributes, '$.generator'
            ) != 'wikilink' THEN 1
            WHEN json_type(
                NEW.attributes, '$.occurrences'
            ) != 'array' THEN 1
            ELSE 0
        END
    """
    conn.execute(
        f"""
        CREATE TRIGGER validate_mentions_attributes_insert
        BEFORE INSERT ON relations
        WHEN NEW.rel_type = 'mentions' AND ({mentions_validation}) = 1
        BEGIN
            SELECT RAISE(ABORT, 'invalid generated mentions attributes');
        END
        """
    )
    conn.execute(
        f"""
        CREATE TRIGGER validate_mentions_attributes_update
        BEFORE UPDATE OF rel_type, attributes ON relations
        WHEN NEW.rel_type = 'mentions' AND ({mentions_validation}) = 1
        BEGIN
            SELECT RAISE(ABORT, 'invalid generated mentions attributes');
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER cleanup_entity_relations
        AFTER DELETE ON entities
        BEGIN
            DELETE FROM relations
            WHERE source_id = OLD.id OR target_id = OLD.id;
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER cleanup_event_relations
        AFTER DELETE ON events
        BEGIN
            DELETE FROM relations
            WHERE source_id = OLD.id OR target_id = OLD.id;
        END
        """
    )


def normalize_relations(conn: sqlite3.Connection) -> None:  # noqa: C901
    """Normalize legacy endpoints and rebuild derived mentions atomically."""
    logger.info("Applying migration: canonical wikilink relations v2")
    normalized_count = 0
    deleted_count = 0
    duplicate_count = 0
    rebuilt_count = 0
    history_count = 0

    conn.execute("DROP INDEX IF EXISTS uq_mentions_src_tgt_offset")
    conn.execute("DROP INDEX IF EXISTS uq_mentions_src_tgt")

    entity_rows = conn.execute(
        "SELECT id, name, description, attributes FROM entities"
    ).fetchall()
    event_rows = conn.execute("SELECT id, name, description FROM events").fetchall()
    valid_ids = {str(row["id"]) for row in [*entity_rows, *event_rows]}
    name_to_ids: Dict[str, set[str]] = defaultdict(set)
    for row in entity_rows:
        item_id = str(row["id"])
        name_to_ids[str(row["name"]).casefold()].add(item_id)
        try:
            attributes = json.loads(row["attributes"] or "{}")
        except (TypeError, json.JSONDecodeError) as exc:
            raise MigrationError(
                f"Malformed entity attributes: {item_id}", record_ids=[item_id]
            ) from exc
        if not isinstance(attributes, dict):
            raise MigrationError(
                f"Invalid entity attributes: {item_id}", record_ids=[item_id]
            )
        aliases = attributes.get("aliases", [])
        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str):
                    name_to_ids[alias.casefold()].add(item_id)
    for row in event_rows:
        name_to_ids[str(row["name"]).casefold()].add(str(row["id"]))

    def resolve_endpoint(raw_value: Any) -> Optional[str]:
        if not isinstance(raw_value, str):
            return None
        value = raw_value.strip()
        if value in valid_ids:
            return value
        if value.casefold().startswith("id:"):
            value = value[3:]
        try:
            canonical = str(uuid.UUID(value))
        except (ValueError, AttributeError):
            canonical = ""
        if canonical in valid_ids:
            return canonical
        matches = name_to_ids.get(raw_value.strip().casefold(), set())
        if len(matches) == 1:
            return next(iter(matches))
        if len(matches) > 1:
            raise MigrationError(
                f"Ambiguous relation endpoint: {raw_value}",
                record_ids=sorted(matches),
            )
        return None

    relation_rows = conn.execute(
        "SELECT rowid, * FROM relations ORDER BY created_at, rowid"
    ).fetchall()
    affected_sources: set[str] = set()
    for row in relation_rows:
        source_id = resolve_endpoint(row["source_id"])
        target_id = resolve_endpoint(row["target_id"])
        if source_id is None or target_id is None:
            conn.execute("DELETE FROM relations WHERE id = ?", (row["id"],))
            deleted_count += 1
            continue
        if row["rel_type"] == "mentions":
            affected_sources.add(source_id)
        if source_id != row["source_id"] or target_id != row["target_id"]:
            conn.execute(
                """
                UPDATE relations
                SET source_id = ?, target_id = ?
                WHERE id = ?
                """,
                (source_id, target_id, row["id"]),
            )
            normalized_count += 1

    seen_exact: set[tuple[str, str, str, str]] = set()
    relation_rows = conn.execute(
        """
        SELECT rowid, * FROM relations
        WHERE rel_type != 'mentions'
        ORDER BY created_at, rowid
        """
    ).fetchall()
    for row in relation_rows:
        raw_attributes = row["attributes"] or "{}"
        try:
            parsed_attributes = json.loads(raw_attributes)
            if not isinstance(parsed_attributes, dict):
                raise ValueError("Expected relation attributes object")
            canonical_attributes = json.dumps(
                parsed_attributes,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise MigrationError(
                f"Malformed relation attributes: {row['id']}",
                record_ids=[str(row["id"])],
            ) from exc
        key = (
            str(row["source_id"]),
            str(row["target_id"]),
            str(row["rel_type"]),
            canonical_attributes,
        )
        if key in seen_exact:
            conn.execute("DELETE FROM relations WHERE id = ?", (row["id"],))
            duplicate_count += 1
        else:
            seen_exact.add(key)

    descriptions = {
        str(row["id"]): str(row["description"] or "")
        for row in [*entity_rows, *event_rows]
    }
    for source_id in affected_sources:
        existing_mentions = conn.execute(
            """
            SELECT rowid, * FROM relations
            WHERE source_id = ? AND rel_type = 'mentions'
            ORDER BY created_at, rowid
            """,
            (source_id,),
        ).fetchall()
        survivor_by_target = {str(row["target_id"]): row for row in existing_mentions}
        desired: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        text_content = descriptions.get(source_id, "")
        for candidate in WikiLinkParser.extract_links(text_content):
            desired_target_id: Optional[str]
            if candidate.is_id_based:
                desired_target_id = resolve_endpoint(candidate.target_id)
            else:
                desired_target_id = resolve_endpoint(candidate.name)
            if desired_target_id is None or desired_target_id == source_id:
                continue
            desired[desired_target_id].append(
                {
                    "field": "description",
                    "start_offset": candidate.span[0],
                    "end_offset": candidate.span[1],
                    "snippet": WikiLinkParser.extract_snippet(
                        text_content,
                        candidate.span[0],
                        candidate.span[1],
                    ),
                }
            )

        conn.execute(
            """
            DELETE FROM relations
            WHERE source_id = ? AND rel_type = 'mentions'
            """,
            (source_id,),
        )
        for target_id, occurrences in desired.items():
            survivor = survivor_by_target.get(target_id)
            relation_id = (
                str(survivor["id"]) if survivor is not None else str(uuid.uuid4())
            )
            created_at = (
                float(survivor["created_at"]) if survivor is not None else time.time()
            )
            attributes = {
                "is_auto_generated": True,
                "generator": "wikilink",
                "occurrences": occurrences,
            }
            conn.execute(
                """
                INSERT INTO relations (
                    id, source_id, target_id, rel_type,
                    attributes, created_at
                )
                VALUES (?, ?, ?, 'mentions', ?, ?)
                """,
                (
                    relation_id,
                    source_id,
                    target_id,
                    json.dumps(attributes),
                    created_at,
                ),
            )
            rebuilt_count += 1

    history_count = conn.execute("SELECT COUNT(*) FROM command_history").fetchone()[0]
    conn.execute("DELETE FROM command_history")
    conn.execute("DELETE FROM edit_sessions")

    install_relation_integrity(conn)
    conn.execute(
        """
        INSERT INTO system_meta (key, value)
        VALUES ('wikilink_relations_schema_version', '2')
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """
    )

    logger.info(
        "Relation migration: normalized=%d, deleted=%d, duplicates=%d, "
        "rebuilt=%d, history_cleared=%d",
        normalized_count,
        deleted_count,
        duplicate_count,
        rebuilt_count,
        history_count,
    )
