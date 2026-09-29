"""Prepare isolated authoring scenarios from the tracked portable world."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from src.core.calendar import CalendarConverter
from src.core.date_parser import DateParser
from src.core.entities import Entity
from src.core.events import Event
from src.performance.models import PROFILES
from src.services.db_service import DatabaseService
from src.services.world_transfer import import_world, inspect_package
from tests.ux.catalog import TASK_BY_ID

ARCHIVE = Path(__file__).resolve().parents[2] / "Rhine_Tribunal_UX_Benchmark_v1.krakenworld"
SCENARIO_VERSION = "1.0"
_NAMESPACE = uuid.UUID("f7412e83-a86c-4b86-bc9f-cb7e89f1c758")
_STAMP = 1_790_661_600.0


def stable_id(task_id: str, kind: str, name: str) -> str:
    """Return a stable scenario-only UUID."""
    return str(uuid.uuid5(_NAMESPACE, f"{task_id}:{kind}:{name}"))


def archive_provenance() -> dict[str, Any]:
    """Read the immutable package's identity and validity."""
    info = inspect_package(ARCHIVE)
    return {
        "path": ARCHIVE.name,
        "sha256": hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
        "package_version": 1,
        "manifest": info["manifest"],
        "files": info["files"],
        "bytes": info["bytes"],
    }


def _ensure_entity(db: DatabaseService, task_id: str, name: str, kind: str) -> Entity:
    existing = next((item for item in db.get_all_entities() if item.name == name), None)
    if existing is not None:
        return existing
    entity = Entity(
        id=stable_id(task_id, "entity", name),
        name=name,
        type=kind,
        created_at=_STAMP,
        modified_at=_STAMP,
    )
    db.insert_entity(entity)
    return entity


def _ensure_year_event(
    db: DatabaseService, task_id: str, name: str, year: int = 961
) -> Event:
    existing = next((item for item in db.get_all_events() if item.name == name), None)
    if existing is not None:
        return existing
    config = db.get_active_calendar_config()
    if config is None:
        raise ValueError("Benchmark archive has no active calendar")
    expression = DateParser(config).parse_expression(str(year))
    event = Event(
        id=stable_id(task_id, "event", name),
        name=name,
        lore_date=expression.representative_time(CalendarConverter(config)),
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
        created_at=_STAMP,
        modified_at=_STAMP,
    )
    db.insert_event(event)
    return event


def _link(
    db: DatabaseService,
    task_id: str,
    source_id: str,
    target_id: str,
    rel_type: str,
    attributes: dict[str, Any] | None = None,
) -> None:
    connection = db.get_connection()
    if connection is None:
        raise RuntimeError("Benchmark database is disconnected")
    connection.execute(
        "INSERT INTO relations (id,source_id,target_id,rel_type,attributes,created_at) "
        "VALUES (?,?,?,?,?,?)",
        (
            stable_id(task_id, "relation", f"{source_id}:{target_id}:{rel_type}"),
            source_id,
            target_id,
            rel_type,
            json.dumps(attributes or {}, sort_keys=True),
            _STAMP,
        ),
    )
    connection.commit()


def _before(first: Event, second: Event, gap: float = 0.0) -> dict[str, Any]:
    return {
        "anchor_a": first.temporal_anchor_id,
        "relation": "before",
        "anchor_b": second.temporal_anchor_id,
        "min_offset_days": gap,
    }


