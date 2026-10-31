import os
import pathlib
import sys
import tempfile

import pytest


@pytest.fixture
def prepare_timing_command(db_service):
    """Exercise the real prepared-plan boundary with the shared database fixture."""

    def prepare(command):
        from src.commands.event_timing_commands import ApplyEventTimingPlanCommand
        from src.commands.event_timing_intents import request_for_command
        from src.services.event_timing.planning import prepare_change
        from src.services.event_timing.store import capture, register

        snapshot = capture(db_service)
        plan = prepare_change(snapshot, request_for_command(command, snapshot))
        assert not plan.errors, plan.errors
        register(db_service, plan)
        return ApplyEventTimingPlanCommand(command, plan.identity, plan.fingerprint)

    return prepare


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
                    QtCore.QCoreApplication.organizationName() or "ProjektKrakenTests"
                )
                application = QtCore.QCoreApplication.applicationName() or "pytest"
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


@pytest.fixture
def qtbot(qtbot):
    """Own registered widgets until pytest-qt finishes their deferred teardown."""
    registered = qtbot.addWidget
    retained = {}

    def add_widget(widget, *, before_close_func=None):
        registered(widget, before_close_func=before_close_func)
        identity = id(widget)
        retained[identity] = widget

        def destroyed():
            retained.pop(identity, None)
            # Explicit deletion must also remove pytest-qt's weak registration:
            # retaining an invalid wrapper would otherwise make close() fail.
            node = qtbot._request.node
            widgets = getattr(node, "qt_widgets", None)
            if widgets is not None:
                node.qt_widgets = [
                    entry for entry in widgets if id(entry[0]()) != identity
                ]

        widget.destroyed.connect(destroyed)

    # Preserve both public spellings and pytest-qt's normal close callbacks.
    qtbot.addWidget = add_widget
    qtbot.add_widget = add_widget
    yield qtbot
    retained.clear()


@pytest.fixture
def theme_presentation(qapp):
    """Compose the production visible-first renderer with shared Qt ownership."""
    from src.core.theme_manager import ThemeManager
    from src.gui.utils.theme_presentation import install_theme_presentation

    runtime = install_theme_presentation(qapp)
    ThemeManager().apply_theme(
        qapp, (repo_root / "src/resources/main.qss").read_text("utf-8")
    )
    yield runtime
    runtime.close()


@pytest.fixture(params=("legacy", "scoped"))
def theme_delivery(request):
    """Exercise compatibility and production presentation for authoring contracts."""
    if request.param == "scoped":
        return request.getfixturevalue("theme_presentation")
    return None


@pytest.fixture(autouse=True)
def isolate_qsettings(qapp):
    """Isolate settings and application presentation; finish deferred Qt teardown."""
    if QApplication is None:
        yield
        return

    existing_widgets = set(qapp.topLevelWidgets())
    saved_stylesheet = qapp.styleSheet()
    saved_font = qapp.font()
    saved_palette = qapp.palette()

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

    # Older component tests construct unparented editors without qtbot ownership.
    # Their singleton theme connections otherwise retain closed authoring trees
    # across thousands of cases, making later theme changes traverse every tree.
    # Preserve outer-scoped fixtures and application infrastructure. Main-window
    # fixtures own their worker and application-filter shutdown explicitly.
    for widget in qapp.topLevelWidgets():
        if widget not in existing_widgets and type(widget).__module__.startswith(
            "src.gui.widgets."
        ):
            widget.deleteLater()

    # pytest-qt schedules widgets for deferred deletion. Flush those events
    # before the next test so singleton signals (notably ThemeManager) cannot
    # accumulate connections to closed widgets across the full serial suite.
    QtCore.QCoreApplication.sendPostedEvents(
        None,
        QtCore.QEvent.Type.DeferredDelete,
    )
    qapp.processEvents()

    # Theme/font tests change QApplication as well as their own widgets. Restore
    # those values so later component tests do not inherit another case's QSS.
    if qapp.styleSheet() != saved_stylesheet:
        qapp.setStyleSheet(saved_stylesheet)
    if qapp.font() != saved_font:
        qapp.setFont(saved_font)
    if qapp.palette() != saved_palette:
        qapp.setPalette(saved_palette)


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
def isolated_theme_manager(qapp, monkeypatch, init_theme_manager, isolate_qsettings):
    """Give each case a real theme sender with no earlier-case signal receivers."""
    from src.core.theme_manager import ThemeManager

    monkeypatch.setattr(ThemeManager, "_instance", None)
    manager = ThemeManager(str(repo_root / "themes.json"))
    yield manager
    # Complete widget deletion while their own sender is still the singleton.
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    qapp.processEvents()


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


@pytest.fixture(autouse=True, scope="session")
def _mock_web_engine_view():
    """Replace QWebEngineView with a lightweight stub for all tests.

    QWebEngineView creates a Chromium subprocess that causes segfaults
    during pytest-qt's event processing on teardown. This replaces the
    application's only QWebEngineView subclass with a lightweight QWidget
    stub, so no native WebEngine instances require per-test cleanup.
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

        def runJavaScript(self, script, callback=None):
            if callback is not None:
                callback(True)

    class _StubWebEngineView(QWidget):
        """Lightweight stand-in for QWebEngineView in tests."""

        loadFinished = QtCore.Signal(bool)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._page = _StubPage()

        def page(self):
            return self._page

        def setHtml(self, html):
            self.loadFinished.emit(True)

        def setPage(self, page):
            self._page = page

    patcher = patch(
        "src.gui.widgets.graph_view.graph_web_view.QWebEngineView",
        _StubWebEngineView,
    )
    patcher.start()
    yield
    patcher.stop()
