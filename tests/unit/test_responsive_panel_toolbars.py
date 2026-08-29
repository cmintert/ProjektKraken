"""Rendered-width checks for panels using responsive action toolbars."""

from pathlib import Path

from PySide6.QtWidgets import QToolButton

from src.core.theme_manager import ThemeManager
from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel
from src.gui.widgets.history_panel import HistoryPanelWidget
from src.gui.widgets.timeline import TimelineWidget
from src.gui.widgets.unified_list import UnifiedListWidget


def _show_narrow(qtbot, widget, width: int = 210) -> None:
    qtbot.addWidget(widget)
    widget.setMaximumWidth(width)
    widget.resize(width, 500)
    widget.show()
    qtbot.wait(1)
    widget.action_toolbar.refresh()


def test_analysis_keeps_primary_action_and_overflows_editorial(qtbot) -> None:
    panel = MainAnalysisPanel()
    _show_narrow(qtbot, panel)

    assert not panel.validate_btn.isHidden()
    assert panel.editorial_checks in panel.action_toolbar.overflowed_buttons()
    assert panel.validate_btn.width() >= panel.validate_btn.sizeHint().width()


def test_timeline_keeps_playback_and_overflows_secondary_options(qtbot) -> None:
    panel = TimelineWidget()
    _show_narrow(qtbot, panel)

    assert not panel.btn_play_pause.isHidden()
    assert (
        panel.chk_snap_playhead_to_events
        in panel.action_toolbar.overflowed_buttons()
    )


def test_project_panel_keeps_new_menu_available_at_narrow_width(qtbot) -> None:
    panel = UnifiedListWidget()
    _show_narrow(qtbot, panel, width=150)

    assert not panel.btn_new.isHidden()
    assert panel.btn_refresh in panel.action_toolbar.overflowed_buttons()
    assert panel.btn_new.width() >= panel.btn_new.sizeHint().width()


def test_history_keeps_undo_and_overflows_clear_at_narrow_width(qtbot) -> None:
    panel = HistoryPanelWidget()
    _show_narrow(qtbot, panel, width=150)

    assert not panel.undo_btn.isHidden()
    assert panel.clear_btn in panel.action_toolbar.overflowed_buttons()


def test_analysis_tab_scrollers_are_themed_and_aligned(qapp, qtbot) -> None:
    template = Path("src/resources/main.qss").read_text(encoding="utf-8")
    previous_style = qapp.styleSheet()
    qapp.setStyleSheet(template.format(**ThemeManager().get_theme()))
    try:
        panel = MainAnalysisPanel()
        _show_narrow(qtbot, panel, width=220)
        tab_bar = panel.tab_widget.tabBar()
        scroll_buttons = {
            button.objectName(): button
            for button in tab_bar.findChildren(QToolButton)
        }
        left = scroll_buttons["ScrollLeftButton"]
        right = scroll_buttons["ScrollRightButton"]

        assert tab_bar.usesScrollButtons()
        assert left.isVisible()
        assert right.isVisible()
        assert left.geometry().right() < right.geometry().left()
        assert right.geometry().right() <= tab_bar.rect().right()
        assert left.geometry().top() == right.geometry().top()
        assert abs(left.height() - tab_bar.height()) <= 2
    finally:
        qapp.setStyleSheet(previous_style)
