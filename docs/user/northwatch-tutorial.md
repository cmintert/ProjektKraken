# Explore a changing kingdom

In this tutorial, you will watch a border, an army and a ruler change together,
then distinguish a dated succession from a report whose exact day is unknown.
You do not need to edit the sample to complete it.

## Start with the sample

Use a fresh **Northwatch Demo (Illustrated)** world supplied by the maintainer.
The Windows application does not create this sample automatically. If you do
not have its complete world folder, ask for one before starting. Maintainers
can reproduce it using the
[Northwatch setup](https://github.com/cmintert/ProjektKraken/blob/main/docs/ux/northwatch-demo.md#recreate-the-sample-for-maintainers).

1. Open **File → Manage Databases…**.
2. If the sample is absent, choose **Add World Folder** and select its complete
   folder containing `world.json`, its `.kraken` file and assets.
3. Select **Northwatch Demo (Illustrated)** and choose **Select & Restart**.
4. Open its map, **Northwatch - watch the border change**, from Project.

**Check:** The sample's name appears in the window title and the map opens.
If the image is missing, stop and obtain the complete sample folder rather than
creating a replacement world or changing your own world.

## Watch the succession

1. Select **01 - The march begins** in Project.
2. Choose **Show world at this event** in the Event editor. If its controls
   overflow, use **More actions**.
3. Look at the map. The army is at Ashford and the kingdom occupies the west.
4. Select **02 - The Northwatch succession** and choose **Show world at this event**.

**Check:** Viewing time advances from 1 January to 10 January, year 1. The army
reaches Northwatch Keep and the border reaches the eastern coast. You changed
the date being viewed; you did not reschedule either event or set World current time.

If nothing changes, check that the sample map is open and that you used
**Show world at this event** rather than editing the event's date field.

## Inspect who rules

1. Select **Kingdom of Ashford** in Project and read its **Ruler** attribute.
2. Use **Go to date → Enter a date…** above the Timeline to view 1 January, year 1,
   using the sample's active calendar.
3. Read **Ruler** again, then view 10 January, year 1, through the same menu.

**Check:** Queen Mara rules at the earlier date; Captain Ilyra rules at the
later date. Read **Source** to see where the displayed value comes from.
Keep the fields unchanged while comparing. These are two historical states
of one kingdom, not duplicate kingdom entries.

## Inspect the uncertain report

1. Select **03 - A disputed surrender report**.
2. Read its date and the description of the damaged chronicle.
3. Choose **Show world at this event** and inspect its Timeline marker.

**Check:** The report is dated to January, year 1, uncertain, with no known day.
Its displayed position does not establish the surrender's exact date. It is a
separate event from the succession; it does not move the ruler or border change.

You have now compared one world's historical states and recognized a limit in
its evidence. Continue with [time and historical state](temporal-model.md) or
{ref}`record a date with incomplete information <help-date-precision>`.

## Return or start again

Choose **Return to Current Time** to return to the world's story time. This
changes Viewing time only. If you edited a field accidentally, cancel an
unfinished edit or use Undo for an already saved supported change. Do not
change dates to make the tutorial match; ask for another fresh sample if its
saved content differs from these checkpoints.
