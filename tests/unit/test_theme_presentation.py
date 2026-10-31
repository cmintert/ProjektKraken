"""Visible-first theme scopes preserve pixels, ownership and hidden-view freshness."""

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton, QVBoxLayout, QWidget

from src.core.theme_manager import ThemeManager
from src.gui.utils.theme_connections import connect_theme, disconnect_theme
from src.gui.utils.theme_presentation import (
    register_theme_scope,
)
from src.gui.utils.theme_stylesheet import compile_theme_stylesheet

pytestmark = pytest.mark.ci_fast


def test_shipped_sheet_compiles_without_theme_colors_in_fixed_metrics():
    pack = compile_theme_stylesheet(Path("src/resources/main.qss").read_text("utf-8"))
    assert "__kraken_token_" not in pack.metrics
    assert "font-family" in pack.metrics
    for theme in ThemeManager().themes.values():
        rendered = pack.render(theme)
        assert "__kraken_token_" not in rendered
        assert theme["surface"] in rendered


def test_color_compiler_keeps_urls_and_rejects_unknown_theme_dependencies():
    pack = compile_theme_stylesheet(
        'QWidget {{ image: url("a;b.png"); color: {text_main}; }}'
    )
    assert 'url("a;b.png")' in pack.metrics
    with pytest.raises(ValueError, match="Unclassified"):
        compile_theme_stylesheet("QWidget {{ margin: {unexpected}; }}")


