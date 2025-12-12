import sys
from PySide6.QtWidgets import QApplication
from src.core.theme_manager import ThemeManager
from src.gui.widgets.wiki_text_edit import WikiTextEdit


def test_rendering():
    app = QApplication(sys.argv)

    # 1. Setup Theme
    tm = ThemeManager()
    print(f"Current Theme: {tm.current_theme_name}")

    # Force reload to be sure we get disk changes
    tm._load_themes()
    tm.set_theme("fantasy_mode")

    theme = tm.get_theme()
    print(f"Active Theme Keys: {list(theme.keys())}")
    print(f"H1 Size in Theme: {theme.get('font_size_h1')}")

    # 2. Setup Widget
    editor = WikiTextEdit()
    editor.set_wiki_text("# My Big Header\n\nSome body text.")

    # 3. Inspect
    doc_css = editor.document().defaultStyleSheet()
    print("\n--- Document CSS ---")
    print(doc_css)

    html = editor.toHtml()
    print("\n--- Generated HTML ---")
    # Just print the first few lines or grep for font-size
    print(html[:500])

    # Check for 30pt match
    if "30pt" in doc_css:
        print("\nSUCCESS: '30pt' found in CSS.")
    else:
        print("\nFAILURE: '30pt' NOT found in CSS.")


if __name__ == "__main__":
    test_rendering()
