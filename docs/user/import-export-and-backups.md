# Import, Export, and World Transfer

## What This Does

Open **File → Import / Export…** to bring lore into the current world, publish
your writing, or move a complete world to another ProjektKraken installation.
The window explains what each format contains and whether it can be imported
again before you choose a file.

These actions serve different purposes:

- **Lore import and export** moves entities, events, relations, tags, dates, and
  custom fields.
- **Longform publishing** creates readable Markdown, Word, or PDF documents.
- **Portable world transfer** moves the whole world, including maps and assets.
- **Backup and restore** recovers the current world's saved data.

## What You Can Do

- Import one file, several files, a folder of lore, or pasted JSON.
- Mix supported JSON, Markdown, CSV, and TSV sources in one reviewed import.
- Map spreadsheet columns to entities, events, or relations.
- Preview new, changed, skipped, and ambiguous records before importing.
- Skip matching records, merge imported fields, or replace record fields.
- Exclude or correct individual records and check the import again.
- Export all lore or the records selected in Explorer.
- Publish the Longform document as Markdown, DOCX, or PDF.
- Export and import a complete `.krakenworld` package.
- Save a transfer report and open the resulting file or folder.

## Supported Formats

| Format | Import | Export | Includes |
|---|---:|---:|---|
| Lore JSON (`.json`) | Yes | Yes | Entities, events, relations, tags, dates, and custom fields |
| CSV or TSV (`.csv`, `.tsv`) | Yes | Yes | One table of entities, events, or relations per file |
| Markdown notes (`.md`) | Yes | Yes | Individual lore notes with supported frontmatter and links |
| Longform Markdown (`.md`) | No | Yes | The authored Longform document |
| Word (`.docx`) | No | Yes | An editable Longform publication |
| PDF (`.pdf`) | No | Yes | A paginated Longform publication |
| Portable world (`.krakenworld`) | Yes | Yes | World details, saved data, maps, calendars, and assets |
| Backup (`.kraken`) | Restore | Create | Saved world data; asset files are not included |

The **Supported formats** tab also links to the specialist tools for map images,
raster layers, galleries, palettes, and analysis reports. It can save example
JSON and CSV files that you can use as templates.

## Import Lore

1. Choose **File → Import / Export…** and open the **Import** tab.
2. Click **Add files…** or **Add folder…**. You can also paste lore JSON into
   the text box.
3. For CSV or TSV, choose whether the file contains entities, events, or
   relations. Map each source column to a ProjektKraken field. Unmapped columns
   are listed as ignored.
4. Choose what should happen when a record matches existing lore. **Skip
   existing records** is the default.
5. Click **Review…**. No world data changes during preparation.
6. Review the source, planned action, match reason, and exact field changes.
   Uncheck records you do not want. Use the action and match menus when needed.
7. Select a record to inspect or correct its fields, then click **Apply edits
   and recheck**.
8. Resolve every error, then click **Import reviewed changes**.

The entire reviewed import is applied together. If a source file or the world
changes after review, ProjektKraken asks you to review again. A completed lore
import can be undone from **Edit → Undo**.

### Matching Choices

- **Skip** keeps the current record unchanged. This is the default and makes
  repeated imports safe.
- **Merge** keeps existing information and adds or updates imported fields.
- **Replace** replaces the record's editable fields with the imported version.

Ambiguous names must be matched to a specific record or excluded. Events need a
valid date. ProjektKraken does not silently turn an unreadable date into day
zero in the unified importer.

## Export Lore

1. Open the **Export** tab.
2. Choose **Lore JSON**, **Lore CSV tables**, or **Markdown / Obsidian notes**.
3. Choose **All lore** or **Explorer selection**.
4. When exporting selected lore, enable **Include missing relationship
   endpoints** if connected records should be added automatically.
5. Choose the destination and click **Review…**.
6. Check the record counts, omitted-relation warnings, destination, and format
   limitations. Click **Create output** when the review is correct.

JSON is the most complete re-importable lore format. CSV creates separate
entity, event, and relation tables. Tags and custom fields are stored as JSON
inside their cells so they can round-trip without flattening. Markdown creates
readable linked notes but is not a complete-world backup.

Note exports copy supported local images into the vault's `assets/` folder.
Relation links use the exported note filenames, including suffixes for duplicate
names. Missing or outside-world images appear in the export review warnings.

## Publish Longform

1. Open the **Export** tab and choose **Longform Markdown**, **Longform Word
   document**, or **Longform PDF**.
