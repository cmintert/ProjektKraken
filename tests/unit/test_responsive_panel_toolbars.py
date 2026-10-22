"""Rendered-width checks for panels using responsive action toolbars."""

from pathlib import Path

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QToolButton

from src.core.theme_manager import ThemeManager
from src.gui.ui_constants import WORKSPACE_CONTENT_INSET
from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel
from src.gui.widgets.graph_view.graph_widget import GraphWidget
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


def test_analysis_checkbox_stays_at_the_right_edge(qtbot) -> None:
    panel = MainAnalysisPanel()
    qtbot.addWidget(panel)
    panel.resize(900, 500)
    panel.show()
    qtbot.wait(1)
    panel.action_toolbar.refresh()

    assert not panel.editorial_checks.isHidden()
    assert (
        panel.editorial_checks.geometry().right()
        == panel.action_toolbar.contentsRect().right()
    )


def test_timeline_keeps_playback_and_overflows_secondary_options(qtbot) -> None:
    panel = TimelineWidget()
    _show_narrow(qtbot, panel)

    assert not panel.btn_play_pause.isHidden()
    assert (
        panel.chk_snap_playhead_to_events in panel.action_toolbar.overflowed_buttons()
    )


def test_project_panel_keeps_new_menu_available_at_narrow_width(qtbot) -> None:
    panel = UnifiedListWidget()
    panel.setStyleSheet(
        ThemeManager().format_stylesheet(
            Path("src/resources/main.qss").read_text(encoding="utf-8")
        )
    )
    _show_narrow(qtbot, panel, width=150)

    assert not panel.btn_new.isHidden()
    assert panel.btn_refresh in panel.action_toolbar.overflowed_buttons()
    assert panel.btn_new.width() >= panel.btn_new.sizeHint().width()


def test_project_filters_keep_selectors_and_overflow_actions(qtbot) -> None:
    panel = UnifiedListWidget()
    panel.setStyleSheet(
        ThemeManager().format_stylesheet(
            Path("src/resources/main.qss").read_text(encoding="utf-8")
        )
    )
    _show_narrow(qtbot, panel, width=300)
    panel.filter_action_toolbar.refresh()

    assert not panel.filter_combo.isHidden()
    assert not panel.sort_combo.isHidden()
    toolbar = panel.filter_action_toolbar
    for button in (
        panel.btn_filter,
        panel.btn_sort_dir,
        panel.btn_hashed_colors,
        panel.btn_clear_filters,
    ):
        assert button.isVisibleTo(panel) or button in toolbar.overflowed_buttons()
    # The production panel retains complete controls on a scrollable page.
    # Compare geometry in that page's coordinates, then exercise the visible route.
    scroll = panel.controls_scroll
    page = scroll.widget()
    right = toolbar.mapTo(page, QPoint(toolbar.width() - 1, 0)).x()
    assert right <= page.contentsRect().right()
    assert scroll.viewport().width() <= panel.width()
    scroll.ensureWidgetVisible(toolbar.overflow_button)
    qtbot.waitUntil(
        lambda: scroll.viewport()
        .rect()
        .contains(
            toolbar.overflow_button.mapTo(
                scroll.viewport(), toolbar.overflow_button.rect().center()
            )
        )
    )


def test_graph_filters_fit_one_compact_row_and_overflow_actions(qtbot) -> None:
    host = GraphWidget()
    bar = host._filter_bar
    host.setStyleSheet(
        ThemeManager().format_stylesheet(
            Path("src/resources/main.qss").read_text(encoding="utf-8")
        )
    )
    qtbot.addWidget(host)
    host.resize(530, 500)
    host.show()
    qtbot.wait(1)
    bar.action_toolbar.refresh()

    assert bar.width() == host.width() - 2 * WORKSPACE_CONTENT_INSET
    from scripts.action_label_audit import audit_widget

    qtbot.waitUntil(lambda: not audit_widget(host))
    assert bar._tag_filter_label.isHidden()
    assert not bar._search_input.isHidden()
    assert not bar._tag_combo.isHidden()
    assert not bar._rel_type_combo.isHidden()
    assert not bar._refresh_btn.isHidden()
    assert bar.action_toolbar.overflowed_buttons()
    assert bar.minimumSizeHint().width() <= 530


def test_history_keeps_undo_and_overflows_clear_at_narrow_width(qtbot) -> None:
    panel = HistoryPanelWidget()
    _show_narrow(qtbot, panel, width=150)

    assert not panel.undo_btn.isHidden()
    assert panel.clear_btn in panel.action_toolbar.overflowed_buttons()


def test_analysis_tab_scrollers_are_themed_and_aligned(qtbot) -> None:
    template = Path("src/resources/main.qss").read_text(encoding="utf-8")
    panel = MainAnalysisPanel()
    panel.setStyleSheet(ThemeManager().format_stylesheet(template))
    _show_narrow(qtbot, panel, width=220)
    tab_bar = panel.tab_widget.tabBar()
    scroll_buttons = {
        button.objectName(): button for button in tab_bar.findChildren(QToolButton)
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
