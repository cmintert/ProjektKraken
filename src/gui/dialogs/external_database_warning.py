"""Shared user-facing warning text for external world databases."""

from pathlib import Path


def external_database_warning(database_path: Path) -> str:
    """Build the confirmation text for approving an external database path."""
    return (
        "This is an advanced storage configuration. The world manifest will "
        "open the following database outside its world folder:\n\n"
        f"{database_path.resolve(strict=False)}\n\n"
        "Before continuing, understand that:\n"
        "- The world is no longer fully portable.\n"
        "- Moving the manifest without the database will break the world.\n"
        "- Assets and database backups may become separated.\n"
        "- Backup and restore must cover both locations.\n"
        "- File synchronization can cause conflicts between computers.\n"
        "- Network-hosted SQLite databases do not support simultaneous "
        "multi-user editing safely.\n\n"
        "Choose No to cancel. You can instead move the complete world folder "
        "to the desired local, removable, network, or synchronized location."
    )
