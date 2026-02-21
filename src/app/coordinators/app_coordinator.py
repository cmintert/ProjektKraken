"""Application Coordinator Facade.

Provides a single entry point to all coordinators, reducing the number of imports
and attributes that MainWindow manages directly. MainWindow creates AppCoordinator
and accesses individual coordinators through it.
"""

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = logging.getLogger(__name__)


class AppCoordinator(QObject):
    """Facade grouping all application coordinators.

    Instead of MainWindow importing and instantiating each coordinator separately,
    it creates a single AppCoordinator that owns and exposes them.

    Attributes:
        data: DataCoordinator for data loading orchestration.
        time: TimeCoordinator for time/playhead management.
        editor: EditorCoordinator for editor state management.
        navigation: NavigationCoordinator for item selection/navigation.
        backup: BackupCoordinator for backup operations.
        fast_inject: FastInjectCoordinator for template injection.
        import_coord: ImportCoordinator for file import operations.

    """

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize all coordinators with the main window reference.

        Args:
            main_window: The main window instance.

        """
        super().__init__(parent=main_window)

        from src.app.coordinators.backup_coordinator import BackupCoordinator
        from src.app.coordinators.data_coordinator import DataCoordinator
        from src.app.coordinators.editor_coordinator import EditorCoordinator
        from src.app.coordinators.fast_inject_coordinator import (
            FastInjectCoordinator,
        )
        from src.app.coordinators.import_coordinator import ImportCoordinator
        from src.app.coordinators.navigation_coordinator import (
            NavigationCoordinator,
        )
        from src.app.coordinators.time_coordinator import TimeCoordinator

        self.data = DataCoordinator(main_window)
        self.time = TimeCoordinator(main_window)
        self.editor = EditorCoordinator(main_window)
        self.navigation = NavigationCoordinator(main_window)
        self.backup = BackupCoordinator(main_window)
        self.fast_inject = FastInjectCoordinator(main_window)
        self.import_coord = ImportCoordinator(main_window)

        logger.debug("AppCoordinator initialized with 7 coordinators")
