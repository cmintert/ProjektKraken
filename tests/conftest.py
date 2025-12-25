import os
import sys
import pathlib

import pytest

# Ensure project root is in sys.path
repo_root = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


@pytest.fixture(scope="session")
def qapp():
    """
    Ensure QApplication is instantiated only once.
    """
    if QApplication is None:
        yield None
        return

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True, scope="session")
def init_theme_manager():
    """
    Ensures ThemeManager is initialized for all tests.
    Sets up the theme manager with fallback to ensure themes are always
    available even if themes.json cannot be loaded.
    """
    if QApplication is None:
        return

    # Change to repository root to ensure themes.json can be found
    os.chdir(repo_root)

    from src.core.theme_manager import ThemeManager

    # Initialize the singleton - will load themes.json or use defaults
    tm = ThemeManager()

    # Verify theme was loaded successfully
    theme = tm.get_theme()
    assert "surface" in theme, "ThemeManager failed to load valid theme"


@pytest.fixture
def db_service():
    """
    Provides a fresh in-memory database service for each test.
    """
    from src.services.db_service import DatabaseService

    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()


@pytest.fixture(autouse=True)
def mock_invoke_method():
    """
    Mocks QMetaObject.invokeMethod to prevent TypeErrors when called with
    MagicMocks and to allow verifying thread-safe calls.
    """
    import sys
    from unittest.mock import patch

    if "PySide6" not in sys.modules and QApplication is None:
        yield None
        return

    try:
        with patch("PySide6.QtCore.QMetaObject.invokeMethod") as mock:
            yield mock
    except (ImportError, AttributeError):
        yield None
