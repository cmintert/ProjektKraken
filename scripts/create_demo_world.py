"""Create an isolated, portable Northwatch first-session sample world.

Run with ``python -m scripts.create_demo_world``. Existing worlds are never replaced.
This offline authoring tool owns its database connection; it is not a GUI mutation.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.entities import Entity
from src.core.events import Event
from src.core.feature_geometry_state import (
    FeatureGeometryState,
    calculate_feature_anchor,
)
from src.core.map import Map, MapLayerNode
from src.core.marker import Marker
from src.core.temporal_expression import (
    TEMPORAL_ATTRIBUTE,
    TemporalExpression,
    TemporalPrecision,
    TemporalQualifier,
)
from src.core.trajectory import Keyframe
from src.core.world import World, WorldManifest
from src.services.db_service import DatabaseService
from src.services.longform_builder import (
    export_longform_to_markdown,
    insert_or_update_longform_meta,
)
from src.services.world_validator import WorldValidator

logger = logging.getLogger(__name__)
WORLD_NAME = "Northwatch Demo (Illustrated)"
GUIDE = Path(__file__).resolve().parents[1] / "docs" / "ux" / "northwatch-demo.md"
MAP_ASSET = Path(__file__).resolve().parents[1] / "assets" / "demo" / "northwatch.png"
ARMY_ASSET = MAP_ASSET.with_name("army.png")
ARMY_ICON_HEX = "68da9295b3cb4c7b9cac3c39b5ca7fc7"
ARMY_ICON_ID = f"custom.{ARMY_ICON_HEX}"


def _populate(db: DatabaseService, world: World) -> None:
    """Write connected sample content through existing persistence APIs."""
    calendar = CalendarConfig.create_default()
    calendar.name = "Northwatch Calendar"
    calendar.epoch_name = "NS"
    db.insert_calendar_config(calendar)
    db.set_active_calendar_config(calendar.id)
    converter = CalendarConverter(calendar)
    before = converter.start_of_day(1, 1, 1)
    change = converter.start_of_day(1, 1, 10)
    after = converter.start_of_day(1, 1, 20)
    opening = Event(
        name="01 - The march begins",
        lore_date=before,
        type="Journey",
        description="Open the Northwatch map, then choose Show world at this event. "
        "The army starts at Ashford; Queen Mara still rules. Next open "
        "[[02 - The Northwatch succession]] and show the world there. "
        "Watch the border and army change before exploring the details.",
    )
    succession = Event(
        name="02 - The Northwatch succession",
        lore_date=change,
        type="Political",
        description="On 10 January, [[Captain Ilyra]] takes the crown from "
        "[[Queen Mara]]. The [[Ashford Army]] reaches [[Northwatch Keep]], "
        "and the [[Kingdom of Ashford]] extends its border to the eastern coast. "
        "Choose Show world at this event, then inspect the kingdom's Ruler "
        "and the keep's description at this date.",
    )
    settled = Event(
        name="04 - The new kingdom",
        lore_date=after,
        type="Political",
        description="The succession is complete. [[Captain Ilyra]] rules the "
        "expanded [[Kingdom of Ashford]]. The army remains at Northwatch. "
        "Compare this with [[01 - The march begins]].",
    )
    expression = TemporalExpression(
        calendar_id=calendar.id,
        year=1,
        month=1,
        precision=TemporalPrecision.MONTH,
        qualifier=TemporalQualifier.UNCERTAIN,
        original_text="January 1 NS? (day unknown)",
    )
    disputed = Event(
        name="03 - A disputed surrender report",
        lore_date=expression.representative_time(converter),
        type="Report",
        description="A damaged chronicle places the surrender of Northwatch "
        "somewhere in January of year 1. The day is unknown. This report is "
        "separate from the dated succession; it does not establish an exact "
        "day for the map or the transfer of power.",
        attributes={
            TEMPORAL_ATTRIBUTE: {
                "schema": 1,
                "expression": expression.to_dict(),
            }
        },
    )
    realm = Entity(
        name="Kingdom of Ashford",
        type="Faction",
        description="Queen Mara's western kingdom stops at the River Ash. "
        "Northwatch and the eastern coast lie beyond its border.",
        attributes={"Ruler": "Queen Mara", "Capital": "Ashford"},
    )
    mara = Entity(
        name="Queen Mara",
        type="Character",
        description="The old queen rules from Ashford until the Northwatch succession.",
        attributes={"Office": "Queen"},
    )
    ilyra = Entity(
        name="Captain Ilyra",
        type="Character",
        description="Commander of the Ashford Army, later crowned at Northwatch.",
        attributes={"Office": "Captain"},
    )
    keep = Entity(
        name="Northwatch Keep",
        type="Location",
        description="An independent eastern fortress guarding the coast.",
        attributes={"Allegiance": "Independent"},
    )
    ashford = Entity(
        name="Ashford",
        type="Location",
        description="The western capital and starting point of the army.",
    )
    army = Entity(
        name="Ashford Army",
        type="Group",
        description="Ilyra's army travels from Ashford to Northwatch "
        "between 1 and 10 January.",
    )
    note = Entity(
        name="The unfinished coronation account",
        type="Document",
        description="Draft",
        attributes={"Purpose": "Validation exercise"},
    )
    entities = [realm, mara, ilyra, ashford, keep, army, note]
    events = [opening, succession, disputed, settled]
    for entity in entities:
        db.insert_entity(entity)
    db.insert_events_bulk(events)
    for entity in [realm, mara, ilyra, keep, army]:
        db.insert_relation(succession.id, entity.id, "involved")
    links: list[tuple[Event | Entity, Event | Entity, str]] = [
        (opening, army, "involved"),
        (army, ilyra, "commanded_by"),
        (army, ashford, "departs_from"),
        (army, keep, "arrives_at"),
        (disputed, keep, "reports_on"),
        (settled, realm, "involved"),
        (note, succession, "describes"),
    ]
    for source, target, relation in links:
        db.insert_relation(source.id, target.id, relation)
    boundary = {
        "status": "known",
        "anchor": {"anchor_id": succession.temporal_anchor_id, "relation": "at"},
    }
    for ruler, side in [(mara, "end"), (ilyra, "start")]:
        db.insert_relation(
            ruler.id,
            realm.id,
            "rules",
            attributes={
                "temporal": {
                    "schema": 1,
                    "start": {"status": "open"},
                    "end": {"status": "open"},
                    side: boundary,
                },
            },
        )
    for entity, attributes, description in [
        (
            realm,
            {"Ruler": "Captain Ilyra"},
            "Ilyra's united kingdom now reaches from Ashford to the eastern coast.",
        ),
        (mara, {"Office": "Former queen"}, "Mara has yielded the crown to Ilyra."),
        (ilyra, {"Office": "Queen"}, "Ilyra was crowned at Northwatch Keep."),
        (
            keep,
            {"Allegiance": "Kingdom of Ashford"},
            "Northwatch is now the eastern stronghold of Ilyra's kingdom.",
        ),
    ]:
        db.insert_relation(
            succession.id,
            entity.id,
            "changes_state",
            attributes={
                "valid_from_event": True,
                "payload": {"attributes": attributes, "description": description},
            },
        )
    map_obj = Map(
        name="Northwatch - watch the border change",
        image_path="assets/maps/northwatch.png",
        description="Compare 1 January with 10 January of year 1.",
        attributes={"map_role": "master"},
    )
    western = [
        {"x": x, "y": y}
        for x, y in [
            (0.18, 0.22),
            (0.44, 0.22),
            (0.45, 0.32),
            (0.49, 0.42),
            (0.47, 0.52),
            (0.51, 0.65),
            (0.47, 0.82),
            (0.18, 0.82),
        ]
    ]
    united = [
        {"x": x, "y": y}
        for x, y in [
            (0.18, 0.22),
            (0.75, 0.22),
            (0.81, 0.30),
            (0.81, 0.43),
            (0.84, 0.52),
            (0.81, 0.64),
            (0.85, 0.82),
            (0.18, 0.82),
        ]
    ]
    border = Marker(
        map_id=map_obj.id,
        object_id=realm.id,
        object_type="entity",
        x=0.315,
        y=0.52,
        label="Ashford realm",
        feature_type="region",
        geometry=western,
    )
    border.x, border.y = calculate_feature_anchor(western)
    markers = [border]
    for entity, x, y in [(ashford, 0.28, 0.72), (keep, 0.72, 0.32), (army, 0.28, 0.72)]:
        markers.append(
            Marker(
                map_id=map_obj.id,
                object_id=entity.id,
                object_type="entity",
                x=x,
                y=y,
                label=entity.name,
            )
        )
    map_obj.layers = MapLayerNode(
        name="Northwatch",
        children=[
            MapLayerNode(
                name=marker.label,
                id=marker.object_id,
                layer_type="region" if marker.is_region else "marker",
            )
            for marker in markers
        ],
    )
    markers[-1].attributes = {
        "_v_marker_icon_id": ARMY_ICON_ID,
        "_v_marker_sizing_source": "custom",
        "_v_marker_sizing": {"mode": "screen_fixed", "screen_px": 72.0},
    }
    db.insert_map(map_obj)
    for marker in markers:
        db.insert_marker(marker)
    anchor = calculate_feature_anchor(united)
    db.feature_geometry_repo.replace_marker_states(
        border.id,
        [
            FeatureGeometryState(
                marker_id=border.id,
                effective_date=change,
                geometry=united,
                anchor_x=anchor[0],
                anchor_y=anchor[1],
            )
        ],
    )
    db.insert_trajectory(
        markers[-1].id,
        [
            Keyframe(before, 0.28, 0.72),
            Keyframe(before + 4.0, 0.49, 0.52),
            Keyframe(change, 0.72, 0.32),
        ],
    )
    db.set_current_time(before)
    connection = db.require_connection()
    items: list[Event | Entity] = [*events, *entities]
    with connection:
        for index, item in enumerate(items):
            insert_or_update_longform_meta(
                connection,
                "events" if isinstance(item, Event) else "entities",
                item.id,
                position=float(index),
                parent_id=None,
                depth=0,
            )
        markdown = export_longform_to_markdown(connection)
    (world.path / "Northwatch Chronicle.md").write_text(markdown, encoding="utf-8")
    report = WorldValidator(db).validate()
    evidence = {
        "before": before,
        "succession": change,
        "after": after,
        "events": {item.name: item.id for item in events},
        "entities": {item.name: item.id for item in entities},
        "map_id": map_obj.id,
        "issues": [
            {
                "type": issue.issue_type.value,
                "name": issue.object_name,
                "message": issue.message,
            }
            for issue in report.issues
        ],
    }
    (world.path / "demo-index.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8"
    )


def create_demo_world(destination: Path) -> World:
    """Create a complete sample atomically, refusing any existing destination.

    Args:
        destination: New world folder, normally under the app's worlds directory.

    Returns:
        The newly created portable world.
    """
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"World already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    manifest = WorldManifest(
        id=str(uuid.uuid4()),
        name=WORLD_NAME,
        description="Watch a border, army and ruler change "
        "during the Northwatch succession.",
        created_at=now,
        modified_at=now,
        db_filename="Northwatch Demo.kraken",
    )
    with TemporaryDirectory(prefix=".northwatch-", dir=destination.parent) as staging:
        world = World(path=Path(staging) / "world", manifest=manifest)
        world.ensure_structure()
        map_dir = world.path / "assets" / "maps"
        map_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(MAP_ASSET, map_dir / "northwatch.png")
        shutil.copyfile(
            ARMY_ASSET, world.path / "assets" / "images" / f"icon_{ARMY_ICON_HEX}.png"
        )
        (world.path / "START HERE.md").write_text(
            GUIDE.read_text(encoding="utf-8"), encoding="utf-8"
        )
        db = DatabaseService(str(world.db_path))
        try:
            db.connect()
            _populate(db, world)
        finally:
            db.close()
        world.path.rename(destination)
    return World(path=destination, manifest=manifest)


def main() -> None:
    """Generate the sample using an optional new destination folder."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("worlds") / WORLD_NAME)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    world = create_demo_world(args.destination)
    logger.info("Demo ready: %s", world.path)


if __name__ == "__main__":
    main()