def _seed_common(db: DatabaseService, task_id: str) -> None:  # noqa: C901
    person_tasks = {
        "KA-02", "KA-05", "KA-06", "KA-07", "KA-08", "KA-12", "KA-14",
        "KA-15", "KA-19", "KB-08", "KC-03", "KC-07", "KC-08",
    }
    house_tasks = {"KA-05", "KA-07", "KA-16"}
    durenmar_tasks = {"KA-05", "KA-08", "KA-18", "KA-19"}
    execution_tasks = {"KA-10", "KA-11", "KA-12", "KA-13", "KA-14", "KA-15", "KA-20"}
    succession_tasks = {"KA-11", "KA-12", "KA-13", "KA-14", "KA-15", "KA-20"}

    if task_id in person_tasks:
        _ensure_entity(db, task_id, "Tasgillia", "Character")
    if task_id in house_tasks:
        _ensure_entity(db, task_id, "House Tytalus", "Faction")
    if task_id in durenmar_tasks:
        _ensure_entity(db, task_id, "Durenmar", "Location")
    if task_id in {"KA-13", "KA-14", "KA-15"}:
        _ensure_entity(db, task_id, "Successor of Tasgillia", "Character")
    if task_id == "KA-17":
        kalliste = _ensure_entity(db, task_id, "Kalliste", "Character")
        event = _ensure_year_event(db, task_id, "Kalliste appointed", 962)
        _link(
            db, task_id, event.id, kalliste.id, "involved",
            {"valid_from_event": True, "payload": {"attributes": {"office": "Quaestor"}}},
        )
    if task_id in execution_tasks:
        _ensure_year_event(db, task_id, "Execution of Tasgillia")
    if task_id in succession_tasks:
        _ensure_year_event(db, task_id, "Succession")
    if task_id in {"KA-14", "KA-15"}:
        successor = _ensure_entity(db, task_id, "Successor of Tasgillia", "Character")
        succession = _ensure_year_event(db, task_id, "Succession")
        _link(
            db, task_id, succession.id, successor.id, "involved",
            {"valid_from_event": True, "payload": {"attributes": {"office": "Prima"}}},
        )
    if task_id == "KA-18":
        _ensure_entity(db, task_id, "Fengheld", "Location")


def _seed_advanced(db: DatabaseService, task_id: str) -> None:
    if task_id in {"KB-01", "KB-10"}:
        for name in ("First omen", "Second omen", "Third omen"):
            _ensure_year_event(db, task_id, name)
    if task_id in {"KB-02", "KB-03", "KB-04", "KB-05", "KB-06", "KB-09"}:
        _ensure_year_event(db, task_id, "First transition")
        _ensure_year_event(db, task_id, "Second transition")
    if task_id == "KB-08":
        person = _ensure_entity(db, task_id, "Tasgillia", "Character")
        first = _ensure_year_event(db, task_id, "First office change")
        second = _ensure_year_event(db, task_id, "Second office change")
        first.attributes["_temporal_v2"]["constraints"] = [_before(first, second)]
        db.insert_event(first)
        for event, value in ((first, "Quaestor"), (second, "Prima")):
            _link(
                db, task_id, event.id, person.id, "involved",
                {"valid_from_event": True, "payload": {"attributes": {"office": value}}},
            )
    if task_id == "KB-07":
        # The author creates the event; this scenario exposes a second calendar.
        config = db.get_active_calendar_config()
        if config is not None:
            config.id = stable_id(task_id, "calendar", "custom")
            config.name = "Tribunal Reckoning"
            config.is_active = True
            db.insert_calendar_config(config)
            db.set_active_calendar_config(config.id)


def _seed_stress(db: DatabaseService, task_id: str, world_path: Path) -> None:
    if task_id == "KC-03":
        _ensure_entity(db, task_id, "Tasgilía", "Character")
    elif task_id == "KC-04":
        connection = db.get_connection()
        if connection is None:
            raise RuntimeError("Benchmark database is disconnected")
        for index in range(128):
            name = f"Tribunal topic {index:03d}"
            connection.execute(
                "INSERT INTO tags (id,name,color,created_at) VALUES (?,?,?,?)",
                (stable_id(task_id, "tag", name), name, "#668899", _STAMP),
            )
        connection.commit()
        _ensure_entity(db, task_id, "Tag target", "Character")
    elif task_id == "KC-05":
        event = Event(
            id=stable_id(task_id, "event", "legacy"),
            name="Legacy exact hearing",
            lore_date=440000.0,
            created_at=_STAMP,
            modified_at=_STAMP,
        )
        db.insert_event(event)
    elif task_id == "KC-06":
        first = _ensure_year_event(db, task_id, "Imported first")
        second = _ensure_year_event(db, task_id, "Imported second")
        first.attributes["_temporal_v2"]["constraints"] = [
            _before(first, second), _before(second, first)
        ]
        db.insert_event(first)
    elif task_id == "KC-09":
        asset = world_path / "assets" / "maps" / "rhine_tribunal_benchmark.png"
        if not asset.is_file():
            raise FileNotFoundError(asset)
        asset.unlink()
    elif task_id == "KC-10":
        _ensure_entity(db, task_id, "Benchmark traveller", "Character")


