# Understand time and historical state

Kraken separates what you know about a date from where it draws that date, and
separates viewing history from changing it. The Northwatch sample illustrates
these distinctions with one succession and a separate uncertain report.

## Viewing time and World current time

Viewing time is the Timeline playhead. It selects the historical Entity values,
map states and relation views you inspect. World current time is the world's
story-time setting. Looking at the march does not move that setting backwards.
**Return to Current Time** brings the view back to it; **Set Current Time**
deliberately changes the story-time setting.

Follow {ref}`Timeline navigation <help-timeline-viewing>` to inspect a date.
Selecting an event and changing its saved date is an authoring operation with
different consequences from viewing the world at that event.

## Precision, uncertainty and duration

The disputed surrender report gives January, year 1, with an uncertain date and
no day. A representative Timeline position makes it possible to arrange and
navigate to the report. It is not evidence for an exact surrender day.

Date precision records which components are known. Qualification records how
confident the assertion is. Explicit possible-date limits supply bounds;
approximate or uncertain wording alone does not establish hard bounds.
Duration separately records how long an event lasts. A year-only occurrence
does not mean a year-long event. A displayed span between partial dates does
not establish an exact number of elapsed days.

Use {ref}`date precision <help-date-precision>` and
{ref}`event timing <help-event-timing>` to enter these assertions. Preserve
separate {ref}`source claims <help-date-evidence>` when accounts disagree.
Use {ref}`chronology <help-event-chronology>` when their order is known even
though exact dates are not. Existing numeric dates keep their exact meaning.

## A visible value has a source

Northwatch's kingdom has a baseline ruler and a dated change at the succession.
Moving the playhead chooses the applicable state. **Source** identifies the
baseline or event supplying a displayed value. Correcting that value edits its
source; simply viewing a later time does not create a new historical change.

Use a deliberate dated change when a fact becomes different from that point
onward. See {ref}`historical Entity editing <help-entity-historical-editing>`
and {ref}`value sources <help-entity-value-source>`. Possible changes remain
distinct from changes established at the viewed date.

## Shape, location and presence

A dated border changes a region's shape; **Base Geometry** supplies the shape
before the first dated state. Shapes switch at their dates without morphing.
A trajectory separately records an Entity's locations over time. Existence
boundaries decide whether a feature is present at all; manual layer hiding
decides whether you display it. These controls answer different questions.

Changing a border does not change **Exists from / Exists until**. Exact presence
starts inclusively and ends exclusively. An unknown boundary is unresolved;
an unbounded boundary has no limit on that side. Shared event-bound relation
transitions retain event identity even if the event moves; copying its displayed
coordinate into manual dates does not.

See {ref}`dated geometry <help-map-historical-geometry>`,
{ref}`visibility <help-map-visibility>`, {ref}`trajectories <help-map-trajectories>`
and {ref}`relation timing <help-relations-timing>` for the separate procedures.
