#!/usr/bin/env python
"""
Quick test to verify font sizes in longform document.
"""

import sys
from PySide6.QtWidgets import QApplication
from src.gui.widgets.longform_editor import LongformContentWidget
from src.core.theme_manager import ThemeManager

def test_font_sizes():
    app = QApplication(sys.argv)
    
    # Initialize theme manager
    tm = ThemeManager()
    theme = tm.get_theme()
    
    print("Current theme:", tm.current_theme_name)
    print("Font sizes from theme:")
    print(f"  h1: {theme.get('font_size_h1')}")
    print(f"  h2: {theme.get('font_size_h2')}")
    print(f"  h3: {theme.get('font_size_h3')}")
    print(f"  body: {theme.get('font_size_body')}")
    
    # Create content widget
    widget = LongformContentWidget()
    
    # Load some test content
    sequence = [
        {
            "table": "events",
            "id": "test-1",
            "name": "Test Event",
            "heading_level": 1,
            "content": "This is some test content.",
            "meta": {}
        },
        {
            "table": "events",
            "id": "test-2",
            "name": "Sub Event",
            "heading_level": 2,
            "content": "This is sub content.",
            "meta": {}
        }
    ]
    
    widget.load_content(sequence)
    
    # Check the stylesheet
    stylesheet = widget.document().defaultStyleSheet()
    print("\nDocument stylesheet:")
    print(stylesheet)
    
    # Check if font sizes are in the stylesheet
    if "font-size: 14pt" in stylesheet:
        print("\n✓ Font sizes appear to be applied")
    else:
        print("\n✗ Font sizes NOT found in stylesheet")
    
    widget.show()
    widget.resize(800, 600)
    
    # Don't run the event loop, just check
    # app.exec()

if __name__ == "__main__":
    test_font_sizes()
