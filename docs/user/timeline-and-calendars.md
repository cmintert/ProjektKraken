# Timeline and Calendars

## What this does

The Timeline places events along the world's history. The playhead represents
the current lore time and also controls time-sensitive map content.

## Use the timeline

- Scroll or use the zoom controls to change scale.
- Drag the view to move through time.
- Select an event to open its inspector.
- Move supported event items to update their date.
- Use the playhead controls to inspect another point in history.
- Choose **Set Current Time** to make the playhead position the world's current
  story time.
- Choose **Return to Current Time** to move the playhead back to the current
  story time without changing it.
- Enable **Snap to Events** to make manual playhead drags and ruler clicks land
  exactly on a nearby event date. Snapping uses a small on-screen distance, so
  it remains predictable at every zoom level. Playback and scripted jumps do
  not snap.

## Dates with incomplete information

Type `961`, `May 961`, or a complete calendar date. Saving and reopening keeps
the precision you entered. **Date fields…** allows month and day to remain
unspecified; Delete clears the selected component. Choosing a month or day
intentionally adds that detail.

Use `c. 961`, `961?`, `before 961`, `after 961`, or `between 959 and 963` when
appropriate. Date qualification is also available under **Date fields…**.
An approximate or uncertain date does not establish hard limits by itself.
The explicit `between`, `before`, `after`, and `by` forms supply bounds.

A bare range such as `961–964` asks whether the event occurred sometime within
that range or lasted from one endpoint to the other. An occurrence window
does not become a duration. A duration retains the precision of both dates.

The timeline uses a representative position for dragging partial dates, but
does not draw an asserted start there. Dotted outlines show possible dates on
the event's track. For durations, hatching shows possible presence and a solid
interior marks only the period when the event is certainly ongoing. A question
mark indicates timing without finite evidence bounds. Dragging keeps the date's
precision. Snapping to a representative position does not make that position
the event's exact historical date. A displayed span between partial endpoints
is a layout value, not an assertion of an exact number of elapsed days.

Existing numeric dates remain exact. Kraken does not reinterpret an old
January 1 date as a year-only assertion.

Leave **Event has duration** unchecked for a single occurrence sometime within
a year. Check it only when the event actually lasted over time. Clearing it
removes the duration without changing the date precision. An uncertain start
and known duration can coexist; the editor does not present their derived
midpoint end as an exact historical date.

## Group events

1. Open **Timeline → Configure Grouping…**.
2. Choose the tags used to form timeline bands.
3. Confirm the grouping.
4. Use **Timeline → Clear Grouping** to return to the ungrouped view.

Group labels can be renamed, recolored, or removed from the current grouping
through their context menu.

## Configure the calendar

Open **Timeline → Calendar Configuration…** to define the active calendar.
Calendar configuration controls how stored lore days are formatted throughout
the interface.

The timeline ruler marks actual calendar boundaries. Year and month ticks line
up with events dated to the first day of that year or month. Week ticks use the
calendar's week length. Quarter ticks appear in years with twelve months.

## Record sources and ordering

In an event, open **Date sources and chronology…** to add each source and its
date as a separate claim. Choose a preferred assertion to use that source's
date for the event. Removing or editing a claim preserves the other claims;
conflicting dates are never combined into one broad date range. A conflict
message distinguishes disjoint source dates from an ordinary year-only date.

The same dialog records **Before**, **After**, or **At the same transition**
relative to another event, with an optional minimum gap in lore days. Cyclic
ordering is rejected. These statements express known chronology without
inventing calendar precision.

Expand a date's fields and choose **Possible date limits…** to set explicit
occurrence limits. An entered until date includes that entire calendar period.
These limits constrain when the event happened; they are separate from its
duration. Approximate dates do not acquire hard limits automatically.

Relations can bind a start or end to a named event, before or after that event,
with a signed day offset. **At event** with zero offset shares the exact same
transition, even when its calendar date is uncertain. Deleting an event used
by chronology shows its dependencies first. Remaining references become
unresolved; undo restores the anchor.

## Tips and gotchas

- Internally, `1.0` represents one lore day, but the interface formats it using
  the active calendar.
- Changing the playhead can change which map trajectory or dated raster state
  is visible.
- With an entity selected, changing the playhead can also show the entity's
  visible historical state. The inspector identifies the source of dated
  descriptions and attributes, so corrections can be saved to the right place.
- Timeline grouping organizes the view; it does not duplicate or delete events.
