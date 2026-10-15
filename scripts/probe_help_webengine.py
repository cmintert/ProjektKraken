"""Run the isolated native Graph-input inspection probe outside pytest's stub."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QElapsedTimer, QEvent, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from src.app.coordinators.help_coordinator import HelpCoordinator
from src.app.help_composition import HelpSurfaceBindings
from src.core.theme_manager import ThemeManager
from src.gui.utils.help_context import HelpContextRegistry
from src.gui.widgets.graph_view.graph_widget import GraphWidget
from src.services.help_bundle_service import HelpBundleService

_LOAD_TIMEOUT_MS = 10_000


def probe(output: Path) -> None:
    """Inspect the real Chromium child with window-level input and no world."""
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="kraken-help-probe-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        ThemeManager(str(Path(__file__).resolve().parents[1] / "themes.json"))
        owner = QWidget()
        graph = GraphWidget(owner)
        QVBoxLayout(owner).addWidget(graph)
        registry = HelpContextRegistry()
        service = HelpBundleService()
        coordinator = HelpCoordinator(owner, registry, service)
        bindings = HelpSurfaceBindings(coordinator)
        for widget in [graph, *graph.findChildren(QWidget)]:
            bindings.bind(widget)
        engine = graph._web_view._web_view
        engine.setHtml(
            "<html><head><title>untouched</title></head>"
            '<body onclick="document.title=\'activated\'" style="margin:0">'
            '<div style="height:100vh">Graph native input probe</div></body></html>'
        )
        owner.resize(720, 500)
        owner.show()
        timer = QElapsedTimer()
        timer.start()
        try:
            while engine.title() != "untouched" and timer.elapsed() < _LOAD_TIMEOUT_MS:
                QTest.qWait(20)
            if engine.title() != "untouched":
                raise RuntimeError("Graph probe document did not load")
            coordinator.inspection.enter()
            point = engine.mapToGlobal(engine.rect().center())
            QTest.mouseClick(
                owner.windowHandle(),
                Qt.MouseButton.LeftButton,
                pos=owner.mapFromGlobal(point),
            )
            QTest.qWait(150)
            popup = QApplication.activePopupWidget()
            if popup is None or coordinator.inspection._topic_id != "graph.exploring":
                raise RuntimeError("Graph native child did not resolve inspection")
            if engine.title() != "untouched":
                raise RuntimeError("Inspection activated the Chromium page")
            metadata = service.validate()
            report = {
                "platform": app.platformName(),
                "revision": metadata.revision,
                "dirty": metadata.dirty,
                "input": "QTest window-level pointer click on real Chromium child",
                "topic": coordinator.inspection._topic_id,
                "dom_click_received": False,
                "world_loaded": False,
                "limits": "Synthetic local HTML; no real graph node, world or human workflow acceptance.",
            }
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        finally:
            coordinator.stop()
            owner.close()
            owner.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()


def main() -> None:
    """Write a bounded machine-readable native probe result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    probe(parser.parse_args().output)


if __name__ == "__main__":
    main()