def test_visible_switch_never_replaces_global_metrics(qapp, qtbot, theme_presentation):
    widget = QDialog()
    layout = QVBoxLayout(widget)
    field = QLineEdit("A name")
    layout.addWidget(field)
    qtbot.addWidget(widget)
    widget.resize(500, 200)
    widget.show()
    qapp.processEvents()
    fixed = qapp.styleSheet()
    with patch.object(qapp, "setStyleSheet", wraps=qapp.setStyleSheet) as global_style:
        for name, theme in ThemeManager().themes.items():
            ThemeManager().set_theme(name, persist=False)
            qapp.processEvents()
            image = field.grab().toImage()
            assert (
                image.pixelColor(image.width() - 10, image.height() // 2).name()
                == theme["surface"].lower()
            )
            assert (
                widget.grab().toImage().pixelColor(2, 2).name()
                == theme["app_bg"].lower()
            )
        global_style.assert_not_called()
    assert qapp.styleSheet() == fixed


def test_hidden_subscriptions_coalesce_and_refresh_before_first_paint(
    qapp, qtbot, theme_presentation
):
    widget = QWidget()
    qtbot.addWidget(widget)
    register_theme_scope(widget)
    observed = []
    connect_theme(widget, lambda theme: observed.append(theme["app_bg"]))
    ThemeManager().set_theme("light_mode", persist=False)
    ThemeManager().set_theme("cyberpunk_mode", persist=False)
    assert not observed
    widget.show()
    assert observed == [ThemeManager().get_theme()["app_bg"]]
    qapp.processEvents()
    assert ThemeManager().get_theme()["app_bg"] in widget.styleSheet()


def test_hidden_root_local_style_does_not_erase_current_colors_on_show(
    qapp, qtbot, theme_presentation
):
    widget = QDialog()
    layout = QVBoxLayout(widget)
    button = QPushButton("Ordinary action")
    layout.addWidget(button)
    qtbot.addWidget(widget)
    connect_theme(widget, lambda _: widget.setStyleSheet("QDialog { padding: 3px; }"))
    ThemeManager().set_theme("light_mode", persist=False)
    widget.show()
    qapp.processEvents()
    assert "padding: 3px" in widget.styleSheet()
    assert ThemeManager().get_theme()["surface"] in widget.styleSheet()
    assert widget.styleSheet().count("Kraken scoped theme begin") == 1


def test_declaration_only_panel_style_keeps_its_local_surface(
    qapp, qtbot, theme_presentation
):
    widget = QDialog()
    qtbot.addWidget(widget)
    layout = QVBoxLayout(widget)
    field = QLineEdit()
    layout.addWidget(field)

    def local_surface(theme):
        widget.setStyleSheet(f"background-color: {theme['surface']};")

    connect_theme(widget, local_surface)
    widget.show()
    for name in ThemeManager().themes:
        ThemeManager().set_theme(name, persist=False)
        qapp.processEvents()
        assert (
            widget.grab().toImage().pixelColor(2, 2).name()
            == ThemeManager().get_theme()["surface"].lower()
        )
        assert (
            field.grab().toImage().pixelColor(10, 10).name()
            == ThemeManager().get_theme()["surface"].lower()
        )


def test_disconnected_hidden_subscriber_is_not_called(qapp, qtbot, theme_presentation):
    widget = QWidget()
    qtbot.addWidget(widget)
    values = []

    def callback(theme):
        values.append(theme)

    connect_theme(widget, callback)
    ThemeManager().set_theme("light_mode", persist=False)
    disconnect_theme(widget, callback)
    qapp.processEvents()
    widget.show()
    qapp.processEvents()
    assert not values


def _scopes(qapp, qtbot, runtime):
    settings, panel = QDialog(), QDialog()
    for widget in (settings, panel):
        qtbot.addWidget(widget)
        widget.resize(300, 200)
        widget.show()
    runtime.register(settings, priority=True)
    runtime.register(panel)
    qapp.processEvents()
    return settings, panel


def test_settings_paints_before_deferred_visible_panel(qapp, qtbot, theme_presentation):
    runtime = theme_presentation
    settings, panel = _scopes(qapp, qtbot, runtime)
    observations = []
    settings_painted = []

    class PaintObserver(QObject):
        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.Paint:
                settings_painted.append(runtime._scope_for(settings).generation)
            return False

    observer = PaintObserver(settings)
    settings.installEventFilter(observer)
    connect_theme(panel, lambda _: observations.append(bool(settings_painted)))
    ThemeManager().set_theme("light_mode", persist=False)
    assert runtime.is_pending
    assert not observations
    assert runtime._scope_for(settings).generation == runtime._generation
    qtbot.waitUntil(lambda: not runtime.is_pending)
    assert observations == [True]
    assert settings_painted[0] == runtime._generation
    assert (
        panel.grab().toImage().pixelColor(2, 2).name()
        == ThemeManager().get_theme()["app_bg"].lower()
    )


def test_rapid_switch_replaces_queued_generation_and_hidden_refresh(
    qapp, qtbot, theme_presentation
):
    runtime = theme_presentation
    settings, panel = _scopes(qapp, qtbot, runtime)
    observed = []
    connect_theme(panel, lambda theme: observed.append(theme["surface"]))
    ThemeManager().set_theme("light_mode", persist=False)
    ThemeManager().set_theme("fantasy_mode", persist=False)
    panel.hide()
    ThemeManager().set_theme("cyberpunk_mode", persist=False)
    qtbot.waitUntil(lambda: not runtime.is_pending)
    assert not observed
    panel.show()
    assert observed == [ThemeManager().get_theme()["surface"]]
    assert runtime._scope_for(panel).generation == runtime._generation
    assert (
        panel.grab().toImage().pixelColor(2, 2).name()
        == ThemeManager().get_theme()["app_bg"].lower()
    )


def test_ok_hide_and_destroyed_scopes_do_not_strand_work(
    qapp, qtbot, theme_presentation
):
    runtime = theme_presentation
    settings, panel = _scopes(qapp, qtbot, runtime)
    observed = []
    connect_theme(panel, lambda _: observed.append("current"))
    ThemeManager().set_theme("light_mode", persist=False)
    settings.hide()
    assert observed == ["current"]
    qtbot.waitUntil(lambda: not runtime.is_pending)
    settings.show()
    ThemeManager().set_theme("dark_mode", persist=False)
    panel.deleteLater()
    qtbot.waitUntil(lambda: not runtime.is_pending)
    runtime.close()
    assert not runtime.is_pending


def test_scene_objects_follow_hidden_view_visibility(qapp, qtbot, theme_presentation):
    from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

    scene = QGraphicsScene()
    view = QGraphicsView(scene)
    qtbot.addWidget(view)
    register_theme_scope(view)
    observed = []
    connect_theme(scene, lambda _: observed.append("current"))
    ThemeManager().set_theme("light_mode", persist=False)
    assert not observed
    view.show()
    assert observed == ["current"]


def test_item_model_parent_overload_keeps_qobject_ownership(
    qapp, qtbot, theme_presentation
):
    from PySide6.QtCore import QAbstractListModel, QModelIndex

    class Model(QAbstractListModel):
        def rowCount(self, parent=QModelIndex()):
            return 0

    widget = QDialog()
    qtbot.addWidget(widget)
    model = Model(widget)
    observed = []
    connect_theme(model, lambda _: observed.append("current"))
    ThemeManager().set_theme("light_mode", persist=False)
    assert not observed
    widget.show()
    assert observed == ["current"]


@pytest.mark.parametrize("point_size", (10, 15, 20))
@pytest.mark.parametrize("kind", ("push", "tool"))
def test_actual_scaled_action_font_and_complete_label_survive_all_themes(
    qapp, qtbot, theme_presentation, point_size, kind
):
    from src.gui.utils.action_label_metrics import action_label_geometry
    from src.gui.utils.style_helper import StyleHelper
    from src.gui.widgets.standard_buttons import LabelSizedToolButton, StandardButton

    root = QDialog()
    qtbot.addWidget(root)
    button = StandardButton(root) if kind == "push" else LabelSizedToolButton(root)
    if isinstance(button, LabelSizedToolButton):
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    button.setText("Apply all theme changes")
    selector = "QPushButton" if kind == "push" else "QToolButton"

    def style(_theme):
        button.setStyleSheet(
            StyleHelper.get_action_role_style("secondary", selector)
            + f"{selector} {{ font-size: {point_size}pt; }}"
        )

    connect_theme(button, style)
    button.setFont(QFont("Segoe UI", point_size))
    root.show()
    for name in ThemeManager().themes:
        ThemeManager().set_theme(name, persist=False)
        qapp.processEvents()
        button.resize(button.sizeHint())
        assert button.font().pointSizeF() == point_size
        assert action_label_geometry(button).fits


def test_new_native_tooltip_uses_current_scope_colors(qapp, qtbot, theme_presentation):
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QToolTip

    widget = QDialog()
    qtbot.addWidget(widget)
    widget.show()
    qapp.processEvents()
    for name in ThemeManager().themes:
        ThemeManager().set_theme(name, persist=False)
        QToolTip.showText(QPoint(20, 20), f"Current theme explanation: {name}", widget)
        qapp.processEvents()
        tips = [
            candidate
            for candidate in qapp.topLevelWidgets()
            if candidate.windowType() == Qt.WindowType.ToolTip and candidate.isVisible()
        ]
        assert tips, (name, QToolTip.isVisible())
        image = tips[0].grab().toImage()
        assert (
            image.pixelColor(5, 5).name()
            == ThemeManager().get_theme()["surface"].lower()
        )
    QToolTip.hideText()
