"""Capture the composed editor through existing Qt fixtures (offscreen evidence)."""

import json
from collections.abc import Generator
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QTextBrowser

from src.core.theme_manager import ThemeManager
from src.services.help_bundle_service import HelpBundleService
from src.services.help_search_service import HelpSearchService

OUTPUT = Path("docs/ux/evidence/krt146/renders")


class HistoryCaptures:
    """Record visible controls using the repository's existing editor fixture."""

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item: pytest.Function) -> Generator[None, None, None]:
        """Capture after the keyboard-route test has exercised the live editor."""
        yield
        if item.callspec.params["entity_type"] != "Character":
            return
        editor = item.funcargs["editor"]
        qtbot = item.funcargs["qtbot"]
        loaded_fonts = {
            name: QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts") / name))
            for name in ("segoeui.ttf", "segoeuib.ttf", "arial.ttf", "georgia.ttf")
        }
        assert all(identity >= 0 for identity in loaded_fonts.values())
        QApplication.setFont(QFont("Segoe UI", 10))
        editor.setWindowFlag(Qt.WindowType.Window, True)
        editor.show()
        section = editor.linked_events_section
        manager = ThemeManager()
        records = []
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for theme in manager.themes:
            manager.set_theme(theme, persist=False)
            editor.setStyleSheet(
                manager.format_stylesheet(
                    Path("src/resources/main.qss").read_text(encoding="utf-8")
                )
            )
            for width in (360, 1100):
                editor.resize(width, 900)
                for populated in (False, True):
                    relations = (
                        [
                            {
                                "id": "relation",
                                "source_id": "event",
                                "source_kind": "event",
                                "source_event_name": "Birth of Ada",
                                "source_event_date": 1,
                                "rel_type": "birth",
                                "attributes": {},
                            }
                        ]
                        if populated
                        else []
                    )
                    editor._load_entity_relations([], relations)
                    editor._presentation.history_disclosure.setChecked(True)
                    button = section.picker_anchor()
                    editor._presentation.reflow()
                    qtbot.wait(30)
                    editor.scroll_area.ensureWidgetVisible(section)
                    qtbot.wait(30)
                    button.setFocus()
                    name = f"{theme}-{width}-{'cards' if populated else 'empty'}.png"
                    assert button.isVisibleTo(editor)
                    assert editor.grab().save(str(OUTPUT / name))
                    records.append(
                        {
                            "file": name,
                            "theme": theme,
                            "requested_width": width,
                            "actual_width": editor.width(),
                            "height": editor.height(),
                            "device_pixel_ratio": editor.devicePixelRatioF(),
                            "font": button.font().toString(),
                            "label": button.text(),
                            "visible": button.isVisibleTo(editor),
                            "focused": button.hasFocus(),
                            "button_width": button.width(),
                            "button_minimum_width": button.minimumSizeHint().width(),
                        }
                    )
        section.setEnabled(False)
        qtbot.wait(20)
        assert editor.grab().save(str(OUTPUT / "disabled.png"))
        section.setEnabled(True)
        help_service = HelpBundleService(root=Path("docs/_build/help"))
        help_service.validate()
        excerpt = help_service.load_inspection_excerpt(
            "authoring.details", "help-lifecycle-event"
        )
        browser = QTextBrowser()
        qtbot.addWidget(browser)
        browser.setHtml(excerpt)
        browser.resize(560, 360)
        browser.show()
        qtbot.wait(20)
        assert "History & context" in browser.toPlainText()
        assert "Add the first event" in browser.toPlainText()
        assert browser.grab().save(str(OUTPUT / "offline-help.png"))
        results = HelpSearchService(help_service.search_documents()).search(
            "Add the first event", limit=8
        )
        (OUTPUT / "captures.json").write_text(
            json.dumps(
                {
                    "platform": "Qt offscreen; not native DPI evidence",
                    "application_fonts": loaded_fonts,
                    "captures": records,
                    "help_search_destinations": [
                        {"title": r.title, "page": r.page, "fragment": r.fragment}
                        for r in results
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    raise SystemExit(
        pytest.main(
            [
                "tests/unit/test_entity_editor.py::test_timeline_add_menu_emits_birth_intent_for_selected_entity",
                "-q",
            ],
            plugins=[HistoryCaptures()],
        )
    )
