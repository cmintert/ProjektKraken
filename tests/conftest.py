import os
import pathlib
import sys
import tempfile

import pytest

# Set Qt to use offscreen platform for headless testing
# This must be set BEFORE any Qt imports
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Ensure project root is in sys.path
repo_root = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

try:
    from PySide6 import QtCore
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None
    QSettings = None
else:
    _NativeQSettings = QtCore.QSettings
    _test_settings_dir = tempfile.mkdtemp(prefix="projektkraken-tests-")
    _NativeQSettings.setPath(
        _NativeQSettings.Format.IniFormat,
        _NativeQSettings.Scope.UserScope,
        _test_settings_dir,
    )

    class TestQSettings(_NativeQSettings):
        """QSettings redirected to a temporary INI store for every test."""

        def __init__(self, *args, **kwargs):
            if not args:
                organization = (
                    QtCore.QCoreApplication.organizationName()
                    or "ProjektKrakenTests"
                )
                application = (
                    QtCore.QCoreApplication.applicationName() or "pytest"
                )
                super().__init__(
                    self.Format.IniFormat,
                    self.Scope.UserScope,
                    organization,
                    application,
                    **kwargs,
                )
            elif len(args) == 2 and all(isinstance(arg, str) for arg in args):
                super().__init__(
                    self.Format.IniFormat,
                    self.Scope.UserScope,
                    args[0],
                    args[1],
                    **kwargs,
                )
            else:
                super().__init__(*args, **kwargs)

    QtCore.QSettings = TestQSettings
    QSettings = TestQSettings


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

    # Remove aggressive os.chdir that changes global state
    # os.chdir(repo_root)

    from src.core.theme_manager import ThemeManager

    # Initialize the singleton with absolute path to themes.json
    # This works because os.path.join (used in paths.py) respects absolute paths
    theme_path = repo_root / "themes.json"
    tm = ThemeManager(str(theme_path))

    # Verify theme was loaded successfully
    theme = tm.get_theme()
    assert "surface" in theme, "ThemeManager failed to load valid theme"


@pytest.fixture(autouse=True)
def _reset_theme_after_test():
    """Reset ThemeManager to dark_mode after each test.

    Prevents theme contamination between tests when a test calls
    set_theme() with a different theme or modifies the singleton state.
    Resets directly without emitting signals to avoid triggering
    callbacks on partially destroyed widgets.
    """
    yield
    try:
        from src.core.theme_manager import ThemeManager

        tm = ThemeManager()
        if tm.current_theme_name != "dark_mode":
            # Reset state without emitting signals (avoids C++ object crashes)
            tm.current_theme_name = "dark_mode"
    except Exception:
        pass


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
        with (
            patch("PySide6.QtCore.QMetaObject.invokeMethod") as mock,
            patch("src.app.main_window.QMetaObject.invokeMethod"),
        ):
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
                if type is bool and isinstance(val, str):
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

    def clear(self):
        """Clear all settings for this organization/application."""
        prefix = f"{self.organization}/{self.application}/"
        keys_to_remove = [k for k in self._storage.keys() if k.startswith(prefix)]
        for key in keys_to_remove:
            del self._storage[key]


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


@pytest.fixture(autouse=True)
def _shutdown_web_engines():
    """Shut down all QWebEngineView instances after each test.

    QWebEngineView must release its page before the profile is deleted,
    otherwise Qt crashes with a segfault during event processing.
    This fixture finds and shuts down all GraphWebView instances,
    then processes pending events to complete the cleanup.
    """
    yield

    if QApplication is None:
        return

    app = QApplication.instance()
    if app is None:
        return

    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView
    except ImportError:
        return

    for widget in app.allWidgets():
        if isinstance(widget, QWebEngineView):
            try:
                page = widget.page()
                if page:
                    page.setWebChannel(None)
                widget.setParent(None)
                widget.close()
                widget.deleteLater()
            except RuntimeError:
                pass

    app.processEvents()


@pytest.fixture(autouse=True, scope="session")
def _mock_web_engine_view():
    """Replace QWebEngineView with a lightweight stub for all tests.

    QWebEngineView creates a Chromium subprocess that causes segfaults
    during pytest-qt's event processing on teardown. This replaces it
    with a lightweight QWidget stub that has the same API surface used
    by GraphWebView.
    """
    from unittest.mock import patch

    if QApplication is None:
        yield
        return

    try:
        from PySide6.QtWidgets import QWidget
    except ImportError:
        yield
        return

    class _StubPage:
        """Minimal stub for QWebEnginePage."""

        def setWebChannel(self, channel):
            pass

        def setBackgroundColor(self, color):
            pass

        def runJavaScript(self, script):
            pass

    class _StubWebEngineView(QWidget):
        """Lightweight stand-in for QWebEngineView in tests."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._page = _StubPage()

        def page(self):
            return self._page

        def setHtml(self, html):
            pass

        def setPage(self, page):
            self._page = page

    patcher = patch(
        "src.gui.widgets.graph_view.graph_web_view.QWebEngineView",
        _StubWebEngineView,
    )
    patcher.start()
    yield
    patcher.stop()
