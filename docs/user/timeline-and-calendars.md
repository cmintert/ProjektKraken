# Timeline and Calendars

## What this does

Use the Timeline to view history, record uncertain dates and compare source
claims. Begin with an open world and its active calendar. The playhead is
**Viewing time**, separate from **World current time**. See the
[time model](temporal-model.md) for precision, duration and historical sources.

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

(dates-with-incomplete-information)=

## Dates with incomplete information: year-only and uncertain dates

Record only the date precision your sources support. A year-only date means the
occurrence is known to that year; it does not assert January 1 or a year-long duration.

1. Enter a year, a month and year, or a complete date using the world’s calendar.
2. Leave unknown month and day components unspecified. In the separate date controls, **Delete** clears the selected component.
3. Add a qualification when needed: for example, `c. 961` for approximate or `961?` for uncertain.
4. If you know actual bounds, enter an expression such as `between 959 and 963`, or use **Possible date limits…**.
5. Validate the date, then use **Save Changes** or check the separate save
   status. Reopen the Event and confirm that unknown components remain unknown.

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

An asserted year-only date means the Event occurred somewhere within that year;
it does not mean the Event lasted a year. An uncertain or approximate date keeps
its qualification separately and supplies no hard limits unless you author them.
When a map or relation follows this Event, refining its date updates the binding
without copying the timeline's representative position into an exact boundary.

Very distant dates may not support second precision or very small offsets.
Kraken explains unrepresentable precision instead of silently rounding an
assertion into a different meaning.

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

1. Open **Settings → This World → Timeline**.
2. Choose the tags used to form timeline bands.
3. Choose **Apply** in Settings Center to save the grouping. Tag colours and
   grouping order remain pending until you apply them.
4. Use **Timeline → Clear Grouping** to return to the ungrouped view.

Group labels can be renamed, recolored, or removed from the current grouping
through their context menu.

(help-calendar-configure)=

## Configure the calendar

1. Open **Settings → This World → Timeline**.
2. Review **This World → Timeline** in Settings Center. Change only the intended
   configuration, then choose **Apply**. **Cancel** discards unapplied changes.
3. Check a known Event date and the Timeline ruler using the resulting calendar.

Calendar configuration controls how stored lore days are formatted throughout
the interface. It does not independently reschedule every saved Event to retain
the old calendar's displayed date. Back up a world before substantial calendar
changes; do not use a calendar change to correct one Event's date.

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

- Dates use the active world's calendar. Do not interpret a raw numeric lore
  day as a calendar year when exchanging records.
- Changing the playhead can change which map trajectory or dated raster state
  is visible.
- With an entity selected, changing the playhead can also show the entity's
  visible historical state. The inspector identifies the source of dated
  descriptions and attributes, so corrections can be saved to the right place.
- Timeline grouping organizes the view; it does not duplicate or delete events.

## Interface control reference

These explanations describe the software operation. Inspecting a control does not run it or read your entered values.

(help-inspect-src-gui-dialogs-calendar-config-dialog-calendarconfigdialog-setup-ui-self-name-edit)=

**Calendar name** — Name this world's calendar. The name identifies the calendar used to
display lore dates.

(help-inspect-src-gui-dialogs-calendar-config-dialog-calendarconfigdialog-setup-ui-self-epoch-edit)=

**Epoch designation** — Set the text used to identify the calendar's epoch.

(help-inspect-src-gui-dialogs-calendar-config-dialog-calendarconfigdialog-setup-ui-self-month-table)=

**Months** — Edit month names, abbreviations and lengths in calendar order. Calendar
changes affect how lore-day values are displayed.

(help-inspect-src-gui-dialogs-calendar-config-dialog-calendarconfigdialog-setup-ui-self-btn-add-month)=

**Add month** — Append a month to the calendar configuration, then supply its name and
length before saving.

(help-inspect-src-gui-dialogs-calendar-config-dialog-calendarconfigdialog-setup-ui-self-btn-remove-month)=

**Remove month** — Remove the selected month from the calendar configuration. Review the
calendar before saving.

(help-inspect-src-gui-dialogs-calendar-config-dialog-calendarconfigdialog-setup-ui-self-day-names-edit)=

**Day Names:** — e.g., Moonday, Starday, Godsday, Waterday, Earthday, Freeday, Sunday.

(help-inspect-src-gui-dialogs-calendar-config-dialog-calendarconfigdialog-setup-ui-self-day-abbrev-edit)=

**Abbreviations:** — e.g., Mo, St, Go, Wa, Ea, Fr, Su.

(help-inspect-src-gui-dialogs-calendar-config-dialog-calendarconfigdialog-setup-ui-self-leap-table)=