2. Enter the document title.
3. Choose A4 or Letter page size. You can add a contents list and include
   referenced images.
4. Choose the output file and click **Review…**.
5. Inspect the document preview and any missing-image or simplified-formatting
   warnings, then click **Create output**.

Publishing follows the authored Longform order. It preserves headings,
paragraphs, emphasis, lists, tables, and contained local images. Wiki links use
readable labels and become internal links when the target is part of the
document. DOCX and PDF files cannot be imported as lore.

Longform Markdown copies referenced local images into a neighboring folder named
after the output file, such as `Chronicle.md.assets/`. Keep that folder beside the
Markdown file when moving or sharing it. Disabling images exports their labels.

(help-world-transfer)=

## Move a Complete World

### Export a World

1. Open **World Transfer & Backups**.
2. Choose **Export the current world with assets**.
3. Choose a `.krakenworld` destination outside the world's asset folder.
4. Review the destination and world contents, then click **Transfer world**.

ProjektKraken creates a consistent saved copy and includes the manifest and
asset folder. Local preferences, search caches, external-path approvals, and
old backups are not included. Missing or unsafe asset references stop the
export so the package does not appear complete when it is not.

### Import a World

1. Choose **Import a portable world as a new world**.
2. Select a `.krakenworld` file and enter a new world name.
3. Review the package size and file count, then click **Transfer world**.
4. Open **Manage Worlds…** and select the imported world. Restart when prompted.

Import always creates a new world folder and a new world identity. It never
overwrites the active world. Internal lore IDs remain intact so relations and
map connections continue to work.

(help-backup-restore)=

(help-world-backups)=

## Back Up and Restore

Use **File → Backup & Restore** or the shortcuts in **World Transfer &
Backups** to create, restore, locate, and configure backups.

Restoring a `.kraken` backup replaces the active world's saved data and is not
an ordinary undoable action. Backups do not contain asset files. Use a portable
world package when maps and other assets need to travel with the world.

Backups include committed database changes even when they are still in SQLite's
write-ahead log. Restore validates the selected backup first, requires unfinished
edits to be resolved, stops database work, and creates a checked safety snapshot
before replacement. After database shutdown, both successful and failed restore
attempts close the application and require a restart. A failure before shutdown
leaves the current session available. The result shows a safety snapshot location
only when that snapshot was created successfully.

## Opening an Older World

When a newer Kraken version needs to upgrade a world, it first creates and checks
a recovery copy. The upgrade runs automatically. If it cannot safely convert the
saved data or create the recovery copy, the world stays unavailable for editing.
The error dialog's **Show Details** button gives the failed step, affected records,
and recovery location.

Recovery copies are kept separately from ordinary automatic backups. They include
the database, saved undo files, deleted images needed by undo, and the world
manifest when available. Some older relation formats require a new undo history;
Kraken tells you when the previous history has been archived.

Keep the recovery directory. A completed copy contains `recovery.json` with
restoration instructions; an incomplete directory without that file is not a
verified backup. Close Kraken and other database clients before restoring files,
and use the previous compatible Kraken version to open the restored world.
Live images and map assets are unchanged by these upgrades.

## Tips & Gotchas

- Use JSON for the safest lore exchange between ProjektKraken worlds.
- Use CSV when you want to edit tables in a spreadsheet. Start from a saved
  template to avoid column-mapping mistakes.
- Use Markdown notes for Obsidian-style writing and Longform DOCX/PDF for
  publishing.
- Review warnings before creating output; they describe omitted relations,
  missing images, and simplified formatting.
- Existing output is only replaced after the new export finishes successfully.
- The result page stays open so you can inspect warnings, open the output, or
  save a report.


## Historical dates in JSON imports

Text dates retain their precision and qualification, including year-only and
month-only input. Numeric lore dates keep their legacy exact meaning. If no
calendar exists, a successful text-date import installs the default calendar;
a dry run does not persist it.

For a bare date range, supply `range_meaning: "occurrence"` or
`range_meaning: "duration"` on the event. Imports reject ambiguous ranges
without this choice. Alternatively, write an explicit occurrence expression
such as `between 961 and 964`.

Semantic dates, optional duration endpoints, event anchors, chronology
constraints, and separate source claims are stored in JSON attributes and
travel with ordinary world/event exports. Keep that metadata when exchanging
records; the numeric timeline position alone cannot preserve uncertainty.

## Interface control reference

These explanations describe the software operation. Inspecting a control does not run it or read your entered values.

(help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-general-section-self-chk-enabled)=