def _augment_scale(world_path: Path, task_id: str) -> None:
    """Add deterministic rows while retaining all archive rows and map assets."""
    profile = PROFILES["standard" if task_id == "KC-01" else "relation-heavy"]
    database = world_path / "world.kraken"
    with sqlite3.connect(database) as connection:
        entity_ids = [stable_id(task_id, "bulk-entity", str(i)) for i in range(profile.entity_count)]
        event_ids = [stable_id(task_id, "bulk-event", str(i)) for i in range(profile.event_count)]
        connection.executemany(
            "INSERT INTO entities (id,type,name,description,attributes,created_at,modified_at) VALUES (?,?,?,?,?,?,?)",
            (
                (identity, "Character", f"Benchmark Person {index:05d}", "", "{}", _STAMP, _STAMP)
                for index, identity in enumerate(entity_ids)
            ),
        )
        connection.executemany(
            "INSERT INTO events (id,type,name,lore_date,lore_duration,description,attributes,created_at,modified_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                (identity, "generic", f"Benchmark Event {index:05d}", 430000.0 + index, 0.0, "", "{}", _STAMP, _STAMP)
                for index, identity in enumerate(event_ids)
            ),
        )
        connection.executemany(
            "INSERT INTO relations (id,source_id,target_id,rel_type,attributes,created_at) VALUES (?,?,?,?,?,?)",
            (
                (
                    stable_id(task_id, "bulk-relation", str(index)),
                    event_ids[index % len(event_ids)],
                    entity_ids[index % len(entity_ids)],
                    "involved",
                    "{}",
                    _STAMP,
                )
                for index in range(profile.relation_count)
            ),
        )


def logical_fingerprint(world_path: Path) -> str:
    """Hash sorted logical rows and packaged assets, excluding clone identity."""
    digest = hashlib.sha256()
    with sqlite3.connect(world_path / "world.kraken") as connection:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        for table in tables:
            digest.update(table.encode())
            columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
            order = '"id"' if "id" in columns else "rowid"
            for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY {order}'):
                digest.update(json.dumps(row, default=str, ensure_ascii=False).encode())
    for asset in sorted((world_path / "assets").rglob("*")):
        if asset.is_file():
            digest.update(asset.relative_to(world_path).as_posix().encode())
            digest.update(hashlib.sha256(asset.read_bytes()).digest())
    return digest.hexdigest()


def prepare_task(task_id: str, worlds_root: Path) -> dict[str, Any]:
    """Import an independent package copy and add only that task's prerequisites."""
    if task_id not in TASK_BY_ID:
        raise ValueError(f"Unknown UX task: {task_id}")
    world_path = import_world(ARCHIVE, worlds_root, f"UX {task_id}", lambda: False)
    db = DatabaseService(str(world_path / "world.kraken"))
    db.connect()
    try:
        if task_id.startswith("KA-"):
            _seed_common(db, task_id)
        elif task_id.startswith("KB-"):
            _seed_advanced(db, task_id)
        else:
            _seed_stress(db, task_id, world_path)
    finally:
        db.close()
    if task_id in {"KC-01", "KC-02"}:
        _augment_scale(world_path, task_id)
    return {
        "task_id": task_id,
        "world_path": str(world_path),
        "scenario_version": SCENARIO_VERSION,
        "fingerprint": logical_fingerprint(world_path),
    }
