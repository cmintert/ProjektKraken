"""Keyboard and state clarity for opt-in generation in composed settings."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.gui.widgets.mcp_access_widget import McpAccessWidget
from src.gui.widgets.settings_center import SettingsCenter

pytestmark = pytest.mark.ci_fast


@pytest.mark.parametrize("theme,width", [("dark_mode", 520), ("light_mode", 960)])
def test_experiment_scope_in_composed_settings(
    qtbot, isolated_theme_manager, theme, width
):
    isolated_theme_manager.set_theme(theme)
    center = SettingsCenter()
    qtbot.addWidget(center)
    form = McpAccessWidget(center)
    center.add_page("kraken", "Integrations", form)
    center.navigate("integrations.mcp")
    form.scope_details.setChecked(True)
    state = {
        "state": "Off",
        "world_name": "Test",
        "message": "",
        "available": True,
        "activity": [],
        "scopes": [],
    }
    form.render_state(state)
    center.resize(width, 850)
    center.show()
    center.activateWindow()
    box = form.scope_boxes["generation"]
    box.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() == box)
    assert box.isVisibleTo(center)
    qtbot.keyClick(box, Qt.Key.Key_Space)
    assert box.isChecked()
    form.render_state(
        {
            **state,
            "state": "Active",
            "scopes": ["generation"],
        }
    )
    assert not box.isEnabled()
    assert "remaining" not in form.status.text()
