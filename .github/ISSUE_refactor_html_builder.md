# refactor: extract HTML builder utility for reuse across widgets

## Problem

Multiple widgets in the codebase hand-roll HTML construction using the same pattern:

1. Create empty list: `html_parts = []`
2. Append HTML fragments in a loop
3. Join and pass to `setHtml()`

**Locations:**
- src/gui/widgets/_analysis_utils.py:91-100 (format_lore_suggestions_html)
- src/gui/widgets/timeline_display_widget.py:130-225
- src/gui/widgets/longform/content.py:108-170

## Solution

Create a reusable HTMLBuilder utility class at src/gui/utils/html_builder.py:

```python
class HTMLBuilder:
    """Fluent HTML builder for QTextBrowser content."""
    
    def add_divider(self, margin: str = "8px 0") -> Self:
        self._parts.append(f"<hr style='margin: {margin}; border: 1px solid #999;' />")
        return self
    
    def add_bold(self, text: str) -> Self:
        self._parts.append(f"<b>{html.escape(text)}</b><br/>")
        return self
    
    def add_italic(self, text: str) -> Self:
        if text:
            self._parts.append(f"<i>{html.escape(text)}</i><br/>")
        return self
    
    def add_text(self, text: str) -> Self:
        if text:
            self._parts.append(html.escape(text))
        return self
    
    def build(self) -> str:
        return "".join(self._parts)
```

## Refactoring
Update each widget to use the builder:
- format_lore_suggestions_html() → 3 LOC
- timeline_display_widget.py → simplified HTML assembly
- longform/content.py → simplified HTML assembly

## Benefits
- DRY: single source of truth for HTML escaping, formatting, dividers
- Fluent API: easier to read and maintain
- Extensibility: add new styled elements without modifying each caller

## Priority
Medium - improves code quality and maintainability but not user-facing