**Leap rules** — Edit the rules that add leap days to this calendar. Review their
intervals and affected months before saving.

(help-inspect-src-gui-dialogs-calendar-config-dialog-calendarconfigdialog-setup-ui-self-btn-add-rule)=

**Add leap rule** — Append a leap-day rule to the calendar configuration.

(help-inspect-src-gui-dialogs-calendar-config-dialog-calendarconfigdialog-setup-ui-self-btn-remove-rule)=

**Remove leap rule** — Remove the selected leap-day rule from the calendar
configuration.

(help-inspect-src-gui-dialogs-calendar-config-dialog-calendarconfigdialog-setup-ui-self-preview-float)=

**Date preview** — Enter a lore-day value to preview how this calendar formats it.
Previewing does not change an Event date.

(help-inspect-src-gui-dialogs-calendar-config-dialog-calendarconfigdialog-setup-ui-self-button-box)=

**Button box** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-grouping-config-dialog-groupingconfigdialog-setup-ui-self-list-widget)=

**Grouping tags** — Select and order the tags used for Timeline groups. Grouping changes
presentation without duplicating saved Events.

(help-inspect-src-gui-dialogs-grouping-config-dialog-groupingconfigdialog-setup-ui-self-btn-up)=

**Move group up** — Move the selected tag earlier in the grouping order. In First Match
mode, earlier groups take priority.

(help-inspect-src-gui-dialogs-grouping-config-dialog-groupingconfigdialog-setup-ui-self-btn-down)=

**Move group down** — Move the selected tag later in the grouping order. Event dates
remain unchanged.

(help-inspect-src-gui-dialogs-grouping-config-dialog-groupingconfigdialog-setup-ui-self-radio-duplicate)=

**Duplicate** — Events with multiple tags appear in all matching groups.

(help-inspect-src-gui-dialogs-grouping-config-dialog-groupingconfigdialog-setup-ui-self-radio-first-match)=

**First Match** — Events appear only in the first matching group.

(help-inspect-src-gui-dialogs-grouping-config-dialog-groupingconfigdialog-setup-ui-self-button-box)=

**Button box** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-temporal-evidence-dialog-temporalevidencedialog-init-self-claims)=

**Source-date claims** — Review separate date claims and their sources. Recording a
disagreement does not combine the claims into one invented date.

(help-inspect-src-gui-dialogs-temporal-evidence-dialog-temporalevidencedialog-init-self-preferred)=

**Preferred** — Choose which recorded source supplies the Event date, or retain an
independent date. Other source claims are preserved.

(help-inspect-src-gui-dialogs-temporal-evidence-dialog-temporalevidencedialog-init-add)=

**Add source date** — Add a separate dated source claim for this Event. Select a
preferred source separately if it should supply the Event date.

(help-inspect-src-gui-dialogs-temporal-evidence-dialog-temporalevidencedialog-init-remove)=

**Remove source date** — Remove the selected source claim from the dialog draft. Review
the preferred source before accepting.

(help-inspect-src-gui-dialogs-temporal-evidence-dialog-temporalevidencedialog-init-actions)=

**Actions** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-widgets-compact-date-widget-compactdatewidget-setup-text-first-self-date-fields-button)=

**Date details and uncertainty** — Expand structured date fields and uncertainty choices
without committing an unfinished date.

(help-inspect-src-gui-widgets-compact-date-widget-compactdatewidget-setup-text-first-self-qualifier-combo)=

**Date qualification** — Describe how certain the date is. Qualification is independent
of omitted month or day precision.

(help-inspect-src-gui-widgets-compact-date-widget-compactdatewidget-setup-text-first-self-limits-button)=

**Possible occurrence limits** — Set the earliest and latest possible occurrence dates
without treating uncertainty as Event duration.

(help-inspect-src-gui-widgets-compact-date-widget-compactdatewidget-edit-limits-enabled)=

**Enable occurrence limit** — Enable this possible-date limit. Leaving it off keeps that
side unspecified.

(help-inspect-src-gui-widgets-compact-date-widget-compactdatewidget-edit-limits-field)=

**Occurrence limit date** — Enter the possible occurrence boundary. This limits
uncertainty; it does not create an Event end date.

(help-inspect-src-gui-widgets-compact-date-widget-compactdatewidget-edit-limits-actions)=

**Actions** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-widgets-compact-date-widget-compactdatewidget-setup-ui-self-spin-year)=

**Year** — Enter the year using the active world's calendar. Month and day may remain
unspecified where partial dates are supported.

(help-inspect-src-gui-widgets-compact-date-widget-compactdatewidget-setup-ui-self-combo-month)=