**Enable automated backups** — Enable or disable automatic backups. Backup settings do
not restore or replace the currently open world.

(help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-general-section-self-spin-interval)=

**Auto-save interval:** — How often to create auto-save backups.

(help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-general-section-self-chk-verify)=

**Verify backup integrity after creation** — Check backup integrity after creation.
Verification does not add asset files to a database backup.

(help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-general-section-self-chk-vacuum)=

**Optimize database before backup** — Runs VACUUM to reclaim space before backup (may be
slow for large DBs).

(help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-retention-section-self-spin-auto-retention)=

**Auto-save backups:** — Number of auto-save backups to keep.

(help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-retention-section-self-spin-daily-retention)=

**Daily backups:** — Number of daily backups to keep.

(help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-retention-section-self-spin-weekly-retention)=

**Weekly backups:** — Number of weekly backups to keep.

(help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-retention-section-self-spin-manual-retention)=

**Manual backups:** — Number of manual backups to keep (-1 = unlimited).

(help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-location-section-btn-open)=

**Open backup folder** — Open the configured backup location in the system file manager.

(help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-location-section-self-edit-custom-dir)=

**Custom backup directory** — Choose a custom location for backup files. This changes
where future backups are stored.

(help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-location-section-btn-browse-custom)=

**Choose backup directory** — Choose the custom backup location with the system folder
picker.

(help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-location-section-self-edit-external-path)=

**External path** — Backups will also be copied to this location (e.g., network drive).

(help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-location-section-btn-browse-external)=

**Choose external copy location** — Choose an additional location to receive backup
copies, such as a network drive.

(help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-buttons-btn-cancel)=

**Cancel** — Cancel this BackupSettings operation without accepting its pending changes.
This is separate from applying or saving them.

(help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-buttons-btn-ok)=

**OK** — Accept the current BackupSettings choices after validation. Review the fields
first; opening Help does not accept them.

(help-inspect-src-gui-dialogs-import-preview-dialog-importpreviewdialog-init-ui-self-tree)=

**Import preview** — Review the proposed Entities, Events, relations and reported
conflicts before importing.

(help-inspect-src-gui-dialogs-import-preview-dialog-importpreviewdialog-init-ui-self-source-edit)=

**Import source name** — Name the origin of imported records, such as Obsidian. This
supports identifying records from the same source.

(help-inspect-src-gui-dialogs-import-preview-dialog-importpreviewdialog-init-ui-self-mode-combo)=

**Existing-record policy** — Choose Update to merge, Overwrite to replace fields, or
Skip to keep existing matching records unchanged.

(help-inspect-src-gui-dialogs-import-preview-dialog-importpreviewdialog-init-ui-self-dry-run-check)=

**Dry run** — Simulate the import and report its result without writing imported changes
to the world.

(help-inspect-src-gui-dialogs-import-preview-dialog-importpreviewdialog-init-ui-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-paste-json-import-dialog-pastejsonimportdialog-init-ui-self-json-edit)=

**Lore JSON** — Paste the lore JSON to import. The import review checks records before
changes are applied.

(help-inspect-src-gui-dialogs-paste-json-import-dialog-pastejsonimportdialog-init-ui-self-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-transfer-csv-dialog-transfercsvdialog-init-self-kind)=

**CSV record kind** — Choose whether the CSV represents Entities or Events so its
columns can be mapped correctly.

(help-inspect-src-gui-dialogs-transfer-csv-dialog-transfercsvdialog-init-self-table)=

**CSV columns** — Map source columns to the supported lore fields. Review the sample
before continuing.

(help-inspect-src-gui-dialogs-transfer-csv-dialog-transfercsvdialog-init-sample)=

**CSV sample** — Read sample source rows while mapping columns. This preview does not
edit the imported file.

(help-inspect-src-gui-dialogs-transfer-csv-dialog-transfercsvdialog-init-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-transfer-csv-dialog-transfercsvdialog-populate-choices)=

**Column destination** — Choose which lore field receives this CSV column, or leave it
unmapped.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-init-self-back)=

**Back** — Return to the previous transfer step without applying the proposed import or
export.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-init-self-cancel)=

**Close** — Cancel this Transfer operation without accepting its pending changes. This
is separate from applying or saving them.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-init-self-next)=

**Review transfer** — Prepare the selected transfer for review. Required source,
destination or mapping choices must be valid first.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-import-self-source-list)=

**Import sources** — Review the files selected for this import before proceeding to
record review.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-import-button)=

