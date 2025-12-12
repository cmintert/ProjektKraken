# Qt Rich Text Styling: CSS Application Gotchas

## Problem Summary

When using Qt's `QTextEdit` with rich text (HTML), applying CSS styles via `document().setDefaultStyleSheet()` does **not reliably work** for dynamically changing content.

## Symptoms

- Font sizes defined in `themes.json` were correctly read and logged
- CSS was being generated with the correct values (verified via DEBUG logs)
- However, the rendered content did not reflect the CSS styles
- Theme switching had no visible effect on font sizes

## Root Cause

Qt's `QTextDocument.setDefaultStyleSheet()` sets a default CSS stylesheet for the document, but:

1. It does **not automatically re-apply** to already-rendered HTML content
2. Even calling it before `setHtml()` may not work reliably in all cases
3. The stylesheet is parsed separately from the HTML content

## Solution: Embed CSS Directly in HTML

Instead of using `setDefaultStyleSheet()`, embed the CSS directly in the HTML content using a `<style>` tag:

```python
# ❌ OLD APPROACH (unreliable)
self.document().setDefaultStyleSheet(css)
self.setHtml(html_content)

# ✅ NEW APPROACH (reliable)
html_with_css = f"<html><head><style>{css}</style></head><body>{html_content}</body></html>"
self.setHtml(html_with_css)
```

## Implementation Details

### Files Modified

- `src/gui/widgets/wiki_text_edit.py`:
  - Added `_get_theme_css()` method that returns the CSS string
  - Modified `set_wiki_text()` to wrap HTML in `<html><head><style>CSS</style></head><body>...</body></html>`
  - Added `body` selector to CSS for fallback styling
  - `_on_theme_changed()` re-renders content to apply new styles

### CSS Selectors Used

```css
a { color: ...; font-weight: bold; text-decoration: none; }
h1 { font-size: ...; font-weight: 600; color: ...; margin-top: 10px; margin-bottom: 5px; }
h2 { font-size: ...; font-weight: 600; color: ...; margin-top: 8px; margin-bottom: 4px; }
h3 { font-size: ...; font-weight: 600; color: ...; margin-top: 6px; margin-bottom: 3px; }
p { margin-bottom: 2px; color: ...; font-size: ...; }
body { color: ...; font-size: ...; }  /* Fallback for non-<p> text */
```

## Key Takeaways

1. **Always embed CSS in HTML** when using `QTextEdit.setHtml()` for reliable styling
2. **Store original content** (e.g., `_current_wiki_text`) to enable re-rendering on theme changes
3. **Add DEBUG logging** to trace theme loading, CSS generation, and content rendering
4. **Include a `body` selector** as fallback for text not wrapped in `<p>` tags

## Debugging Tips

Enable DEBUG logging to trace the styling pipeline:

```python
logger.debug(f"Building theme CSS. Current theme: {tm.current_theme_name}")
logger.debug(f"Font sizes from theme: h1={fs_h1}, h2={fs_h2}, h3={fs_h3}, body={fs_body}")
logger.debug(f"Setting HTML with embedded CSS (body length: {len(html_body)})")
```

Check logs for:
- Theme file being loaded correctly
- Font size values being read from theme
- CSS being generated with expected values
- HTML being set with embedded CSS

---

*Documented: 2025-12-12*
*Issue resolved in: WikiTextEdit, LongformContentWidget*
