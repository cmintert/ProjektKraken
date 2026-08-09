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
- Enable **Snap to Events** to make manual playhead drags and ruler clicks land
  exactly on a nearby event date. Snapping uses a small on-screen distance, so
  it remains predictable at every zoom level. Playback and scripted jumps do
  not snap.

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

## Tips and gotchas

- Internally, `1.0` represents one lore day, but the interface formats it using
  the active calendar.
- Changing the playhead can change which map trajectory or dated raster state
  is visible.
- Timeline grouping organizes the view; it does not duplicate or delete events.
