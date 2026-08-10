"""Application Coordinator Facade.

Provides a single entry point to all coordinators, reducing the number of imports
and attributes that MainWindow manages directly. MainWindow creates AppCoordinator
and accesses individual coordinators through it.
"""

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from src.app.qt_invocation import invoke_queued

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = logging.getLogger(__name__)


class AppCoordinator(QObject):
    """Facade grouping all application coordinators.

    Instead of MainWindow importing and instantiating each coordinator separately,
    it creates a single AppCoordinator that owns and exposes them.

    Attributes:
        data: DataCoordinator for data loading orchestration.
        context_tags: ContextTagCoordinator for session creation tags and recovery.
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
        from src.app.coordinators.context_tag_coordinator import ContextTagCoordinator
        from src.app.coordinators.data_coordinator import DataCoordinator
        from src.app.coordinators.editor_coordinator import EditorCoordinator
        from src.app.coordinators.fast_inject_coordinator import (
            FastInjectCoordinator,
        )
        from src.app.coordinators.feature_geometry_coordinator import (
            FeatureGeometryCoordinator,
        )
        from src.app.coordinators.import_coordinator import ImportCoordinator
        from src.app.coordinators.navigation_coordinator import (
            NavigationCoordinator,
        )
        from src.app.coordinators.time_coordinator import TimeCoordinator
        from src.app.coordinators.trajectory_edit_coordinator import (
            TrajectoryEditCoordinator,
        )

        self.context_tags = ContextTagCoordinator(main_window)
        self.data = DataCoordinator(main_window)
        self.time = TimeCoordinator(main_window)
        self.editor = EditorCoordinator(main_window)
        self.navigation = NavigationCoordinator(main_window)
        self.backup = BackupCoordinator(main_window)
        self.fast_inject = FastInjectCoordinator(main_window)
        self.import_coord = ImportCoordinator(main_window)
        self.trajectory_edit = TrajectoryEditCoordinator(main_window)
        self.feature_geometry = FeatureGeometryCoordinator(main_window)

        self.main_window = main_window
        logger.debug("AppCoordinator initialized with 10 coordinators")

    def validate_world(self) -> None:
        """Request world validation on the DatabaseWorker thread.

        The result is delivered asynchronously via the worker's
        ``validation_complete`` signal. Subscribe to that signal before
        calling this method to receive the
        :class:`~src.core.analysis.WorldValidationReport`.
        """
        invoke_queued(
            self.main_window.worker,
            "validate_world",
        )

    def analyze_temporal(self) -> None:
        """Request temporal analysis on the DatabaseWorker thread.

        The result is delivered asynchronously via the worker's
        ``temporal_analysis_complete`` signal. Subscribe to that signal before
        calling this method to receive the
        :class:`~src.core.analysis.TemporalAnalysisReport`.
        """
        invoke_queued(
            self.main_window.worker,
            "analyze_temporal",
        )

    def run_intelligence_analysis(self, analysis_type: str = "all") -> None:
        """Request non-blocking intelligence analysis from a world snapshot.

        The result is delivered asynchronously via the
        :class:`~src.app.intelligence_analysis_manager.IntelligenceAnalysisManager`.
        Subscribe to that manager before calling this method to receive the
        :class:`~src.core.analysis.IntelligenceReport`.

        Args:
            analysis_type: Scope of analysis — ``"all"``, ``"plot_holes"``,
                ``"relations"``, or ``"lore"``.  Defaults to ``"all"``.
        """
        self.main_window.intelligence_analysis_manager.start(analysis_type)

    def cancel_intelligence_analysis(self) -> None:
        """Request cooperative cancellation of the active AI analysis."""
        self.main_window.intelligence_analysis_manager.cancel()
