"""Tests for color utilities."""

from PySide6.QtGui import QColor

from src.gui.utils.color_utils import get_hashed_color


def test_get_hashed_color_is_deterministic():
    """Test that the same string always yields the same color."""
    color1 = get_hashed_color("Chapter 1")
    color2 = get_hashed_color("Chapter 1")

    assert color1.name() == color2.name()
    assert color1.alpha() == color2.alpha()


def test_get_hashed_color_differs_by_string():
    """Test that different strings yield different colors."""
    color1 = get_hashed_color("Chapter 1")
    color2 = get_hashed_color("Chapter 2")

    assert color1.name() != color2.name()


def test_get_hashed_color_is_valid_qcolor():
    """Test that the returned object is a valid QColor."""
    color = get_hashed_color("Test")
    assert isinstance(color, QColor)
    assert color.isValid()
