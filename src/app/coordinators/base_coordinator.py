"""Shared base class for application coordinators."""

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

if TYPE_CHECKING:
    from src.app.main_window import MainWindow


class BaseCoordinator(QObject):
    """Base class for all coordinators.

    Coordinators are responsible for handling specific UI logic and interactions
    that were previously embedded in MainWindow. They help decouple the
    application logic from the main window class.
    """

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize the coordinator.

        Args:
            main_window: The main window instance.

        """
        super().__init__(parent=main_window)
        self.main_window = main_window