**Month precision** — Choose a month, or leave it unspecified when only the year is
known.

(help-inspect-src-gui-widgets-compact-date-widget-compactdatewidget-setup-ui-self-combo-day)=

**Day precision** — Choose a day, or leave it unspecified when the exact day is not
known.

(help-inspect-src-gui-widgets-compact-date-widget-compactdatewidget-setup-ui-self-btn-time-toggle)=

**Time toggle** — Show / hide time input (auto-shown for non-midnight dates).

(help-inspect-src-gui-widgets-compact-date-widget-compactdatewidget-setup-ui-self-btn-calendar)=

**Choose calendar date** — Open the date picker for this field. This chooses a date; it
does not configure the world's calendar.

(help-inspect-src-gui-widgets-compact-date-widget-compactdatewidget-setup-ui-self-spin-hour)=

**Hour** — Set the hour component of this date. Showing time fields is separate from
setting date uncertainty.

(help-inspect-src-gui-widgets-compact-date-widget-compactdatewidget-setup-ui-self-spin-minute)=

**Minute** — Set the minute component of this date.

(help-inspect-src-gui-widgets-compact-date-widget-compactdatewidget-setup-ui-self-txt-date)=

**Txt date** — Enter date text (e.g. '15 Jan 3019').

(help-inspect-src-gui-widgets-compact-date-widget-calendarpopup-setup-ui-self-spin-year)=

**Calendar year** — Choose the year shown by the date picker.

(help-inspect-src-gui-widgets-compact-date-widget-calendarpopup-setup-ui-self-combo-month)=

**Calendar month** — Choose the month shown by the date picker.

(help-inspect-src-gui-widgets-compact-date-widget-calendarpopup-setup-ui-btn-ok)=

**OK** — Accept the current Calendar Popup choices after validation. Review the fields
first; opening Help does not accept them.

(help-inspect-src-gui-widgets-compact-date-widget-calendarpopup-setup-ui-btn-cancel)=

**Cancel** — Cancel this Calendar Popup operation without accepting its pending changes.
This is separate from applying or saving them.

(help-inspect-src-gui-widgets-compact-date-widget-calendarpopup-refresh-grid-btn)=

**Choose day** — Choose this day in the calendar picker. Accept the picker to use the
chosen date.

(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-temporal-description-fields-self-chronology-button)=

**Chronology button** — Record Before, After or Same transition as another Event.
Chronology constrains ordering without inventing missing date precision.

(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-temporal-description-fields-self-temporal-evidence-button)=

**Temporal evidence button** — Record separate source-date claims and choose which
source supplies the Event date. Conflicting claims remain separate.

(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-temporal-description-fields-self-btn-show-world-at-event)=

**Show world at event** — Move Viewing time to this Event’s saved date without changing
World current time or applying unsaved date edits.

(help-inspect-src-gui-widgets-lore-date-widget-loredatewidget-setup-ui-self-year-spin)=

**Year** — Set the year component using the active calendar.

(help-inspect-src-gui-widgets-lore-date-widget-loredatewidget-setup-ui-self-month-combo)=

**Month** — Set the month component using the active calendar.

(help-inspect-src-gui-widgets-lore-date-widget-loredatewidget-setup-ui-self-day-combo)=

**Day** — Set the day component using the active calendar.

(help-inspect-src-gui-widgets-lore-date-widget-loredatewidget-setup-ui-self-hour-combo)=

**Hour** — Set the hour component of this date.

(help-inspect-src-gui-widgets-lore-date-widget-loredatewidget-setup-ui-self-minute-combo)=

**Minute** — Set the minute component of this date.

(help-inspect-src-gui-widgets-lore-date-widget-loredatewidget-setup-ui-self-raw-spin)=

**Raw lore date** — Edit the date as a numeric count of lore days. This is another
representation of the same date.

(help-inspect-src-gui-widgets-lore-date-widget-loredatewidget-setup-ui-self-raw-toggle)=

**Show raw date** — Show or hide the numeric lore-day representation of this date.

(help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-btn-step-back)=

**Previous date** — Step the Timeline playhead backward using the playback controller.
This changes Viewing time, not Event dates.

(help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-btn-play-pause)=

**▶** — Start or pause Timeline playback. Playback changes Viewing time rather than
rewriting event dates.

(help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-btn-step-forward)=

**Next date** — Step the Timeline playhead forward using the playback controller. World
current time is unchanged.

(help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-btn-set-current-time)=

**Set Current Time** — Deliberately make the playhead position the world’s current story
time. Ordinary date navigation changes Viewing time only.

(help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-btn-return-present)=