**Choose import source** — Choose the indicated import source type. The records are
reviewed before they are written.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-import-self-pasted-example)=

**Insert complete example** — Load a complete, valid entity/event/relation example for
editing.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-import-self-pasted)=

**Pasted** — Paste a lore JSON object here.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-import-self-mode)=

**Existing-record policy** — Choose whether matching records are skipped, merged or
replaced. Review each proposed change before applying the import.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-export-self-export-format)=

**Export format** — Choose an output format. Available document and data options depend
on this format.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-export-self-scope)=

**Export scope** — Export all lore or the current Explorer selection. This choice does
not change the selection itself.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-export-self-endpoints)=

**Include relation endpoints** — Include entries referenced by exported relations even
when those entries are outside the chosen export selection.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-export-self-title-edit)=

**Document title** — Set the title used in the exported document. This does not rename
the world or its entries.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-export-self-page-size)=

**Page size** — Choose A4 or Letter for formats that support paged output.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-export-self-contents)=

**Contents list** — Include a contents list in supported document output.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-export-self-images)=

**Referenced images** — Include referenced images in supported export output.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-export-self-destination)=

**Destination** — Choose where the output will be saved.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-export-choose)=

**Choose destination** — Choose the output file or folder for the selected export
format.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-world-self-world-mode)=

**Portable world operation** — Choose whether to export the current world with assets or
import a package as a separate new world.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-world-self-package-path)=

**World package path** — Review the portable-world package selected for import or
export. A portable package includes assets; a database backup does not.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-world-self-package-button)=

**Choose world package** — Choose the portable-world package to read or write for this
transfer.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-world-self-world-name)=

**World name** — New world folder name (required for import).

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-world-button)=

**World and backup tools** — Open the indicated specialist workflow: database backup
creation, backup restoration or world management. Restoration replaces saved database
content; it is separate from portable-world import.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-reference-self-template-kind)=

**Reference template kind** — Choose the kind of import reference or example to create.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-reference-button)=

**Save import template** — Save the selected kind of CSV template or JSON example for
preparing external lore data.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-reference-button-2)=

**Open specialist tool** — Open the indicated map-image, raster, gallery or analysis
workflow. Each tool handles its own source selection and confirmation.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-review-self-tree)=

**Transfer review** — Review each proposed record and its action before applying the
transfer.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-review-self-details)=

**Details** — Select a record to inspect or correct its JSON fields.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-review-self-diagnostics)=

**Transfer diagnostics** — Read validation errors and warnings for this proposed
transfer. Correct the source or review fields, then recheck.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-review-self-recheck)=

**Recheck edited records** — Apply edits within the transfer review and rerun
validation. This does not yet commit the import to the world.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-results-self-results)=

**Transfer results** — Read the completed transfer's counts, warnings and output
location.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-results-self-open-file)=

**Open output file** — Open the completed export file with the system's associated
application.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-results-self-open-folder)=

**Open output folder** — Open the completed transfer's output folder in the system file
manager.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-build-results-save)=

**Save transfer report** — Write the transfer result report to a chosen file without
changing world content.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-show-import-review-action)=

**Record action** — Choose how this proposed import record should be handled, such as
creating, updating or skipping it.

(help-inspect-src-gui-dialogs-transfer-dialog-transferdialog-show-import-review-match)=

**Record match** — Choose the existing world entry that this imported record should
match. Review the proposed fields before applying.

(help-inspect-src-app-ui-manager-uimanager-create-file-menu-transfer-action)=

**Import and export** — Open the transfer workflow for lore records, documents, portable
worlds and reference templates.

(help-inspect-src-app-ui-manager-uimanager-create-file-menu-backup-menu)=

**Backup &amp;&amp; Restore** — Open the Backup Restore menu to choose a related
operation. Opening the menu does not apply any of its actions.

(help-inspect-src-app-ui-manager-uimanager-create-file-menu-backup-action)=

**Create backup** — Save a backup of the world's database. Asset files are separate; use
portable-world export to include assets.

(help-inspect-src-app-ui-manager-uimanager-create-file-menu-restore-action)=

**Restore backup** — Replace the active world's database with a selected backup after
confirmation. This is recovery, not an ordinary undo step; assets are not restored by a
database backup.

(help-inspect-src-app-ui-manager-uimanager-create-file-menu-location-action)=

**Show backup location** — Open the configured backup folder in the system file manager.

(help-inspect-src-app-ui-manager-uimanager-create-file-menu-settings-action)=

**Backup settings** — Configure automatic backups, retention and storage locations
without restoring a backup.
