import pytest
from src.gui.widgets.unified_list import UnifiedListWidget
from src.gui.utils.shortcut_manager import ShortcutManager


@pytest.fixture
def unified_list(qtbot):
    widget = UnifiedListWidget()
    qtbot.addWidget(widget)
    # Ensure it's visible for shortcuts to work if needed (though programmatic check doesn't strictly need it)
    return widget


def test_shortcuts_configured(unified_list):
    """Test that shortcuts are correctly assigned to actions."""
    # Find the actions
    create_event_action = None
    create_entity_action = None
    create_map_action = None

    # Access actions stored as attributes
    if hasattr(unified_list, "action_create_event"):
        create_event_action = unified_list.action_create_event
    if hasattr(unified_list, "action_create_entity"):
        create_entity_action = unified_list.action_create_entity
    if hasattr(unified_list, "action_create_map"):
        create_map_action = unified_list.action_create_map

    assert create_event_action is not None
    assert create_entity_action is not None
    assert create_map_action is not None

    # Check sequences
    assert create_event_action.shortcut() == ShortcutManager.CREATE_EVENT.key_sequence
    assert create_entity_action.shortcut() == ShortcutManager.CREATE_ENTITY.key_sequence
    assert create_map_action.shortcut() == ShortcutManager.CREATE_MAP.key_sequence


def test_new_button_tooltip(unified_list):
    """Test that the New button tooltip contains shortcut info."""
    tooltip = unified_list.btn_new.toolTip()
    assert ShortcutManager.CREATE_EVENT.tooltip in tooltip
    assert ShortcutManager.CREATE_ENTITY.tooltip in tooltip
    assert ShortcutManager.CREATE_MAP.tooltip in tooltip
    assert "Ctrl+E" in tooltip
    assert "Ctrl+I" in tooltip
    assert "Ctrl+M" in tooltip


def test_widgets_actions_count(unified_list):
    """Test that actions are added to the widget itself."""
    actions = unified_list.actions()
    assert unified_list.action_create_event in actions
    assert unified_list.action_create_entity in actions
    assert unified_list.action_create_map in actions
