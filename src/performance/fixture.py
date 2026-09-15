"""Deterministic, disposable large-world fixture generation."""

from __future__ import annotations

import json
import random
import sqlite3
import time
import uuid
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from src.core.world import World, WorldManifest
from src.performance.models import FixtureProfile
from src.services.db_service import DatabaseService

_FIXTURE_NAMESPACE = uuid.UUID("c9b79935-3334-4a39-8c2a-f4d1af81b4a8")
_BATCH_SIZE = 5_000


def _stable_id(seed: int, kind: str, index: int) -> str:
    return str(uuid.uuid5(_FIXTURE_NAMESPACE, f"{seed}:{kind}:{index}"))


def _batches(rows: Iterable[tuple[Any, ...]]) -> Iterator[list[tuple[Any, ...]]]:
    batch: list[tuple[Any, ...]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= _BATCH_SIZE:
            yield batch
            batch = []
    if batch:
        yield batch


def _insert_batches(
    connection: sqlite3.Connection, sql: str, rows: Iterable[tuple[Any, ...]]
) -> None:
    for batch in _batches(rows):
        connection.executemany(sql, batch)


def generate_fixture(
    world_root: Path, profile: FixtureProfile, seed: int
) -> dict[str, Any]:
    """Generate one isolated portable world and return its manifest evidence."""
    started = time.perf_counter()
    world_root.mkdir(parents=True, exist_ok=False)
    world_name = f"Performance {profile.name}"
    database_name = "measurement.kraken"
    world = World(
        path=world_root,
        manifest=WorldManifest(
            id=_stable_id(seed, "world", 0),
            name=world_name,
            description="Disposable measurement-only fixture.",
            created_at=1_700_000_000.0,
            modified_at=1_700_000_000.0,
            db_filename=database_name,
        ),
    )
    world.ensure_structure()
    database = world.db_path

    service = DatabaseService(str(database))
    service.connect()
    service.close()

    rng = random.Random(seed)
    now = 1_700_000_000.0
    content = "x" * profile.description_size
    event_ids = [_stable_id(seed, "event", i) for i in range(profile.event_count)]
    entity_ids = [
        _stable_id(seed, "entity", i) for i in range(profile.entity_count)
    ]
    all_ids = entity_ids + event_ids
    tag_ids = [_stable_id(seed, "tag", i) for i in range(profile.tag_count)]

    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA foreign_keys=ON")
        with connection:
            _insert_batches(
                connection,
                """
                INSERT INTO events
                    (id, type, name, lore_date, lore_duration, description,
                     attributes, created_at, modified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        event_id,
                        ("battle", "discovery", "political", "personal")[i % 4],
                        f"Event {i:05d}",
                        float(rng.randrange(100))
                        if profile.dense_dates
                        else float(i * 3 + rng.random()),
                        float(i % 12),
                        content,
                        json.dumps(
                            {
                                "importance": i % 5,
                                "region": f"region-{i % 32}",
                                "_tags": [f"tag-{i % profile.tag_count:03d}"],
                            },
                            separators=(",", ":"),
                        ),
                        now + i,
                        now + i,
                    )
                    for i, event_id in enumerate(event_ids)
                ),
            )
            _insert_batches(
                connection,
                """
                INSERT INTO entities
                    (id, type, name, description, attributes, created_at, modified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        entity_id,
                        ("character", "location", "faction", "artifact")[i % 4],
                        f"Entity {i:05d}",
                        content,
                        json.dumps(
                            {
                                "status": ("active", "historic")[i % 2],
                                "region": f"region-{i % 32}",
                                "_tags": [f"tag-{i % profile.tag_count:03d}"],
                            },
                            separators=(",", ":"),
                        ),
                        now + i,
                        now + i,
                    )
                    for i, entity_id in enumerate(entity_ids)
                ),
            )
            connection.executemany(
                "INSERT INTO tags (id, name, color, created_at) VALUES (?, ?, ?, ?)",
                [
                    (tag_id, f"tag-{i:03d}", f"#{i % 256:02x}6688", now)
                    for i, tag_id in enumerate(tag_ids)
                ],
            )
            _insert_batches(
                connection,
                "INSERT INTO event_tags (event_id, tag_id, created_at) VALUES (?, ?, ?)",
                (
                    (event_id, tag_ids[i % profile.tag_count], now)
                    for i, event_id in enumerate(event_ids)
                ),
            )
            _insert_batches(
                connection,
                "INSERT INTO entity_tags (entity_id, tag_id, created_at) VALUES (?, ?, ?)",
                (
                    (entity_id, tag_ids[i % profile.tag_count], now)
                    for i, entity_id in enumerate(entity_ids)
                ),
            )
            relation_types = ("involved", "located_in", "caused", "member_of")
            _insert_batches(
                connection,
                """
                INSERT INTO relations
                    (id, source_id, target_id, rel_type, attributes, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        _stable_id(seed, "relation", i),
                        all_ids[rng.randrange(len(all_ids))],
                        all_ids[rng.randrange(len(all_ids))],
                        relation_types[i % len(relation_types)],
                        '{"weight":1.0}',
                        now + i,
                    )
                    for i in range(profile.relation_count)
                ),
            )
            if profile.marker_count:
                _insert_temporal_map(
                    connection, profile, seed, entity_ids, now
                )
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        connection.close()

    return {
        "profile": profile.to_dict(),
        "seed": seed,
        "world_id": world.id,
        "world_path": str(world_root.resolve()),
        "database_path": str(database.resolve()),
        "database_size_bytes": database.stat().st_size,
        "generation_ms": (time.perf_counter() - started) * 1000.0,
    }


def _insert_temporal_map(
    connection: sqlite3.Connection,
    profile: FixtureProfile,
    seed: int,
    entity_ids: list[str],
    now: float,
) -> None:
    map_id = _stable_id(seed, "map", 0)
    connection.execute(
        """
        INSERT INTO maps
            (id, name, image_path, description, attributes, created_at, modified_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (map_id, "Measurement Map", "", "", "{}", now, now),
    )
    marker_ids = [_stable_id(seed, "marker", i) for i in range(profile.marker_count)]
    base_geometry = json.dumps(
        {"type": "LineString", "coordinates": [[0.1, 0.1], [0.9, 0.9]]},
        separators=(",", ":"),
    )
    _insert_batches(
        connection,
        """
        INSERT INTO markers
            (id, map_id, object_id, object_type, x, y, label, attributes,
             created_at, modified_at, feature_type, geometry, style)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                marker_id,
                map_id,
                entity_ids[i],
                "entity",
                (i % 100) / 100.0,
                ((i // 100) % 100) / 100.0,
                f"Marker {i}",
                "{}",
                now,
                now,
                "path" if i < profile.geometry_state_count else "point",
                base_geometry if i < profile.geometry_state_count else None,
                "{}",
            )
            for i, marker_id in enumerate(marker_ids)
        ),
    )
    trajectory_json = json.dumps(
        {
            "type": "MovingPoint",
            "coordinates": [[0.1, 0.1], [0.9, 0.9]],
            "datetimes": [0.0, 30_000.0],
        },
        separators=(",", ":"),
    )
    _insert_batches(
        connection,
        """
        INSERT INTO moving_features
            (id, marker_id, t_start, t_end, trajectory, properties, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                _stable_id(seed, "trajectory", i),
                marker_ids[i],
                0.0,
                30_000.0,
                trajectory_json,
                json.dumps(
                    {
                        "kraken_trajectory": {
                            "schema_version": 2,
                            "points": [
                                {
                                    "id": _stable_id(seed, f"trajectory-{i}-point", 0),
                                    "kind": "timed",
                                },
                                {
                                    "id": _stable_id(seed, f"trajectory-{i}-point", 1),
                                    "kind": "timed",
                                },
                            ],
                            "legs": [
                                {
                                    "from_id": _stable_id(
                                        seed, f"trajectory-{i}-point", 0
                                    ),
                                    "to_id": _stable_id(
                                        seed, f"trajectory-{i}-point", 1
                                    ),
                                    "mode": "linear",
                                    "timing": "distance",
                                }
                            ],
                        }
                    },
                    separators=(",", ":"),
                ),
                now,
            )
            for i in range(profile.moving_marker_count)
        ),
    )
    _insert_batches(
        connection,
        """
        INSERT INTO feature_geometry_states
            (id, marker_id, effective_date, geometry, anchor_x, anchor_y,
             created_at, modified_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                _stable_id(seed, "geometry-state", i),
                marker_ids[i],
                10_000.0,
                base_geometry,
                0.5,
                0.5,
                now,
                now,
            )
            for i in range(profile.geometry_state_count)
        ),
    )
