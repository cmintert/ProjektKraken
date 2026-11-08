"""Disposable facts and protocol cases for source or packaged MCP acceptance."""

import uuid
from pathlib import Path
from typing import Any

from PIL import Image

from src.core.calendar import CalendarConfig, LeapYearRule, MonthDefinition, YearVariant
from src.core.entities import Entity
from src.core.events import Event
from src.core.image_attachment import ImageAttachment
from src.core.map import Map
from src.services.db_service import DatabaseService

WORLD_NOW = 120.0
PLAYHEAD = 110.0


def seed(path: Path) -> dict[str, str]:
    """Create known facts before the queued-worker host takes ownership."""
    if path.exists():
        raise ValueError("Verification requires a fresh database path")
    assets = path.parent / "assets"
    assets.mkdir(exist_ok=True)
    Image.new("RGB", (48, 32), (30, 60, 90)).save(assets / "fixture.png")
    db = DatabaseService(str(path))
    db.connect()
    try:
        calendar = CalendarConfig.create_default()
        calendar.is_active = True
        calendar.leap_year_rules = [LeapYearRule(4, 100, 400, 1, 1)]
        calendar.year_variants = [
            YearVariant(2, [MonthDefinition("Festival", "F", 12)])
        ]
        db.insert_calendar_config(calendar)
        db.set_current_time(WORLD_NOW)
        entity = Entity(
            "Ilyra",
            "person",
            "Complete saved prose.\n" * 4000,
            attributes={"rank": "citizen", "_longform": {"default": {"position": 1}}},
        )
        event = Event("Coronation", 100)
        db.insert_entity(entity)
        db.insert_event(event)
        preceding = Event("Accession", 99)
        db.insert_event(preceding)
        event_relation = db.insert_relation(preceding.id, event.id, "precedes", {})
        relation = db.insert_relation(
            event.id,
            entity.id,
            "changes",
            {
                "valid_from": 100,
                "payload": {
                    "description": "Crowned ruler",
                    "attributes": {"rank": "queen"},
                },
            },
        )
        item = Map(
            "Northwatch map", "assets/fixture.png", description="Saved map notes"
        )
        db.insert_map(item)
        attachment = ImageAttachment(
            str(uuid.uuid4()),
            "entity",
            entity.id,
            "assets/fixture.png",
            caption="Ruler portrait",
        )
        db.get_attachment_repo().insert(attachment)
        return {
            "entity_id": entity.id,
            "event_id": event.id,
            "relation_id": relation,
            "map_id": item.id,
            "attachment_id": attachment.id,
            "description": entity.description,
            "calendar_id": calendar.id,
            "event_relation_id": event_relation,
        }
    finally:
        db.close()


def cases(facts: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Exercise every tool, with real saved facts instead of transport stubs."""
    return {
        "list_calendars": {},
        "read_calendar_section": {
            "calendar_id": facts["calendar_id"],
            "section": "leap_year_rules",
        },
        "get_time_context": {},
        "browse_relationships": {},
        "get_active_world": {},
        "get_world_overview": {},
        "get_capabilities": {},
        "search_world": {"query": "Coronation", "ranking": "relevance"},
        "browse_world": {"kinds": ["event"]},
        "get_object": {"kind": "event", "id": facts["event_id"]},
        "get_objects": {
            "objects": [
                {"kind": "event", "id": facts["event_id"]},
                {"kind": "entity", "id": "missing"},
            ],
            "detail": "compact",
        },
        "get_context": {
            "kind": "entity",
            "id": facts["entity_id"],
            "mode": "at_playhead",
            "lore_day": 110,
        },
        "list_connections": {"entity_id": facts["entity_id"], "mode": "all_history"},
        "get_object_summary": {"kind": "entity", "id": facts["entity_id"]},
        "read_object_section": {
            "kind": "entity",
            "id": facts["entity_id"],
            "section": "description",
        },
        "read_context_section": {
            "kind": "entity",
            "id": facts["entity_id"],
            "mode": "at_playhead",
            "lore_day": 110,
            "section": "attributes",
        },
        "browse_facets": {"category": "types"},
        "read_longform": {},
        "browse_maps": {},
        "read_map": {"map_id": facts["map_id"], "section": "metadata"},
        "list_attachments": {"kind": "entity", "id": facts["entity_id"]},
        "get_image_preview": {"source_kind": "map", "source_id": facts["map_id"]},
        "semantic_search": {"query": "Coronation"},
        "search_shared_content": {"query": "Ruler"},
    }
