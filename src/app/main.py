"""
Main Application Module (Legacy Shim).

This module has been refactored:
- MainWindow class is now in src.app.main_window
- Application entry point is now in src.app.entry

This shim preserves backward compatibility for existing imports.
"""

# Re-export MainWindow for backward compatibility
# Re-export classes that tests may patch
# These imports maintain backward compatibility with existing test mocks
from PySide6.QtCore import QSettings, QThread, QTimer  # noqa: F401
from PySide6.QtWidgets import QInputDialog, QMessageBox  # noqa: F401

from src.app.command_coordinator import CommandCoordinator  # noqa: F401
from src.app.connection_manager import ConnectionManager  # noqa: F401
from src.app.data_handler import DataHandler  # noqa: F401

# Re-export entry point functions
from src.app.entry import cleanup_app, main  # noqa: F401
from src.app.main_window import MainWindow  # noqa: F401
from src.app.ui_manager import UIManager  # noqa: F401
from src.commands.entity_commands import (  # noqa: F401
    CreateEntityCommand,
    DeleteEntityCommand,
    UpdateEntityCommand,
)
from src.commands.event_commands import (  # noqa: F401
    CreateEventCommand,
    DeleteEventCommand,
    UpdateEventCommand,
)
from src.commands.relation_commands import (  # noqa: F401
    AddRelationCommand,
    RemoveRelationCommand,
    UpdateRelationCommand,
)
from src.services.worker import DatabaseWorker  # noqa: F401

# Support direct execution
if __name__ == "__main__":
    main()
