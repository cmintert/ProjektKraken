"""
Tag Migration Script for ProjektKraken.

Migrates tags from JSON attributes to normalized database tables.
This script extracts tags from events.attributes._tags and entities.attributes._tags
and populates the normalized tags, event_tags, and entity_tags tables.

Usage:
    python migrate_tags.py [--db-path PATH] [--dry-run]

Options:
    --db-path PATH    Path to the .kraken database file (default: user data directory)
    --dry-run         Run migration without committing changes (for testing)
"""

import argparse
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, List, Set

from src.core.paths import get_user_data_path
from src.services.db_service import DatabaseService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class TagMigration:
    """Handles migration of tags from JSON to normalized tables."""

    def __init__(self, db_service: DatabaseService):
        """
        Initialize the migration.

        Args:
            db_service: DatabaseService instance connected to the database.
        """
        self.db_service = db_service
        self.conn = db_service._connection
        self.stats = {
            "unique_tags": 0,
            "event_tag_associations": 0,
            "entity_tag_associations": 0,
            "events_processed": 0,
            "entities_processed": 0,
        }

    def check_tables_exist(self) -> bool:
        """
        Check if normalized tag tables already exist.

        Returns:
            bool: True if tables exist, False otherwise.
        """
        cursor = self.conn.execute(
            """
            SELECT COUNT(*) as count FROM sqlite_master 
            WHERE type='table' AND name IN ('tags', 'event_tags', 'entity_tags')
            """
        )
        result = cursor.fetchone()
        return result["count"] == 3

    def create_normalized_tables(self) -> None:
        """Create the normalized tag tables by executing the SQL migration."""
        logger.info("Creating normalized tag tables...")

        migration_path = (
            Path(__file__).parent / "migrations" / "0004_normalize_tags.sql"
        )
        if not migration_path.exists():
            raise FileNotFoundError(f"Migration file not found: {migration_path}")

        with open(migration_path, "r") as f:
            sql = f.read()

        # Execute the SQL migration
        self.conn.executescript(sql)
        self.conn.commit()
        logger.info("Normalized tag tables created successfully.")

    def extract_tags_from_events(self) -> Dict[str, List[str]]:
        """
        Extract all tags from events' attributes JSON.

        Returns:
            Dict mapping event_id to list of tag names.
        """
        logger.info("Extracting tags from events...")
        event_tags_map = {}

        cursor = self.conn.execute(
            "SELECT id, attributes FROM events WHERE attributes IS NOT NULL"
        )

        for row in cursor.fetchall():
            event_id = row["id"]
            try:
                attributes = json.loads(row["attributes"]) if row["attributes"] else {}
                tags = attributes.get("_tags", [])

                if tags and isinstance(tags, list):
                    # Remove duplicates and whitespace
                    unique_tags = list(set(tag.strip() for tag in tags if tag.strip()))
                    if unique_tags:
                        event_tags_map[event_id] = unique_tags
                        self.stats["events_processed"] += 1
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse attributes for event {event_id}: {e}")
                continue

        logger.info(f"Extracted tags from {self.stats['events_processed']} events")
        return event_tags_map

    def extract_tags_from_entities(self) -> Dict[str, List[str]]:
        """
        Extract all tags from entities' attributes JSON.

        Returns:
            Dict mapping entity_id to list of tag names.
        """
        logger.info("Extracting tags from entities...")
        entity_tags_map = {}

        cursor = self.conn.execute(
            "SELECT id, attributes FROM entities WHERE attributes IS NOT NULL"
        )

        for row in cursor.fetchall():
            entity_id = row["id"]
            try:
                attributes = json.loads(row["attributes"]) if row["attributes"] else {}
                tags = attributes.get("_tags", [])

                if tags and isinstance(tags, list):
                    # Remove duplicates and whitespace
                    unique_tags = list(set(tag.strip() for tag in tags if tag.strip()))
                    if unique_tags:
                        entity_tags_map[entity_id] = unique_tags
                        self.stats["entities_processed"] += 1
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse attributes for entity {entity_id}: {e}"
                )
                continue

        logger.info(f"Extracted tags from {self.stats['entities_processed']} entities")
        return entity_tags_map

    def collect_unique_tags(
        self, event_tags: Dict[str, List[str]], entity_tags: Dict[str, List[str]]
    ) -> Set[str]:
        """
        Collect all unique tag names from events and entities.

        Args:
            event_tags: Mapping of event_id to tag list.
            entity_tags: Mapping of entity_id to tag list.

        Returns:
            Set of unique tag names.
        """
        unique_tags = set()

        for tags in event_tags.values():
            unique_tags.update(tags)

        for tags in entity_tags.values():
            unique_tags.update(tags)

        self.stats["unique_tags"] = len(unique_tags)
        logger.info(f"Found {len(unique_tags)} unique tags")
        return unique_tags

    def insert_tags(self, tag_names: Set[str]) -> Dict[str, str]:
        """
        Insert unique tags into the tags table.

        Args:
            tag_names: Set of unique tag names.

        Returns:
            Dict mapping tag name to tag ID.
        """
        logger.info(f"Inserting {len(tag_names)} tags into tags table...")
        tag_id_map = {}
        created_at = time.time()

        for tag_name in sorted(tag_names):  # Sort for consistent ordering
            tag_id = str(uuid.uuid4())

            # Use INSERT OR IGNORE to handle potential duplicates
            self.conn.execute(
                "INSERT OR IGNORE INTO tags (id, name, created_at) VALUES (?, ?, ?)",
                (tag_id, tag_name, created_at),
            )

            # Retrieve the actual ID (in case tag already existed)
            cursor = self.conn.execute(
                "SELECT id FROM tags WHERE name = ?", (tag_name,)
            )
            result = cursor.fetchone()
            tag_id_map[tag_name] = result["id"]

        logger.info(f"Inserted {len(tag_id_map)} tags")
        return tag_id_map

    def insert_event_tag_associations(
        self, event_tags: Dict[str, List[str]], tag_id_map: Dict[str, str]
    ) -> None:
        """
        Insert event-tag associations into event_tags table.

        Args:
            event_tags: Mapping of event_id to tag list.
            tag_id_map: Mapping of tag name to tag ID.
        """
        logger.info("Creating event-tag associations...")
        created_at = time.time()

        for event_id, tags in event_tags.items():
            for tag_name in tags:
                tag_id = tag_id_map.get(tag_name)
                if not tag_id:
                    logger.warning(f"Tag ID not found for tag: {tag_name}")
                    continue

                # Use INSERT OR IGNORE to handle potential duplicates
                cursor = self.conn.execute(
                    """
                    INSERT OR IGNORE INTO event_tags (event_id, tag_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (event_id, tag_id, created_at),
                )
                # Only count if a row was actually inserted (not ignored)
                if cursor.rowcount > 0:
                    self.stats["event_tag_associations"] += 1

        logger.info(
            f"Created {self.stats['event_tag_associations']} event-tag associations"
        )

    def insert_entity_tag_associations(
        self, entity_tags: Dict[str, List[str]], tag_id_map: Dict[str, str]
    ) -> None:
        """
        Insert entity-tag associations into entity_tags table.

        Args:
            entity_tags: Mapping of entity_id to tag list.
            tag_id_map: Mapping of tag name to tag ID.
        """
        logger.info("Creating entity-tag associations...")
        created_at = time.time()

        for entity_id, tags in entity_tags.items():
            for tag_name in tags:
                tag_id = tag_id_map.get(tag_name)
                if not tag_id:
                    logger.warning(f"Tag ID not found for tag: {tag_name}")
                    continue

                # Use INSERT OR IGNORE to handle potential duplicates
                cursor = self.conn.execute(
                    """
                    INSERT OR IGNORE INTO entity_tags (entity_id, tag_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (entity_id, tag_id, created_at),
                )
                # Only count if a row was actually inserted (not ignored)
                if cursor.rowcount > 0:
                    self.stats["entity_tag_associations"] += 1

        logger.info(
            f"Created {self.stats['entity_tag_associations']} entity-tag associations"
        )

    def verify_migration(self) -> bool:
        """
        Verify that the migration was successful.

        Returns:
            bool: True if verification passes, False otherwise.
        """
        logger.info("Verifying migration...")

        # Check that tables exist
        if not self.check_tables_exist():
            logger.error("Normalized tables do not exist after migration")
            return False

        # Verify tag count
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM tags")
        tag_count = cursor.fetchone()["count"]
        if tag_count != self.stats["unique_tags"]:
            logger.error(
                f"Tag count mismatch: expected {self.stats['unique_tags']}, "
                f"got {tag_count}"
            )
            return False

        # Verify event_tags count
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM event_tags")
        event_tags_count = cursor.fetchone()["count"]
        logger.info(f"Event-tag associations in database: {event_tags_count}")

        # Verify entity_tags count
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM entity_tags")
        entity_tags_count = cursor.fetchone()["count"]
        logger.info(f"Entity-tag associations in database: {entity_tags_count}")

        logger.info("Migration verification passed!")
        return True

    def run(self, dry_run: bool = False) -> bool:
        """
        Execute the complete migration.

        Args:
            dry_run: If True, don't commit changes (rollback at end).

        Returns:
            bool: True if migration succeeded, False otherwise.
        """
        try:
            # Check if tables already exist
            if self.check_tables_exist():
                logger.info("Normalized tag tables already exist.")
                logger.info("Migration is idempotent - checking for new data...")
            else:
                # Create normalized tables
                self.create_normalized_tables()

            # Extract tags from events and entities
            event_tags = self.extract_tags_from_events()
            entity_tags = self.extract_tags_from_entities()

            # Collect unique tags
            unique_tags = self.collect_unique_tags(event_tags, entity_tags)

            if not unique_tags:
                logger.info("No tags found to migrate.")
                return True

            # Insert tags
            tag_id_map = self.insert_tags(unique_tags)

            # Insert associations
            self.insert_event_tag_associations(event_tags, tag_id_map)
            self.insert_entity_tag_associations(entity_tags, tag_id_map)

            if dry_run:
                logger.info("DRY RUN: Rolling back changes...")
                self.conn.rollback()
            else:
                # Commit changes
                self.conn.commit()
                logger.info("Changes committed successfully.")

            # Verify migration
            if not dry_run and not self.verify_migration():
                logger.error("Migration verification failed!")
                return False

            # Print statistics
            logger.info("=" * 60)
            logger.info("MIGRATION STATISTICS:")
            logger.info(f"  Events processed: {self.stats['events_processed']}")
            logger.info(f"  Entities processed: {self.stats['entities_processed']}")
            logger.info(f"  Unique tags: {self.stats['unique_tags']}")
            logger.info(
                f"  Event-tag associations: {self.stats['event_tag_associations']}"
            )
            logger.info(
                f"  Entity-tag associations: {self.stats['entity_tag_associations']}"
            )
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            self.conn.rollback()
            raise


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate tags from JSON attributes to normalized tables"
    )
    parser.add_argument(
        "--db-path", type=str, help="Path to the .kraken database file", default=None
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run migration without committing changes",
    )

    args = parser.parse_args()

    # Determine database path
    if args.db_path:
        db_path = args.db_path
    else:
        db_path = get_user_data_path("world.kraken")

    logger.info(f"Using database: {db_path}")

    # Create backup recommendation
    if not args.dry_run:
        logger.warning("=" * 60)
        logger.warning("IMPORTANT: Make sure you have a backup of your database!")
        logger.warning(f"Database path: {db_path}")
        logger.warning("=" * 60)
        response = input("Continue with migration? (yes/no): ")
        if response.lower() != "yes":
            logger.info("Migration cancelled by user.")
            return

    # Connect to database
    db_service = DatabaseService(db_path)
    db_service.connect()

    try:
        # Run migration
        migration = TagMigration(db_service)
        success = migration.run(dry_run=args.dry_run)

        if success:
            logger.info("Migration completed successfully!")
        else:
            logger.error("Migration failed!")

    finally:
        db_service.close()


if __name__ == "__main__":
    main()
