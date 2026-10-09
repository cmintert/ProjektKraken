# Troubleshooting

## The app does not start

1. Confirm that you extracted the complete ZIP before launching it.
2. Confirm that `ProjektKraken.exe` and `_internal` are in the same extracted
   `ProjektKraken` folder.
3. Move the extracted folder to a normal user location such as Documents or
   Desktop, then double-click `ProjektKraken.exe` again.
4. Verify the ZIP against its supplied `.sha256` file. Download it again if the
   hashes differ.

Normal diagnostics are written to `logs/kraken.<process ID>.log` beside the
executable. Each running instance has its own log and rotation set; old process
logs can be removed after those instances exit. If the portable `logs` directory
is unwritable, look in `%APPDATA%\ProjektKraken\logs` on Windows (or the platform
user data directory). Log files rotate at 5 MB with five backups per process.
If rotation fails, writes to that file pause for 30 seconds before another
attempt; a `*.logging-error.txt` file beside it records the latest failure.
Logging failures do not stop edits or saves. Include the relevant log and
failure notice, the package version, and your Windows version when reporting a
problem. AI audit logging is opt-in, uses separate per-process files, and remains
isolated from normal diagnostics.

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
