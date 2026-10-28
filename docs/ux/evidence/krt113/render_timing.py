"""Render disposable offscreen timing cards; no saved world or preferences change."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext
from src.core.theme_manager import ThemeManager
from src.gui.dialogs.event_timing_review_dialog import EventTimingReviewDialog
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.help_viewer import HelpViewer
from src.gui.widgets.temporal_range_widget import TemporalRangeWidget
from src.services.event_timing.planning import TimingChangeRequest, prepare_change
from src.services.help_bundle_service import HelpBundleService
from src.services.help_search_service import HelpSearchService


def main() -> None:
    """Capture source modes, independent end, focus and narrow scrolling in six themes."""
    root = Path(__file__).resolve().parents[4]
    output = Path(__file__).resolve().parent
    settings = root / "docs/_build/krt113/render-settings"
    settings.mkdir(parents=True, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings)
    )
    app = QApplication([])
    for font in ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf"):
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + font)
    app.setFont(QFont("Segoe UI", 10))
    manager = ThemeManager()
    manager.apply_theme(
        app, (root / "src/resources/main.qss").read_text(encoding="utf-8")
    )
    converter = CalendarConverter(CalendarConfig.create_default())
    source = Event("Treaty signed at the winter council", 100, id="treaty")
    timing = EventTimingDefinition(
        EndpointDefinition(instant=20),
        "independent",
        EndpointDefinition(
            "event", anchor_id="event:treaty", offset={"unit": "days", "value": -0.5}
        ),
    )
    event = Event("Siege", 20, id="siege", attributes=timing.apply({}))
    context = TemporalResolutionContext.build([event, source], converter)
    for theme in manager.themes:
        manager.set_theme(theme, app, persist=False)
        for width in (360, 680):
            card = TemporalRangeWidget()
            card.set_calendar_converter(converter)
            card.load_timing(event, context)
            card.range_button.setChecked(True)
            card.source_end.options.disclosure.setChecked(True)
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            area.setWidget(card)
            area.resize(width, 1000)
            area.show()
            card.source_end.options.offset.setFocus()
            for _ in range(4):
                app.processEvents()
            area.grab().save(str(output / f"timing-{theme}-{width}.png"))
            area.close()
            area.deleteLater()
            app.processEvents()
    manager.set_theme("dark_mode", app, persist=False)
    card = TemporalRangeWidget()
    card.set_calendar_converter(converter)
    card.load_timing(
        Event(
            "Future metadata",
            None,
            id="future",
            attributes={"_temporal_v2": {"schema": 99, "future": "preserved"}},
        ),
        context,
    )
    card.resize(360, card.sizeHint().height())
    card.show()
    app.processEvents()
    card.grab().save(str(output / "timing-unsupported-360.png"))
    card.close()
    service = HelpBundleService(root=root / "docs/_build/help")
    topic = service.resolve_topic("event.timing")
    results = HelpSearchService(service.search_documents()).search("follow event")
    assert any("event.timing" in result.topic_ids for result in results)
    for theme in ("dark_mode", "light_mode"):
        manager.set_theme(theme, app, persist=False)
        for width in (360, 680):
            viewer = HelpViewer(None)
            viewer.title.setText(topic.title)
            viewer.set_content(service.load_page(topic.page))
            viewer.resize(width, 900)
            viewer.show()
            app.processEvents()
            viewer.browser.scrollToAnchor(topic.fragment)
            app.processEvents()
            viewer.grab().save(str(output / f"help-{theme}-{width}.png"))
            viewer.close()
            viewer.deleteLater()
            app.processEvents()

    plan = prepare_change(
        {
            "world_id": "disposable-review-evidence",
            "events": [event.to_dict(), source.to_dict()],
            "calendar": converter._config.to_json(),
            "calendars": [converter._config.to_dict()],
            "consumers": [],
        },
        TimingChangeRequest(updates={source.id: {"lore_date": 110}}),
    )
    assert not plan.errors
    for theme in manager.themes:
        manager.set_theme(theme, app, persist=False)
        for width in (360, 680):
            dialog = EventTimingReviewDialog(plan.consequences)
            dialog.resize(width, 560)
            dialog.show()
            app.processEvents()
            assert dialog.changes.horizontalScrollBar().maximum() == 0
            dialog.grab().save(str(output / f"review-{theme}-{width}.png"))
            dialog.close()
            dialog.deleteLater()
            app.processEvents()

    for theme in manager.themes:
        manager.set_theme(theme, app, persist=False)
        for width in (360, 680):
            parent = QWidget()
            parent.worker = MagicMock()
            # No database worker is present in this disposable presentation.
            with patch("PySide6.QtCore.QMetaObject.invokeMethod"):
                editor = EventEditorWidget(parent)
                editor.set_calendar_converter(converter)
                editor.set_temporal_context(context)
                editor.load_event(event)
            requests = []
            editor.save_requested.connect(requests.append)
            follow = editor.temporal_widget.source_start
            follow.mode.setCurrentIndex(1)
            follow.events.setCurrentIndex(follow.events.findData("event:" + source.id))
            editor._on_autosave()
            editor.autosave_manager.stop_timer()
            assert not requests
            assert "Timing not saved" in editor.save_status.text()
            editor.setWindowFlag(Qt.WindowType.Window, True)
            editor.resize(width, 900)
            editor.show()
            for _ in range(4):
                app.processEvents()
            editor.grab().save(str(output / f"autosave-{theme}-{width}.png"))
            editor.close()
            editor.deleteLater()
            parent.deleteLater()
            app.processEvents()


if __name__ == "__main__":
    main()
