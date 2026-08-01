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


@pytest.fixture(autouse=True)
def isolate_qsettings(qapp):
    """Isolate settings and complete deferred Qt teardown for every test."""
    if QApplication is None:
        yield
        return

    settings_dir = tempfile.mkdtemp(
        prefix="case-",
        dir=_test_settings_dir,
    )
    _NativeQSettings.setPath(
        _NativeQSettings.Format.IniFormat,
        _NativeQSettings.Scope.UserScope,
        settings_dir,
    )
    TestQSettings.setDefaultFormat(TestQSettings.Format.IniFormat)
    yield

    # pytest-qt schedules widgets for deferred deletion. Flush those events
    # before the next test so singleton signals (notably ThemeManager) cannot
    # accumulate connections to closed widgets across the full serial suite.
    QtCore.QCoreApplication.sendPostedEvents(
        None,
        QtCore.QEvent.Type.DeferredDelete,
    )
    qapp.processEvents()


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
def mock_invoke_method(request):
    """
    Mocks QMetaObject.invokeMethod to prevent TypeErrors when called with
    MagicMocks and to allow verifying thread-safe calls.
    """
    if request.node.get_closest_marker("real_qt_invoke") is not None:
        yield None
        return

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
