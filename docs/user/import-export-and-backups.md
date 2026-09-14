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

## Back Up and Restore

Use **File → Backup & Restore** or the shortcuts in **World Transfer &
Backups** to create, restore, locate, and configure backups.

Restoring a `.kraken` backup replaces the active world's saved data and is not
an ordinary undoable action. Backups do not contain asset files. Use a portable
world package when maps and other assets need to travel with the world.

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
