"""Capture bounded Help presentation evidence without loading a world."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from PySide6.QtCore import QPoint, QSettings, Qt, qVersion
from PySide6.QtWidgets import QApplication, QTextEdit, QVBoxLayout, QWidget

from src.app.coordinators.help_coordinator import HelpCoordinator
from src.core.theme_manager import ThemeManager
from src.gui.utils.help_context import HelpContextRegistry
from src.services.help_bundle_service import HelpBundleService


def capture(
    output: Path,
    *,
    include_assistance: bool = False,
    topic_id: str = "writing.edit",
    inspection_example: str = "duration",
) -> None:
    """Render six palettes at normal/narrow widths and report label geometry."""
    app = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parents[1]
    theme = ThemeManager(str(root / "themes.json"))
    output.mkdir(parents=True, exist_ok=True)
    owner = QWidget()
    text = QTextEdit(owner)
    QVBoxLayout(owner).addWidget(text)
    registry = HelpContextRegistry()
    registry.register_control(text, "writing.edit")
    coordinator = HelpCoordinator(owner, registry, HelpBundleService())
    source: QWidget | None = None
    if include_assistance and inspection_example == "explorer":
        from src.app.help_composition import HelpSurfaceBindings
        from src.gui.widgets.unified_list import UnifiedListWidget

        explorer = UnifiedListWidget(owner)
        owner.layout().addWidget(explorer)
        bindings = HelpSurfaceBindings(coordinator)
        for widget in [explorer, *explorer.findChildren(QWidget)]:
            bindings.bind(widget)
        source = explorer.btn_new
    elif include_assistance:
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        source = CompactDurationWidget(owner)
        owner.layout().addWidget(source)
        registry.register_inspection(source, "event.duration", "event.timing")
    owner.show()
    records = []
    try:
        for name in theme.get_available_themes():
            theme.set_theme(name)
            coordinator.history.clear()
            coordinator.index = -1
            coordinator.open_topic(topic_id)
            for width in (640, 360):
                coordinator.viewer.resize(width, 560)
                coordinator.viewer.buttons["Return to work"].setFocus(
                    Qt.FocusReason.OtherFocusReason
                )
                app.processEvents()
                viewer = coordinator.viewer
                geometry = {
                    label: {
                        "width": button.width(),
                        "required": button.sizeHint().width(),
                        "enabled": button.isEnabled(),
                        "visible": button.isVisible(),
                    }
                    for label, button in viewer.buttons.items()
                }
                if any(
                    item["width"] < item["required"] or not item["visible"]
                    for item in geometry.values()
                ):
                    raise ValueError(f"Clipped Help control: {name}, {width}")
                filename = f"{name.replace(' ', '-').lower()}-{width}.png"
                if not viewer.grab().save(str(output / filename)):
                    raise OSError(f"Could not save {filename}")
                records.append({"theme": name, "width": width, "controls": geometry})
                if include_assistance:
                    capture_assistance(
                        coordinator, app, output, name, width, records, source
                    )
                    if inspection_example == "explorer" and source is not None:
                        owner.resize(width, 420)
                        source.setEnabled(False)
                        app.processEvents()
                        filename = f"{name}-{width}-disabled-explorer.png"
                        if not owner.grab().save(str(output / filename)):
                            raise OSError(filename)
                        records.append(
                            {
                                "theme": name,
                                "width": width,
                                "state": "disabled-explorer",
                                "file": filename,
                            }
                        )
                        source.setEnabled(True)
        screen = owner.screen()
        metadata = coordinator.service.validate()
        report = {
            "platform": app.platformName(),
            "qt_version": qVersion(),
            "app_version": metadata.version,
            "source_revision": metadata.revision,
            "source_dirty": metadata.dirty,
            "topic_id": topic_id,
            "inspection_example": inspection_example,
            "device_pixel_ratio": owner.devicePixelRatioF(),
            "logical_dpi": screen.logicalDotsPerInch(),
            "renders": records,
        }
        (output / "presentation.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    finally:
        coordinator.stop()
        owner.close()


def capture_assistance(
    coordinator: HelpCoordinator,
    app: QApplication,
    output: Path,
    theme_name: str,
    width: int,
    records: list[dict],
    source: QWidget | None,
) -> None:
    """Capture populated/empty search and the actual native excerpt popup."""
    viewer = coordinator.viewer
    coordinator.show_search()
    for state, query in (("search", "border"), ("no-results", "xyzzy")):
        viewer.query.setText(query)
        coordinator.search()
        if state == "search":
            viewer.results.setFocus()
        else:
            viewer.query.setFocus()
        app.processEvents()
        filename = f"{theme_name}-{width}-{state}.png"
        if not viewer.grab().save(str(output / filename)):
            raise OSError(filename)
        records.append(
            {"theme": theme_name, "width": width, "state": state, "file": filename}
        )
    viewer.hide_search()
    if source is not None:
        coordinator.inspection.display(source, None, source.mapToGlobal(QPoint(0, 0)))
        app.processEvents()
        popup = QApplication.activePopupWidget()
        if popup is None:
            raise ValueError("Missing native explanation popup")
        filename = f"{theme_name}-{width}-explanation.png"
        if not popup.grab().save(str(output / filename)):
            raise OSError(filename)
        records.append(
            {
                "theme": theme_name,
                "width": width,
                "state": "explanation",
                "file": filename,
            }
        )
        coordinator.inspection.dismiss()
        app.processEvents()


def main() -> None:
    """Write presentation artifacts to an explicitly selected directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--search-inspection", action="store_true")
    parser.add_argument("--topic", default="writing.edit")
    parser.add_argument(
        "--inspection-example", choices=("duration", "explorer"), default="duration"
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="kraken-help-capture-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        capture(
            args.output,
            include_assistance=args.search_inspection,
            topic_id=args.topic,
            inspection_example=args.inspection_example,
        )


if __name__ == "__main__":
    main()
