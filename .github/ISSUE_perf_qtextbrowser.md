# perf: reduce QTextBrowser widget instantiation in intelligence panel lore table

## Problem

The lore suggestions table in IntelligencePanel currently creates a new QTextBrowser widget for each row (N+1 instantiation). For large reports with many lore suggestions, this causes noticeable UI stall during table population.

**Current Pattern** (src/gui/widgets/intelligence_panel.py:210-214):
```python
for row, filler in enumerate(report.lore_suggestions):
    browser = QTextBrowser()  # Creates widget per row
    browser.setHtml(format_lore_suggestions_html(filler.suggestions))
    browser.setReadOnly(True)
    browser.setFrameShape(QFrame.Shape.NoFrame)
    self.lore_table.setCellWidget(row, 2, browser)
```

QTextBrowser is a heavy widget with HTML parsing, scrolling, text selection, and event handling overhead.

## Solutions

### Option A: Use QStyledItemDelegate
Render HTML to QTextDocument without creating per-row widgets. Delegate handles rendering at paint time.

### Option B: Widget Pool + Data Binding
Reuse a small pool of QTextBrowser widgets and bind them to cell data via a model.

### Option C: Detail Pane Pattern
Move HTML rendering to a separate detail pane that shows when a row is selected, rather than embedding in cells.

## Testing
- Profile table population time with 100+ lore suggestions
- Verify rendering quality matches current approach
- Measure memory usage before/after

## Related
- Similar widgets: timeline_display_widget.py, graph_view widgets
- Affects: IntelligencePanel.display_report() hot path
