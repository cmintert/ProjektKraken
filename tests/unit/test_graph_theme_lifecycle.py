"""Latest-theme delivery and renderer state preservation, including real JS."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

if __name__ == "__main__":
    # Install before importing any project Qt code: named stores otherwise use
    # the Windows registry even after setDefaultFormat(IniFormat).
    from scripts.gui_probe_settings import install_probe_settings

    _settings_directory = tempfile.TemporaryDirectory(prefix="kraken-graph-theme-test-")
    install_probe_settings(_settings_directory.name)

from src.core.theme_manager import ThemeManager
from src.gui.widgets.graph_view.graph_web_view import GraphWebView
from src.gui.widgets.graph_view.graph_widget import GraphWidget

pytestmark = pytest.mark.ci_fast


def test_theme_script_retains_placeholder_like_authored_text():
    from src.gui.widgets.graph_view.theme_update import theme_update_script

    label = "Literal %GENERATION% and %FRAME% and %PAYLOAD%"
    script = theme_update_script({}, [{"id": "node", "label": label}], [], 3, 9)
    assert label in script
    assert "window.__krakenGraphThemeRevision = 9" in script


def test_pending_theme_coalesces_and_ignores_replaced_page(qapp, qtbot):
    view = GraphWebView()
    qtbot.addWidget(view)
    original = view._web_view
    engine = MagicMock()
    view._web_view = engine
    widget = GraphWidget()
    qtbot.addWidget(widget)
    theme = dict(widget._get_current_theme_config())
    # No script dispatch while the page is still loading.
    view.update_theme(theme)
    theme["background_color"] = "red"
    view.update_theme(theme)
    engine.page().runJavaScript.assert_not_called()
    view._load_finished(True)
    script, old_callback = engine.page().runJavaScript.call_args.args
    assert '"background_color": "red"' in script
    view._theme_attempts = 249
    view.load_html("replacement")
    old_callback(True)
    assert view._pending_theme is not None
    view._load_finished(True)
    _, callback = engine.page().runJavaScript.call_args.args
    callback(False)
    assert view._theme_timer.isActive()  # The replacement gets a fresh retry budget.
    view._try_theme()
    _, callback = engine.page().runJavaScript.call_args.args
    callback(True)
    assert view._pending_theme is None
    view._web_view = original
    view.shutdown()
    callback(True)  # Late browser completion after shutdown is harmless.


def _javascript(page, qtbot, script):
    result = []
    page.runJavaScript(script, lambda value: result.append(value))
    qtbot.waitUntil(lambda: bool(result), timeout=15000)
    return result[0]


def test_scoped_graph_stays_covered_until_its_current_browser_frame(
    qapp, qtbot, theme_presentation
):
    view = GraphWebView()
    qtbot.addWidget(view)
    original = view._web_view
    view._web_view = engine = MagicMock()
    widget = GraphWidget()
    qtbot.addWidget(widget)
    view.update_theme(widget._get_current_theme_config())
    view._load_finished(True)
    _, update_finished = engine.page().runJavaScript.call_args.args
    update_finished(True)
    assert view._pending_theme is not None
    assert not view._theme_cover.isHidden()
    view._try_theme()
    script, painted = engine.page().runJavaScript.call_args.args
    assert "__krakenGraphThemePainted" in script
    painted(True)
    assert view._pending_theme is None
    assert view._theme_cover.isHidden()
    view._web_view = original
    view.shutdown()


def _check_real_graph_theme(runtime, qtbot):
    widget = GraphWidget()
    qtbot.addWidget(widget)
    runtime.register(widget)
    widget.installEventFilter(runtime)
    widget.resize(800, 600)
    widget.show()
    widget._all_nodes = [
        {"id": "one", "name": "First", "object_type": "entity", "type": "person"},
        {"id": "two", "name": "Second", "object_type": "event"},
    ]
    widget._all_edges = [
        {"id": "edge", "source_id": "one", "target_id": "two", "rel_type": "link"}
    ]
    widget._resolved_lexicon = {
        "nodes": {"person": {"color": "red"}},
        "edges": {"link": {"color": "blue"}},
    }
    widget._refresh_display_locally()
    view = widget._web_view
    page = view._web_view.page()
    qtbot.waitUntil(lambda: view._page_loaded, timeout=15000)
    qtbot.waitUntil(
        lambda: _javascript(page, qtbot, "Boolean(window.updateGraph)"), timeout=15000
    )
    edge_font = """(() => {
        const {size, align, strokeWidth, color, background} =
            network.body.edges.edge.options.font;
        return JSON.stringify([size, align, strokeWidth, color, background]);
    })()"""
    theme = ThemeManager().get_theme()
    actual = json.loads(_javascript(page, qtbot, edge_font))
    assert actual == [14, "horizontal", 0, theme["text_main"], theme["app_bg"]], actual
    _javascript(
        page,
        qtbot,
        """(() => {
        network.stopSimulation(); network.selectNodes(['one']);
        network.moveTo({position: {x: 12, y: 34}, scale: 0.7, animation: false});
        window.themeRestarts = 0;
        network.startSimulation = () => {window.themeRestarts++;};
        return true;
    })()""",
    )
    snapshot = """JSON.stringify({positions: network.getPositions(),
        selection: network.getSelection(), camera: network.getViewPosition(),
        scale: network.getScale(), physics: network.physics.options.enabled})"""
    before = _javascript(page, qtbot, snapshot)
    for name in ("light_mode", "dark_mode", "light_mode"):
        ThemeManager().set_theme(name, persist=False)
        qtbot.waitUntil(lambda: view._pending_theme is None, timeout=15000)
        theme = ThemeManager().get_theme()
        actual = json.loads(_javascript(page, qtbot, edge_font))
        assert actual == [14, "horizontal", 0, theme["text_main"], theme["app_bg"]]
    assert _javascript(page, qtbot, snapshot) == before
    assert _javascript(page, qtbot, "window.themeRestarts") == 0
    assert (
        _javascript(page, qtbot, "network.body.nodes.one.options.color.background")
        == "red"
    )
    assert (
        _javascript(page, qtbot, "network.body.edges.edge.options.color.color")
        == "blue"
    )
    assert (
        _javascript(page, qtbot, "network.body.nodes.one.options.font.color")
        == ThemeManager().get_theme()["text_main"]
    )
    widget.hide()
    ThemeManager().set_theme("dark_mode", persist=False)
    qtbot.waitUntil(lambda: view._pending_theme is None, timeout=15000)
    widget.show()
    widget._all_nodes = []
    widget._all_edges = []
    widget._refresh_display_locally()
    ThemeManager().set_theme("light_mode", persist=False)
    qtbot.waitUntil(lambda: view._pending_theme is None, timeout=15000)
    expected = ThemeManager().get_theme()["text_main"]
    from PySide6.QtGui import QColor

    color = QColor(expected)
    expected_css = f"rgb({color.red()}, {color.green()}, {color.blue()})"
    assert (
        _javascript(
            page, qtbot, "getComputedStyle(document.querySelector('.message h2')).color"
        )
        == expected_css
    )
    view.shutdown()


def _check_graph_authoring_renderer(qtbot):
    """Exercise actual Vis datasets, bridge payloads, and scope restoration."""
    from src.core.authoring_scope import AuthoringScope

    widget = GraphWidget()
    qtbot.addWidget(widget)
    widget.resize(700, 500)
    widget.show()
    nodes = [
        {
            "id": "first",
            "name": "Scout",
            "object_type": "entity",
            "tags": ["Adventure"],
        },
        {"id": "second", "name": "Faction", "object_type": "entity", "tags": ["Other"]},
    ]
    widget.display_graph(nodes, [])
    view = widget._web_view
    page = view._web_view.page()
    qtbot.waitUntil(lambda: view._renderer_generation == view._page_generation)
    qtbot.waitUntil(lambda: bool(widget._session_positions))
    before = dict(widget._session_positions)
    gestures = []
    widget.connection_requested.connect(gestures.append)
    assert _javascript(
        page,
        qtbot,
        """(() => {
            const graph = document.getElementById('mynetwork');
            const handle = document.querySelector('.graph-connect-handle');
            network.unselectAll();
            network.redraw();
            handle.setPointerCapture = () => {};
            handle.hasPointerCapture = () => true;
            const viewport = graph.getBoundingClientRect();
            const center = network.canvasToDOM(network.getPosition('first'));
            const x = viewport.left + center.x;
            const y = viewport.top + center.y;
            const move = (clientX, clientY) => {
                const element = document.elementFromPoint(clientX, clientY);
                element?.dispatchEvent(new PointerEvent('pointermove', {
                    bubbles: true, clientX, clientY
                }));
            };
            move(x, y);
            if (handle.hidden || handle.dataset.source !== 'first') return false;
            const initial = handle.getBoundingClientRect();
            network.body.data.nodes.update({
                id: 'first', label: 'Province of Harendun and its neighboring towns'
            });
            network.redraw();
            const start = handle.getBoundingClientRect();
            if (start.left !== initial.left || start.top !== initial.top) return false;
            const handleX = start.left + start.width / 2;
            for (let step = 1; step <= 20; step++) {
                move(x + (handleX - x) * step / 20, y);
                if (handle.hidden || handle.dataset.source !== 'first') return false;
            }
            if (document.elementFromPoint(handleX, y) !== handle) return false;
            const target = network.canvasToDOM(network.getPosition('second'));
            handle.dispatchEvent(new PointerEvent('pointerdown', {
                button: 0, clientX: handleX, clientY: y
            }));
            handle.dispatchEvent(new PointerEvent('pointerup', {
                button: 0, clientX: handleX, clientY: y
            }));
            handle.dispatchEvent(new MouseEvent('click', {detail: 1}));
            handle.click();
            handle.dispatchEvent(new PointerEvent('pointerdown', {
                button: 0, clientX: handleX, clientY: y
            }));
            handle.dispatchEvent(new PointerEvent('pointermove', {
                clientX: handleX, clientY: y + 25
            }));
            handle.dispatchEvent(new PointerEvent('pointerup', {
                button: 0, clientX: handleX, clientY: y
            }));
            handle.dispatchEvent(new PointerEvent('pointerdown', {
                button: 0, clientX: handleX, clientY: y
            }));
            handle.dispatchEvent(new PointerEvent('pointerup', {
                button: 0, clientX: viewport.left + target.x,
                clientY: viewport.top + target.y
            }));
            return network.getSelectedNodes().length === 0;
        })()""",
    )
    qtbot.waitUntil(lambda: len(gestures) >= 3)
    assert len(gestures) == 3
    assert gestures[0]["source"] == "first" and not gestures[0].get("target")
    assert gestures[1]["source"] == "first" and not gestures[1].get("target")
    assert gestures[2]["source"] == "first" and gestures[2]["target"] == "second"

    widget.seed_node("third", {"x": 108.0, "y": 54.0})
    nodes.append(
        {
            "id": "third",
            "name": "Council",
            "object_type": "event",
            "tags": ["Adventure"],
        }
    )
    widget.display_graph(nodes, [])
    qtbot.waitUntil(lambda: "third" in widget._session_positions)
    assert {
        identity: widget._session_positions[identity] for identity in before
    } == before
    assert widget._session_positions["third"] == {"x": 108, "y": 54}
    widget.set_authoring_scope(AuthoringScope(("Adventure",)))
    qtbot.waitUntil(
        lambda: _javascript(
            page, qtbot, "network.body.data.nodes.get('second') === null"
        )
    )
    widget.set_authoring_scope(AuthoringScope())
    qtbot.waitUntil(
        lambda: _javascript(
            page, qtbot, "Boolean(network.body.data.nodes.get('second'))"
        )
    )
    assert (
        json.loads(
            _javascript(page, qtbot, "JSON.stringify(network.getPosition('second'))")
        )
        == before["second"]
    )

    _javascript(
        page,
        qtbot,
        "network.selectNodes(['first']); network.emit('click', {nodes: ['first']})",
    )
    qtbot.waitUntil(lambda: widget._selected_graph_node == ("entity", "first"))
    widget.display_graph(nodes, [], focus_node_id="third")
    qtbot.waitUntil(
        lambda: _javascript(page, qtbot, "network.getSelectedNodes()[0] === 'third'")
    )
    widget.connect_button.click()
    assert gestures[-1] == {"source": "third", "source_kind": "event"}

    view.shutdown()


def test_real_graph_theme_in_isolated_process():
    # Native WebEngine must not run inside pytest-qt's shared teardown lifecycle.
    environment = dict(
        os.environ,
        QT_QPA_PLATFORM="offscreen",
        QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu",
    )
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy; runpy.run_path("
            + repr(str(Path(__file__).resolve()))
            + ", run_name='__main__')",
        ],
        check=True,
        env=environment,
        timeout=60,
        capture_output=True,
        text=True,
    )


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    from scripts.benchmark_theme_switch import _wait
    from src.gui.utils.theme_presentation import install_theme_presentation

    with _settings_directory:
        app = QApplication([])
        runtime = install_theme_presentation(app)
        # Exercise scoped theme delivery on the Graph root. In this isolated
        # browser fixture, an application filter also sees native WebEngine
        # internals before they have stable Python wrappers.
        app.removeEventFilter(runtime)
        ThemeManager().apply_theme(
            app, Path("src/resources/main.qss").read_text("utf-8")
        )

        class _Loop:
            def addWidget(self, widget):
                pass

            def waitUntil(self, predicate, timeout=15000):
                _wait(app, predicate, timeout / 1000)

        _check_real_graph_theme(runtime, _Loop())
        _check_graph_authoring_renderer(_Loop())
        runtime.close()
