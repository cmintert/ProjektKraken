"""
Data Migration Utility for ProjektKraken.
Moves existing world.kraken and assets from project root to the AppData directory.
"""

import logging
import shutil
from pathlib import Path

from src.core.paths import get_user_data_path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def migrate():
    # 1. Define Paths
    project_root = Path(__file__).parent.resolve()

    # Source Paths
    old_db = project_root / "world.kraken"
    old_assets = project_root / "assets"

    # Destination Paths
    new_db_path = Path(get_user_data_path("world.kraken"))
    new_data_dir = new_db_path.parent

    logger.info("Migration started.")
    logger.info(f"Source: {project_root}")
    logger.info(f"Destination: {new_data_dir}")

    # 2. Migrate Database
    if old_db.exists():
        old_size = old_db.stat().st_size
        logger.info(f"Found old database at {old_db} ({old_size} bytes)")

        # Check if destination exists and is smaller (default empty one is ~98KB)
        # We only overwrite if the source is significantly larger or if we are sure.
        # To be safe, we'll back up the new one if it exists.
        if new_db_path.exists():
            backup_path = new_db_path.with_suffix(".kraken.bak")
            logger.info(f"Backing up existing new database to {backup_path}")
            try:
                shutil.copy2(new_db_path, backup_path)
            except Exception as e:
                logger.error(f"Failed to create backup: {e}")

        logger.info(f"Copying {old_db} -> {new_db_path}")
        try:
            shutil.copy2(old_db, new_db_path)
            # Verify size
            new_size = new_db_path.stat().st_size
            if new_size == old_size:
                logger.info(f"Database migrated successfully (Size: {new_size})")
            else:
                logger.error(
                    f"Size mismatch after copy! Expected {old_size}, got {new_size}"
                )
        except Exception as e:
            logger.error(f"Failed to copy database: {e}")
            logger.error(
                "Is the application still running? Please close it and try again."
            )
    else:
        logger.warning(f"No source database found at {old_db}. Skipping DB migration.")

    # 3. Migrate Assets
    if old_assets.exists() and old_assets.is_dir():
        # Specifically move images, thumbnails and maps
        folders_to_migrate = ["images", "thumbnails", "maps"]
        for folder in folders_to_migrate:
            src_folder = old_assets / folder
            if src_folder.exists() and src_folder.is_dir():
                dest_folder = new_data_dir / "assets" / folder
                dest_folder.mkdir(parents=True, exist_ok=True)

                logger.info(f"Migrating folder: {folder}")
                for item in src_folder.iterdir():
                    if item.is_file():
                        dest_file = dest_folder / item.name
                        if (
                            not dest_file.exists()
                            or dest_file.stat().st_size != item.stat().st_size
                        ):
                            logger.info(f"  Copying {item.name}")
                            shutil.copy2(item, dest_file)
                        else:
                            logger.info(f"  Skipping {item.name} (already exists)")
            else:
                logger.info(f"Folder not found: {folder}")
    else:
        logger.warning(
            f"No source assets folder found at {old_assets}. Skipping asset migration."
        )

    logger.info("Migration check complete!")


if __name__ == "__main__":
    migrate()
