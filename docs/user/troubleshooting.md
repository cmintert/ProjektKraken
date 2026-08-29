# Troubleshooting

## The app does not start

1. Confirm that you extracted the complete ZIP before launching it.
2. Confirm that `ProjektKraken.exe` and `_internal` are in the same extracted
   `ProjektKraken` folder.
3. Move the extracted folder to a normal user location such as Documents or
   Desktop, then double-click `ProjektKraken.exe` again.
4. Verify the ZIP against its supplied `.sha256` file. Download it again if the
   hashes differ.

Normal diagnostics are written to `logs/kraken.log` beside the executable.
Include that file, the package version, and your Windows version when reporting
a startup problem.

## A saved layout prevents startup

If the application opens, choose **Layouts → Reset Layout**. This restores the
default panel arrangement without deleting world folders.

## AI models are not listed

- Confirm LM Studio is running.
- Enter only the server address.
- Refresh models after loading or unloading a model in LM Studio.
- Generation and embedding may require different models.

## Raster editing has paused

Raster editing pauses when a save fails or the selected raster target becomes
stale. Read the visible error, reselect an existing Base or dated state, and
resume only after the underlying save problem is resolved.

## A panel seems to be missing

Choose the panel under **View → Panels**. Kraken reopens its current zone and
activates the panel wherever you moved it. Use **Layouts → Reset Layout** when
necessary.

## Changes are not where expected

Confirm the active world in the title bar, the selected inspector item, the
active map, and the timeline playhead. Dated map content may change as the
playhead moves.