**Return to Current Time** — Move Viewing time back to World current time without
changing that saved current story time.

(help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-btn-go-to-date)=

**Go to date** — Open date navigation to a selected Event or an entered calendar date.
Navigation changes Viewing time without changing World current time.

(help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-date-navigation-menu)=

**Date navigation menu** — Open the Date navigation menu menu to choose a related
operation. Opening the menu does not apply any of its actions.

(help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-selected-event-date-action)=

**Go to selected Event** — Move Viewing time to the selected Event's saved date. This
does not change the Event or World current time.

(help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-enter-date-action)=

**Enter viewed date** — Open date entry to move the Timeline playhead to a chosen
calendar date.

(help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-chk-snap-playhead-to-events)=

**Snap to Events** — Snap manual playhead movement to nearby event dates. This does not
add precision to partial event dates or affect playback jumps.

(help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-btn-fit)=

**Fit View** — Fit the current content into the available view without changing saved
positions or dates.

Overlapping events are arranged chronologically: the earlier event stays above
later events whose labels or timing markers overlap it. Non-overlapping events
can share a row. Equal saved dates use a stable tie-break. Saved dates determine
this order without adding precision to uncertain dates.
Spacing follows measured text and marker widths rather than a fixed label box.

Zooming uses the fewest rows allowed by those rules and reclaims spare rows
automatically. An overlapping chain can need more rows than a layout that allows
later events above earlier ones.

(help-inspect-timeline-compact-lanes)=

**Compact lanes** — To explicitly repack the arrangement, open the arrow beside **Fit View** and
choose **Compact lanes**. In a narrow panel, open **More actions**, then the
**Fit View** submenu. Automatic zooming already minimizes row count; this action
rebuilds the same deterministic chronological arrangement. Dates, the
viewed time and selection stay unchanged. This arrangement becomes the starting
point for subsequent zooms. The action is unavailable when there are no events.
Row arrangements are retained while this timeline is open, rather than saved
with the world.

(help-inspect-src-gui-widgets-timeline-display-widget-timelinedisplaywidget-init-self-text-display)=

**Linked-event Timeline** — Read and navigate the linked Events shown for the inspected
entry. This is separate from changing their saved dates.

(help-inspect-src-gui-dialogs-event-chronology-dialog-eventchronologydialog-init-add)=

**Add ordering** — Add a draft Before, After or Same transition constraint between this
Event and another Event. Accept the dialog to save it.

(help-inspect-src-gui-dialogs-event-chronology-dialog-eventchronologydialog-init-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-event-chronology-dialog-eventchronologydialog-add-row-order)=

**Order** — Same transition treats both events as one chronological point, not merely
overlapping dates.

(help-inspect-src-gui-dialogs-event-chronology-dialog-eventchronologydialog-add-row-target)=

**Other Event** — Choose the Event used by this ordering constraint. Ordering does not
supply missing date precision.

(help-inspect-src-gui-dialogs-event-chronology-dialog-eventchronologydialog-add-row-gap)=

**Minimum gap** — Set the minimum separation between Event starts in lore days. The
ordering determines which Event is earlier.

(help-inspect-src-gui-dialogs-event-chronology-dialog-eventchronologydialog-add-row-more)=

**Gap…** — Show the minimum-separation field for this ordering. The gap compares event
starts in lore days.

(help-inspect-src-gui-dialogs-event-chronology-dialog-eventchronologydialog-add-row-remove)=

**Remove ordering** — Remove this ordering row from the dialog draft. Accept the dialog
to save the revised constraints.

(help-inspect-src-gui-dialogs-go-to-date-dialog-gotodatedialog-init-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-widgets-timeline-group-band-manager-groupbandmanager-on-context-menu-requested-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-widgets-timeline-group-band-manager-groupbandmanager-on-context-menu-requested-rename-action)=

**Rename Timeline group** — Renaming a grouping tag is not implemented in this build.
This menu item does not change tags or Event names.

(help-inspect-src-gui-widgets-timeline-group-band-manager-groupbandmanager-on-context-menu-requested-color-action)=

**Change Color...** — Choose a display colour for this style. Styling does not create or
remove a world relation.

(help-inspect-src-gui-widgets-timeline-group-band-manager-groupbandmanager-on-context-menu-requested-remove-action)=

**Remove from grouping** — Remove this tag from the Timeline grouping configuration. The
tagged entries remain in the world.

(help-inspect-view-src-gui-widgets-timeline-init-timelinewidget-init-self-view)=

**Timeline canvas** — Navigate Events and Viewing time on the Timeline. Dragging an
Event can change its date; inspection does not select or move it.
