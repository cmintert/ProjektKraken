"""Theme-event floods must not trigger authoring context resolution."""

from unittest.mock import patch

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QWidget

from src.app.main_window import GlobalShortcutFilter
from tests.unit import test_help_coordinator as help_tests

generated_root = help_tests.generated_root
help_setup = help_tests.help_setup
focus_setup = help_tests.focus_setup
pytestmark = pytest.mark.ci_fast

THEME_EVENTS = (
    QEvent.Type.StyleChange,
    QEvent.Type.PaletteChange,
    QEvent.Type.FontChange,
    QEvent.Type.LayoutRequest,
    QEvent.Type.PolishRequest,
    QEvent.Type.UpdateRequest,
)


@pytest.mark.parametrize("event_type", THEME_EVENTS)
def test_global_shortcuts_ignore_theme_events_before_context(qapp, event_type):
    owner = QWidget()
    receiver = QWidget(owner)
    shortcut_filter = GlobalShortcutFilter(owner)
    with patch("src.app.main_window.owns_assistance_input") as context:
        assert not shortcut_filter.eventFilter(receiver, QEvent(event_type))
        context.assert_not_called()
    owner.deleteLater()


@pytest.mark.parametrize("event_type", THEME_EVENTS)
def test_help_filters_ignore_theme_events_before_context(help_setup, event_type):
    coordinator, _, _, _, text = help_setup
    with patch.object(coordinator, "belongs") as context:
        assert not coordinator.eventFilter(text, QEvent(event_type))
        assert not coordinator.inspection.eventFilter(text, QEvent(event_type))
        context.assert_not_called()


@pytest.mark.parametrize("active", [False, True])
def test_focus_writing_theme_flood_does_not_resolve_help(focus_setup, active):
    _, editor, controller = focus_setup
    if active:
        controller.enter(editor)
    with patch("src.gui.utils.help_context.owns_assistance_input") as context:
        for _ in range(100):
            for event_type in THEME_EVENTS:
                assert not controller.eventFilter(editor, QEvent(event_type))
        context.assert_not_called()
    assert (controller.active is editor) == active
