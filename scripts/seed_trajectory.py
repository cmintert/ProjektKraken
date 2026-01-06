"""
Seed Trajectory Script
Creates a test map, a marker, and a trajectory for verification.
"""

import sys
import os
import uuid
import time
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.db_service import DatabaseService
from src.app.constants import DEFAULT_DB_NAME
from src.core.trajectory import Keyframe
from src.core.map import Map
from src.core.marker import Marker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_data():
    db_path = DEFAULT_DB_NAME  # or specific path if needed
    db = DatabaseService(db_path)
    db.connect()

    # 1. Ensure Map Exists
    maps = db.get_all_maps()
    if not maps:
        logger.info("Creating test map...")
        map_id = str(uuid.uuid4())
        new_map = Map(id=map_id, name="Test Map", image_path="assets/maps/world.jpg")
        db.insert_map(new_map)
    else:
        map_id = maps[0].id
        logger.info(f"Using existing map: {maps[0].name} ({map_id})")

    # 2. Create Entity (Helper internal method usually, but exposed in db_service)
    entities = db.get_all_entities()
    if not entities:
        logger.info("Creating test entity...")
        # Since insert_entity requires an Entity object, skipping for now and just using a dummy ID
        # or relying on existing entities.
        # Let's try to fetch again or create one if we had the class structure handy.
        # But we can just use a random UUID for object_id since markers don't strictly enforce FK constraint in all repos?
        # Actually Schema enforces FK? No, markers.object_id is just TEXT, no FK to entities/events table in schema (lines 191).
        entity_id = str(uuid.uuid4())
    else:
        # Find one to use
        entity = next((e for e in entities if e.name == "Voyager 1"), entities[0])
        entity_id = entity.id
        logger.info(f"Using existing entity: {entity.name} ({entity_id})")

    # 3. Create Marker (if not exists)
    markers = db.get_markers_for_map(map_id)
    marker = next((m for m in markers if m.object_id == entity_id), None)

    if not marker:
        logger.info("Creating marker...")
        marker_id = str(uuid.uuid4())
        new_marker = Marker(
            id=marker_id,
            map_id=map_id,
            object_id=entity_id,
            object_type="entity",
            x=0.5,
            y=0.5,
            label="Voyager 1",
        )
        db.insert_marker(new_marker)
    else:
        marker_id = marker.id
        logger.info(f"Using existing marker: {marker_id}")

    # 4. Create Trajectory
    # Simple diagonal movement from t=0 to t=100
    trajectory_data = [
        Keyframe(t=0.0, x=0.2, y=0.2),
        Keyframe(t=50.0, x=0.5, y=0.5),
        Keyframe(t=100.0, x=0.8, y=0.8),
    ]

    logger.info("Inserting trajectory...")
    db.insert_trajectory(marker_id, trajectory_data)

    # 5. Verify Reading Back
    logger.info("Verifying read back...")
    trajectories = db.get_trajectories_by_map(map_id)
    found = False
    for m_id, t_id, keyframes in trajectories:
        if m_id == marker_id:
            found = True
            logger.info(f"Found trajectory with {len(keyframes)} keyframes.")
            for k in keyframes:
                logger.info(f"  t={k.t}, x={k.x}, y={k.y}")
            break

    if found:
        logger.info("SUCCESS: Trajectory seeded and verified.")
    else:
        logger.error("FAILURE: Trajectory not found after insertion.")

    db.close()


if __name__ == "__main__":
    seed_data()
