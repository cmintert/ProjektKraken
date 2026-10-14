# Timeline and Calendars

## What this does

The Timeline places events along the world's history. The playhead represents
the current lore time and also controls time-sensitive map content.

(help-timeline-viewing)=

## Use the timeline

**Viewing time** is the Timeline playhead position. It determines which historical
Entity state and time-sensitive map content you see. **World current time** is the
world’s current story time.

1. Use **Go to date → Enter a date…** to inspect a particular date.
2. With an Event selected, use **Go to selected event** or **Show world at this event** to view its saved date.
3. Choose **Return to Current Time** to return to the world’s current story time.

These navigation actions change Viewing time without changing World current time. Choose
**Set Current Time** only when you deliberately want the viewed position to become the
world’s current story time.

For a partial or uncertain event date, navigation uses a representative position. It
does not make that position the event’s exact historical date or increase its saved
precision.

**Example:** Your story’s current time is 980. Go to 962 to inspect Ada’s historical
description and the borders shown then. World current time remains 980; **Return to
Current Time** takes you back.

**Related:** {ref}`Historical Entity editing <help-entity-historical-editing>` ·
{ref}`Date precision <help-date-precision>` · {ref}`Historical geometry
<help-map-historical-geometry>` · {ref}`Map trajectories <help-map-trajectories>`

(help-control-timeline-viewing)=

> Viewing time is the playhead position used to inspect historical entity state, maps and the graph. World current time is the world's current story time. Moving the playhead, going to a date or showing the world at an event changes Viewing without changing World current time. Set Current Time deliberately makes the viewed position the current story time; Return to Current Time moves Viewing back to it. The two marks can coincide without becoming the same setting. Asking for Help explains these roles without moving either time.

### Navigation, event movement and snapping

- Scroll or use the zoom controls to change scale.
- Drag the view to move through time.
- Select an event to open its inspector.
- Move supported event items to update their date.
- Use the playhead controls to inspect another point in history.
- Open **Go to date** above the timeline and choose **Go to selected event**
  to move the playhead to the selected event's saved date and center the view.
  This option is disabled when the selected object is not an available event.
  Approximate dates use a representative position, explained in the viewing
  status after navigation. Selection and World Time stay unchanged.
- Choose **Go to date → Enter a date…** to enter an exact date in the active
  calendar. In narrow layouts, the same menu is under **More actions**. Add an
  hour and minute if needed; a date alone goes to the start of that day. The
  playhead moves there and the timeline centers on it, even without an event.
- In the Event Editor, choose **Show world at this event** to move the playhead
  to the event's saved date and center the timeline. Maps, entity state, and the
  graph follow the playhead. The event stays selected, World Time stays unchanged,
  and unsaved event edits remain in the editor. Partial or uncertain dates use
  the saved numeric date anchor; duration events use their start date.
- Choose **Set Current Time** to make the playhead position the world's current
  story time.
- Choose **Return to Current Time** to move the playhead back to the current
  story time without changing it.
- Enable **Snap to Events** to make manual playhead drags and ruler clicks land
  exactly on a nearby event date. Snapping uses a small on-screen distance, so
  it remains predictable at every zoom level. Playback and scripted jumps do
  not snap.

(help-date-precision)=

## Dates with incomplete information

Record only the date precision your sources support. A year-only date means the
occurrence is known to that year; it does not assert January 1 or a year-long duration.

1. Enter a year, a month and year, or a complete date using the world’s calendar.
2. Leave unknown month and day components unspecified. In the separate date controls, **Delete** clears the selected component.
3. Add a qualification when needed: for example, `c. 961` for approximate or `961?` for uncertain.
4. If you know actual bounds, enter an expression such as `between 959 and 963`, or use **Possible date limits…**.

Approximate and uncertain qualifications do not establish hard limits by themselves. An
occurrence window describes when something happened, not how long it lasted.

The Timeline may place a hollow diamond inside a possible-date window. That position
helps arrange the display; it is not an asserted exact date. Saving and reopening
preserves the precision you entered.

**Example:** Record Ada’s coronation as `962` if only the year is known. Use `between
961 and 963` if the evidence instead establishes those bounds. Leave duration disabled
unless the ceremony’s elapsed length is separately known.

**Related:** {ref}`Event dates and duration <help-event-timing>` · {ref}`Date evidence
<help-date-evidence>` · {ref}`Chronology <help-event-chronology>` · {ref}`Timeline
viewing <help-timeline-viewing>`

(help-control-date-precision)=

> Date qualification describes how a date is known; it does not add a missing month or day. Leave month or day unspecified when the sources give only a year or month. Choosing a component intentionally adds precision. Approximate and uncertain dates do not supply hard limits by themselves: use explicit possible occurrence limits when those bounds are known. For example, `961?` records uncertainty about the year, while `between 959 and 963` supplies a bounded occurrence window. Neither form automatically gives the event a duration.

### Read uncertainty on the Timeline

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

(record-sources-and-ordering)=

(help-date-evidence)=

## Record conflicting date evidence

Date evidence keeps each source’s date claim separately, so you can choose an event date
without losing alternative accounts.

1. Select an Event and open **Date evidence…**.
2. Choose **Add source date**.
3. Enter the citation under **Source / citation** and its date under **Date given by source**.
4. Repeat for other sources.
5. Use **Use this source as the event date** to choose the account you want to follow, then confirm with **OK**.

Editing or removing one source date preserves the other claims. Conflicting dates are
not automatically merged into a broad range. A conflict between sources is different
from a single source giving only a year.

Date evidence records what the sources say. Use **Chronology…** separately to record
that one event happened before or after another.

**Example:** A chronicle dates Ada’s coronation to 962, while a later account gives 964.
Record both claims and choose which source supplies the event date. Do not enter
`between 962 and 964` unless that range itself represents your intended historical
assertion.

**Related:** {ref}`Date precision <help-date-precision>` · {ref}`Event dates and
duration <help-event-timing>` · {ref}`Chronology <help-event-chronology>`

(help-event-chronology)=

## Record event chronology without inventing dates

Chronology records how events are ordered when their calendar dates alone do not express
what you know.

1. Select an Event and save any edited date or duration.
2. Open **Chronology…** and choose **Add ordering**.
3. Choose **Before**, **After**, or **Same transition as**, then select the other Event.
4. For Before or After, use **Gap…** if you know a minimum separation between their starts.
5. Confirm with **OK**.

The dialog includes orderings recorded from either Event. These statements preserve the
dates’ precision: recording “before” does not invent an exact day.

**Same transition as** means both Events share one chronological point. It is stronger
than saying their possible dates overlap. Before/After compares event starts, so lasting
events can still overlap.

Kraken rejects circular orderings and constraints that cannot fit the recorded dates.
Later date edits must also remain consistent with those constraints.

**Example:** Both Ada’s coronation and a treaty are dated only to 962, but a chronicle
says the coronation came first. Record the coronation **Before** the treaty without
assigning either an invented month or day.

**Related:** {ref}`Date precision <help-date-precision>` · {ref}`Date evidence
<help-date-evidence>` · {ref}`Event dates and duration <help-event-timing>` ·
{ref}`Relation timing <help-relations-timing>`

## Tips and gotchas

- Internally, `1.0` represents one lore day, but the interface formats it using
  the active calendar.
- Changing the playhead can change which map trajectory or dated raster state
  is visible.
- With an entity selected, changing the playhead can also show the entity's
  visible historical state. The inspector identifies the source of dated
  descriptions and attributes, so corrections can be saved to the right place.
- Timeline grouping organizes the view; it does not duplicate or delete events.
