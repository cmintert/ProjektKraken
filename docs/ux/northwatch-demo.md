# The Northwatch Succession

Open **Northwatch Demo (Illustrated)** in World Manager. If it is not listed,
register the complete `Northwatch Demo (Illustrated)` folder. Open its map,
**Northwatch - watch the border change**.

## Try the changing world

1. Open **01 - The march begins** and choose **Show world at this event**.
   It is 1 January, year 1. The kingdom occupies the west; the army is at Ashford.
2. Open **02 - The Northwatch succession** and choose **Show world at this event**.
   It is 10 January. The border reaches the eastern coast and the army is at
   Northwatch Keep. Move the timeline playhead between those dates to compare.
3. Open **Kingdom of Ashford** at those two dates. Its **Ruler** changes from
   Queen Mara to Captain Ilyra. Northwatch Keep's description and allegiance change
   too. Follow the succession event's relations to the people and places involved.

The map, ruler and descriptions show what was true at the date you selected.
The sample content can be edited like any other world.

The travelling army uses the supplied illustrated army marker. Its route crosses
the River Ash bridge.
The illustrated parchment map is neutral geography; the border is an editable
historical overlay rather than part of the picture.

## Explore the rest

- Open **03 - A disputed surrender report**. Its date is **January, year 1,
  uncertain; day unknown**. Its position on the timeline is a display coordinate,
  not evidence of an exact surrender day. The dated succession remains a separate
  event; the disputed report does not change the border or ruler.
- Run world validation. **The unfinished coronation account** has only “Draft”
  as its description: this is one deliberate, repairable editorial finding.
  Write a useful account, save it, then validate again to see the finding disappear.
- Open Longform to read the connected material in order. A generated
  **Northwatch Chronicle.md** is also included in the world folder.
- Back up the sample using Kraken's backup controls, or export its Longform
  material. Work on this sample rather than your own world when trying restoration.

## Recreate the sample (for maintainers)

From the repository environment, run:

```powershell
.venv\Scripts\python.exe -m scripts.create_demo_world
```

To create another copy, supply `--destination` with a new folder. Existing worlds
are never overwritten. Generated world data lives under the ignored `worlds/`
directory; the generator, `assets/demo/northwatch.png`, `assets/demo/army.png`
and this route are the
reproducible source. The map was created with the built-in image generator.

## Observed first-session runs (KRT-18)

This sample is ready for observation; automated checks cannot establish
discoverability or the two-minute first-value target. Do not coach participants
through the first steps. Give them the sample and ask them to explore how its
history changes. Record whether they find the route themselves.

| Run | Time to first visible change | Help / wrong turns | Explanation in their own words | Follow-up |
| --- | --- | --- | --- | --- |
| 1 | Pending | | | |
| 2 | Pending | | | |
| 3 | Pending | | | |
| 4 | Pending | | | |
| 5 | Pending | | | |

Feed confusion and wrong turns into the Authoring UX benchmark log. Success means
the participant can explain that Kraken shows what was true at a chosen point in
history, and encounters the first visible change within two minutes without
developer coaching. The later validation, Longform and export steps have no
two-minute limit.

This content uses existing navigation (authoring contracts 1, 2, 4 and 5), keeps
uncertainty explicit, and adds no controls or keyboard conventions. Map geography
is content rather than application presentation; widget styling continues to use
the existing semantic theme roles. Human observations remain pending.
