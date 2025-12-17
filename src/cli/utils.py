"""
CLI Utilities Module.

Common utility functions for CLI tools.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def validate_database_path(db_path: str, allow_create: bool = False) -> bool:
    """
    Validate that a database file exists.

    Args:
        db_path: Path to the database file.
        allow_create: If True, allows non-existent databases (for create
            operations).

    Returns:
        True if valid, False otherwise.
    """
    path = Path(db_path)

    if not path.exists():
        if allow_create:
            # Database will be created automatically by DatabaseService
            logger.debug(f"Database will be created: {db_path}")
            return True
        else:
            logger.error(f"Database file not found: {db_path}")
            return False

    return True
