"""Unit tests for EmptyStateWidget."""

import pytest

from src.gui.widgets.empty_state_widget import EmptyStateWidget


@pytest.fixture
def empty_state(qtbot):
    """Create EmptyStateWidget for testing."""
    widget = EmptyStateWidget(
        title="Test Title",
        description="Test description text.",
    )
    qtbot.addWidget(widget)
    return widget


def test_init_hidden_by_default(qtbot):
    """Test widget is hidden by default."""
    widget = EmptyStateWidget()
    qtbot.addWidget(widget)
    assert widget.isHidden()


def test_init_with_title_and_description(empty_state):
    """Test widget shows title and description."""
    assert empty_state._title_label.text() == "Test Title"
    assert empty_state._description_label.text() == "Test description text."
    assert not empty_state._description_label.isHidden()


def test_init_no_description(qtbot):
    """Test widget hides description label when empty."""
    widget = EmptyStateWidget(title="Title Only")
    qtbot.addWidget(widget)
    assert widget._description_label.isHidden()


def test_set_message(empty_state):
    """Test updating the title message."""
    empty_state.set_message("New Title")
    assert empty_state._title_label.text() == "New Title"


def test_set_description(empty_state):
    """Test updating the description."""
    empty_state.set_description("New description")
    assert empty_state._description_label.text() == "New description"
    assert not empty_state._description_label.isHidden()


def test_set_description_empty_hides_label(empty_state):
    """Test clearing the description hides the label."""
    empty_state.set_description("")
    assert empty_state._description_label.isHidden()


def test_add_action_primary(empty_state, qtbot):
    """Test adding a primary action button."""
    callback_called = []
    button = empty_state.add_action(
        "Primary Action", lambda: callback_called.append(True), primary=True
    )
    assert button.text() == "Primary Action"

    button.click()
    assert len(callback_called) == 1


def test_add_action_secondary(empty_state, qtbot):
    """Test adding a secondary action button."""
    callback_called = []
    button = empty_state.add_action(
        "Secondary Action", lambda: callback_called.append(True), primary=False
    )
    assert button.text() == "Secondary Action"

    button.click()
    assert len(callback_called) == 1


def test_add_multiple_actions(empty_state):
    """Test adding multiple action buttons."""
    btn1 = empty_state.add_action("Action 1", lambda: None, primary=True)
    btn2 = empty_state.add_action("Action 2", lambda: None, primary=False)
    btn3 = empty_state.add_action("Action 3", lambda: None)

    assert empty_state._button_layout.count() == 3
    assert btn1.text() == "Action 1"
    assert btn2.text() == "Action 2"
    assert btn3.text() == "Action 3"


def test_show_hide(empty_state):
    """Test show/hide visibility toggling."""
    assert empty_state.isHidden()
    empty_state.show()
    assert not empty_state.isHidden()
    empty_state.hide()
    assert empty_state.isHidden()
