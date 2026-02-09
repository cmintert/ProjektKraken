"""
Unit tests for WikiTextEdit Focus Mode functionality.
"""

import pytest
from PySide6.QtCore import Qt

from src.gui.widgets.wiki_text_edit import WikiTextEdit


def test_focus_button_exists(qtbot):
    """Test that focus button is created and visible."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    
    # Button should exist and be visible
    assert hasattr(widget.editor, 'btn_focus')
    assert widget.editor.btn_focus.isVisible()


def test_focus_button_properties(qtbot):
    """Test that focus button has correct properties."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    
    # Check button properties
    assert widget.btn_focus.text() == "FC"
    assert widget.btn_focus.toolTip() == "Toggle Focus Mode"
    assert widget.btn_focus.isCheckable()
    assert widget.btn_focus.width() == 30
    assert widget.btn_focus.height() == 24


def test_focus_mode_initial_state(qtbot):
    """Test that focus mode starts inactive."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    
    assert widget._focus_mode_active is False
    assert widget.btn_focus.isChecked() is False


def test_focus_button_click_emits_signal(qtbot):
    """Test that clicking focus button emits signal with correct value."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    
    # Initially unchecked
    assert not widget.btn_focus.isChecked()
    
    # Click to activate
    with qtbot.waitSignal(widget.focus_mode_changed) as blocker:
        widget.btn_focus.click()
    
    assert blocker.args == [True]
    assert widget._focus_mode_active is True
    assert widget.btn_focus.isChecked() is True


def test_focus_button_toggle_emits_false(qtbot):
    """Test that toggling off emits False."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    
    # First activate
    widget.btn_focus.click()
    assert widget._focus_mode_active is True
    
    # Then deactivate
    with qtbot.waitSignal(widget.focus_mode_changed) as blocker:
        widget.btn_focus.click()
    
    assert blocker.args == [False]
    assert widget._focus_mode_active is False
    assert widget.btn_focus.isChecked() is False


def test_focus_signal_forwarded_to_wrapper(qtbot):
    """Test that focus_mode_changed signal is forwarded from editor to wrapper."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    
    # Signal should be emitted from both editor and wrapper
    with qtbot.waitSignal(widget.focus_mode_changed) as blocker:
        widget.editor.btn_focus.click()
    
    assert blocker.args == [True]


def test_buttons_stacked_vertically(qtbot):
    """Test that buttons are positioned vertically with spacing."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    
    # Get button positions
    md_pos = widget.btn_toggle_view.pos()
    focus_pos = widget.btn_focus.pos()
    
    # Same X coordinate (vertically aligned)
    assert md_pos.x() == focus_pos.x()
    
    # Focus button below MD button
    assert focus_pos.y() > md_pos.y()
    
    # Check spacing (should be about 4px plus button height)
    spacing = focus_pos.y() - md_pos.y()
    expected_spacing = widget.btn_toggle_view.height() + 4
    assert spacing == expected_spacing


def test_buttons_positioned_right_aligned(qtbot):
    """Test that buttons are aligned to the right side."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    
    # Buttons should be near the right edge
    # Expected: width - button_width - padding_right - scrollbar_width
    expected_x = 400 - 30 - 5 - 15  # 350
    md_pos = widget.btn_toggle_view.pos()
    
    assert md_pos.x() == expected_x


def test_buttons_have_shared_stylesheet(qtbot):
    """Test that both buttons use the same stylesheet."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    
    md_style = widget.btn_toggle_view.styleSheet()
    focus_style = widget.btn_focus.styleSheet()
    
    # Should have the same style
    assert md_style == focus_style
    
    # Should contain dynamic transparency values
    assert "rgba(50, 50, 50, 40)" in md_style
    assert "rgba(80, 80, 80, 240)" in md_style
    assert "rgba(255, 153, 0, 200)" in md_style


def test_focus_button_checked_state_styling(qtbot):
    """Test that checked state applies the correct styling."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    
    # Check that stylesheet includes checked state
    style = widget.btn_focus.styleSheet()
    assert ":checked" in style
    assert "rgba(255, 153, 0, 200)" in style  # Orange active state


def test_focus_mode_toggle_programmatic(qtbot):
    """Test programmatic toggle of focus mode."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    
    # Call toggle_focus_mode directly
    widget.editor.btn_focus.setChecked(True)
    
    with qtbot.waitSignal(widget.focus_mode_changed) as blocker:
        widget.editor.toggle_focus_mode()
    
    assert blocker.args == [True]
    assert widget._focus_mode_active is True


def test_resize_maintains_button_positions(qtbot):
    """Test that resizing maintains vertical button stack."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    
    # Initial size
    widget.resize(400, 300)
    initial_md_pos = widget.btn_toggle_view.pos()
    initial_focus_pos = widget.btn_focus.pos()
    
    # Resize
    widget.resize(600, 400)
    new_md_pos = widget.btn_toggle_view.pos()
    new_focus_pos = widget.btn_focus.pos()
    
    # X should change (move right), Y should stay the same
    assert new_md_pos.x() > initial_md_pos.x()
    assert new_md_pos.y() == initial_md_pos.y()
    
    # Vertical spacing should be maintained
    initial_spacing = initial_focus_pos.y() - initial_md_pos.y()
    new_spacing = new_focus_pos.y() - new_md_pos.y()
    assert initial_spacing == new_spacing
