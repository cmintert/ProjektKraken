# KRT-80 writing-column evidence

Captured 2026-10-10 with the isolated Qt inspector renderer. The 24 PNGs cover
Entity and Event Overview, with writing panels closed and open, at requested
360, 800 and 1200 px widths in light and dark themes. The open-panel captures
put keyboard focus on Summary. The renderer uses the production stylesheet and
font, but no database or personal world. Exact environment, source hashes,
geometry and scroll measurements are in [captures.json](captures.json).

| Inspector width | Overview content | Writing column | Side gutters | Horizontal scroll |
| --- | ---: | ---: | ---: | ---: |
| 360 px | 324 px | 302 px | 11 / 11 px | 0 |
| 800 px | 764 px | 734 px | 15 / 15 px | 0 |
| 1200 px | 1164 px | 760 px | 202 / 202 px | 0 |

These measurements hold for both editors and themes. At 1200 px the column is
bounded and centered; at 360 px it uses nearly all available width. The toolbar,
visible editor and writing actions share the column's left edge. The prose stays
left-aligned. The expanded Summary/AI controls wrap within the same width.
Event timing and History & context retain their separate Overview layout.

Visual examples: [wide Entity, light](entity-light_mode-1200-overview.png),
[normal Event, light](event-light_mode-800-overview.png),
[narrow Entity, dark](entity-dark_mode-360-overview.png), and
[narrow Event with panels open, dark](event-dark_mode-360-writing_panels.png).

The implementation reuses the live wiki editor, its splitter object, and shared
supporting-action styles. The empty splitter pane is hidden in the bounded
column so the visible text surface fills it. Focus writing still moves and
restores the same editor/document. Contracts 1, 3, 5, 6, 7, 8 and 9 apply;
Overview remains the visible route, multiline Enter remains with the editor,
and no exception or contract revision is introduced. Supporting/AI controls
retain neutral roles; focus and disabled states use existing StyleHelper rules.

This is rendered layout evidence, not a human task comparison. KRT-45/KRT-81
retain the matched benchmark acceptance.
