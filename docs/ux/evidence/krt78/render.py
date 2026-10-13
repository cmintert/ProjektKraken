"""Generate offscreen KRT-78 presentation evidence, not native acceptance."""

import json
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QEventLoop, QSettings, Qt
from PySide6.QtGui import QFont, QFontDatabase, QFontInfo
from PySide6.QtWidgets import QApplication, QWidget

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from src.core.calendar import CalendarConfig, CalendarConverter  # noqa: E402
from src.core.events import Event  # noqa: E402
from src.core.theme_manager import ThemeManager  # noqa: E402
from src.gui.widgets.event_editor import EventEditorWidget  # noqa: E402
from src.gui.widgets.timeline import TimelineWidget  # noqa: E402


def main() -> None:
    """Capture shared controls at normal/narrow widths and text scales."""
    out = Path("tmp/krt78-presentation")
    out.mkdir(parents=True, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(out / "settings")
    )
    app = QApplication([])
    for filename in ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf"):
        QFontDatabase.addApplicationFont(f"C:/Windows/Fonts/{filename}")
    app.setFont(QFont("Segoe UI", 10))
    manager = ThemeManager()
    manager.load_stylesheet("src/resources/main.qss")
    base_font = QFont(app.font())
    converter = CalendarConverter(CalendarConfig.create_default())
    records = []
    for theme in manager.themes:
        manager.set_theme(theme, app)
        for scale in (1.0, 1.25, 1.5, 2.0):
            font = QFont(base_font)
            font.setPointSizeF(base_font.pointSizeF() * scale)
            app.setFont(font)
            app.setStyleSheet(
                manager.format_stylesheet()
                + f"\nQWidget {{ font-size: {font.pointSizeF()}pt; }}"
            )
            for width in (360, 760):
                parent = QWidget()
                editor = EventEditorWidget(parent)
                # This isolated presentation fixture has no attachment worker.
                editor.gallery.set_owner = lambda *_args: None
                editor.autosave_manager.set_enabled(False)
                editor.set_calendar_converter(converter)
                editor.load_event(Event(id="event", name="Charter", lore_date=433177.5))
                editor.inspector.main_tabs.setCurrentWidget(editor.tab_details)
                editor.resize(width, 720)
                editor.show()
                timeline = TimelineWidget()
                timeline.set_calendar_converter(converter)
                timeline.set_selected_event_navigation("event", "Charter")
                timeline.resize(width, 320)
                timeline.show()
                app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
                stem = f"{theme}-{scale:g}-{width}"
                editor.grab().save(str(out / f"{stem}-editor.png"))
                timeline.grab().save(str(out / f"{stem}-timeline.png"))
                menu = timeline.date_navigation_menu
                menu.popup(timeline.mapToGlobal(timeline.rect().topLeft()))
                app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
                menu.grab().save(str(out / f"{stem}-menu.png"))
                menu.close()
                timeline.set_selected_event_navigation(None, "Select an event")
                menu.popup(timeline.mapToGlobal(timeline.rect().topLeft()))
                app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
                menu.grab().save(str(out / f"{stem}-disabled.png"))
                menu.close()
                timeline.activateWindow()
                focus_target = (
                    timeline.action_toolbar.overflow_button
                    if timeline.btn_go_to_date.isHidden()
                    else timeline.btn_go_to_date
                )
                focus_target.setFocus(Qt.FocusReason.TabFocusReason)
                app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
                timeline.grab().save(str(out / f"{stem}-focus.png"))
                records.append(
                    {
                        "theme": theme,
                        "text_scale": scale,
                        "requested_width": width,
                        "editor_width": editor.width(),
                        "timeline_width": timeline.width(),
                        "font_points": font.pointSizeF(),
                        "effective_font": QFontInfo(editor.font()).family(),
                        "effective_font_points": QFontInfo(editor.font()).pointSizeF(),
                        "device_pixel_ratio": timeline.devicePixelRatioF(),
                        "overflowed": timeline.btn_go_to_date.isHidden(),
                        "focus_target": focus_target.text(),
                        "focus_acquired": focus_target.hasFocus(),
                    }
                )
                editor.close()
                timeline.close()
                parent.close()
                editor.deleteLater()
                timeline.deleteLater()
                parent.deleteLater()
                app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
    (out / "manifest.json").write_text(json.dumps(records, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
