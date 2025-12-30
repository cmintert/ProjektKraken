import os
import pathlib
import sys

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


class MockQSettings:
    """
    In-memory mock for QSettings to prevent tests from overwriting real config.
    """

    _storage = {}  # Class-level storage to persist across instances if needed

    def __init__(self, *args, **kwargs):
        self.organization = args[0] if len(args) > 0 else "MockOrg"
        self.application = args[1] if len(args) > 1 else "MockApp"

    def setValue(self, key, value):
        full_key = f"{self.organization}/{self.application}/{key}"
        self._storage[full_key] = value

    def value(self, key, default=None, type=None):
        full_key = f"{self.organization}/{self.application}/{key}"
        val = self._storage.get(full_key, default)
        if type is not None and val is not None:
            try:
                if type == bool and isinstance(val, str):
                    return val.lower() == "true"
                return type(val)
            except (ValueError, TypeError):
                return default
        return val

    def remove(self, key):
        full_key = f"{self.organization}/{self.application}/{key}"
        if full_key in self._storage:
            del self._storage[full_key]

    def contains(self, key):
        full_key = f"{self.organization}/{self.application}/{key}"
        return full_key in self._storage

    def sync(self):
        pass


@pytest.fixture(autouse=True, scope="session")
def mock_qsettings_global():
    """
    Globally patches QSettings for the entire test session.
    Protects user's real settings from being overwritten by tests.
    """
    from unittest.mock import patch

    # Patch PySide6.QtCore.QSettings
    # We use a string reference so imports inside functions pick it up.
    # Note: If modules import QSettings at top-level, they might need reload,
    # but in this codebase most import inside functions or use standard imports.
    patcher = patch("PySide6.QtCore.QSettings", MockQSettings)
    mock_class = patcher.start()

    yield mock_class

    patcher.stop()
