(help-event-recurrence)=

# Repeat an Event

Use recurrence for a festival, market or predictable phenomenon that appears
regularly. It remains one ordinary Event with one description, set of tags and
relationships. Its calculated appearances do not create additional entries.

## Set a repeating schedule

Start with an open world and an Event with an independently authored exact date.
Calendar schedules use the saved world calendar. An approximate date, a date
following another Event, or an independently specified end needs to be changed
deliberately before it can anchor this first version of recurrence.

1. Select the Event in Explorer and check its date. This date anchors the pattern;
   it need not be the first occurrence in the world's history.
2. Open **Repeats** and select **Repeat this Event**.
3. Choose **Repeat every** and a **Unit**: elapsed days, calendar weeks, months or
   years. Only elapsed days accept fractional intervals.
4. For a weekly schedule, select its weekdays. For a monthly or annual weekday
   schedule, choose first through fifth, or last, and one weekday. The anchor date
   must match the chosen pattern. Annual rules use the anchor's calendar month.
5. Choose **Forward**, **Backward** or **Both directions**. Optional **Earliest
   occurrence** and **Latest occurrence** dates limit the starts of occurrences.
   Both limits must include the anchor date.
   A typed date includes that whole day; a typed time includes its stated
   precision. Unchanged saved bounds retain their exact values.
6. Check the date preview and choose **Save Changes**. Description autosave does
   not apply a pending recurrence or date edit.

Reopen the Event to check the saved schedule. **Discard** restores the
saved schedule along with the existing date controls. A failed save leaves the
draft available for correction. Turning off **Repeat this Event** and saving
restores an ordinary timeline item without moving its authored date.

If the schedule changed elsewhere while you were editing, the save is rejected
instead of overwriting that change. Preserve any draft wording you need, use
**Discard** to reload the saved Event, and reapply your intended schedule.

## Find occurrences on the Timeline

Recurring Events appear as **circles with adjacent names and dates** in a compact
strip below the date ruler and time labels, above ordinary Event lanes. Ordinary
Events retain their diamond marks. Each circle pinpoints an occurrence's date;
fitting its label near an edge does not move the pin. This includes the anchor occurrence.
Zoom in if the pattern is hidden: annual schedules appear at year scale and
closer, while more frequent schedules require closer scales.

Select a marker to inspect its occurrence date and description and select its
ordinary Event. A crowded marker opens a list of Event names and occurrence
dates; use the keyboard or pointer to choose one. **More occurrences…** continues
a bounded list. Selecting an occurrence does not move the playhead or edit a
date. Open the ordinary Event editor to change its schedule; markers cannot be
dragged to reschedule a repetition.

## Calendar dates, duration and history

An elapsed-day interval and a calendar month or year are different schedules.
Calendar rules keep the anchor's day and month position, or its selected weekday
rule. A nonexistent day, missing month or absent fifth weekday is skipped rather
than moved. The next valid occurrence is still calculated from the anchor, so
skipping February does not move a month-end festival to an earlier day in March.
Calendar changes can leave a schedule unavailable; its data remains stored and
the strip explains the problem so you can correct it in the editor.

No end means an instant. An authored fixed duration applies to each repetition;
overlapping repetitions remain distinct. An occurrence can remain visible when
its start is outside the viewport but its duration enters it.

Create significant happenings as separate Events. A riot during one festival
gets its own date and relationships. An ordinary link associates it with the
festival without making it move when the festival schedule changes.

Existing timing references and world-state effects still refer to the Event's
authored date. Repetitions do not apply those effects again. This version does
not support following an individual calculated occurrence, individual overrides,
historical schedule revisions, astronomical conditions or automatic recurring
changes to the world.

## Control explanations

(help-event-repeats)=

**Repeats** reveals optional recurrence settings on the selected ordinary Event.
The authored date anchors forward, backward or two-way repetition. Review the
preview and use Save Changes to apply the schedule; description autosave does
not apply it. Collapsing the section preserves its values.

(help-event-repeat-interval)=

**Repeat every** sets the positive interval in the selected unit. Calendar
weeks, months and years require whole intervals; elapsed days allow fractions.
The preview explains an invalid interval or an anchor that does not match the
weekday rule. Save Changes applies corrected values.

(help-timeline-repeats)=

**Recurring Events** shows calculated occurrences as circles at their actual
dates, with ordinary Event typography and no permanent button box. Zoom controls
their visibility without adding Event records. Select an occurrence or crowded list entry to select its ordinary
Event and inspect the occurrence date. The playhead stays in place, and marker
selection never edits the schedule. Use the ordinary Event editor for changes.

**Related:** {ref}`Event dates <help-event-timing>` ·
{ref}`Timeline navigation <help-timeline-viewing>`.
