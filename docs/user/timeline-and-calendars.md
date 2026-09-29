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

The timeline draws precise numeric and minute/second occurrences as solid
diamonds. Hour, day, month, and year precision use a hollow diamond at a layout
anchor inside a dotted, capped possible-date window. The hollow diamond does not
assert an exact date. An explicitly bounded occurrence also uses capped dots;
a one-sided bound has one cap and a fading open end. Approximate or uncertain
dates without hard limits have a fixed-size soft halo, not a measured date
range. At wide zoom levels, narrow windows collapse to a compact symbol; zooming
in restores their calendar-sized span without changing the saved precision.

For durations, hatching shows possible presence and a solid bar marks only the
period when the event is certainly ongoing. A question mark indicates timing
that cannot be bounded on the current calendar. Dragging keeps the date's
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

In an event, open **Date evidence...** to add each source and its date
separately. Choose a source to use its date for the event. Removing or editing
a source preserves the others; conflicting dates are never combined into one
broad range. A conflict message distinguishes disjoint source dates from an
ordinary year-only date.

Open **Chronology...** to record **Before**, **After**, or **Same transition as**
relative to another event, with an optional minimum gap in lore days. The
dialog includes orderings recorded from either event. Same transition treats
both events as one chronological point, rather than dates that merely overlap.
Ordering compares event starts, so events with durations can still overlap.
These statements do not change either event's date precision. Save an edited
date or duration before opening Chronology. Kraken rejects new cycles and
orderings that cannot fit within the recorded dates, including later date edits.

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
