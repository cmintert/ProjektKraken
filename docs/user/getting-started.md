# Getting Started

## What this does

Each ProjektKraken world is a portable folder containing its lore database,
manifest, and assets. You can move or back up the whole folder without
separating its content.

## Install and launch

### Windows

1. Open the ProjektKraken release on GitHub and download both files with the
   same version:
   - `ProjektKraken-0.19.5-beta1-windows-x64.zip`
   - `ProjektKraken-0.19.5-beta1-windows-x64.zip.sha256`
2. Open PowerShell in the download folder and run:

   ```powershell
   Get-FileHash .\ProjektKraken-0.19.5-beta1-windows-x64.zip -Algorithm SHA256
   ```

3. Compare the reported hash with the value in the `.sha256` file. The letters
   may use different capitalization, but every character must match.
4. Extract the complete ZIP into an ordinary user folder such as Documents or
   Desktop. Do not launch the application from inside the ZIP.
5. Open the extracted `ProjektKraken` folder and double-click
   `ProjektKraken.exe`.

No Python installation, command prompt, or `start-kraken.cmd` is required.
Keep the `_internal` folder beside `ProjektKraken.exe`; it contains the files
the application needs.

## Create or open a world

1. Open **File → Manage Databases…**.
2. Create a world, or choose **Add World Folder** to register an existing complete
   world folder from a local, removable, network, or synchronized location.
3. Confirm the selection.
4. The active world name appears in the application title.

World folders are stored under `worlds/` in portable installations:

```text
worlds/
└── My World/
    ├── world.json
    ├── My World.kraken
    └── assets/
```

## First workflow

1. In the Explorer, open the **New** menu.
2. Create an event, entity, or map.
3. Select the new item to open its inspector.
4. Add a description, attributes, tags, images, or relations.
5. Open the Timeline, Map, Graph, or Longform dock when you need another view.

## Tips and gotchas

- Copy the entire world folder when transferring a world.
- **Link External DB** is an advanced option for an existing `.kraken` file outside
  the world folder. It reduces portability, separates backup locations, and is not
  suitable for simultaneous multi-user editing. ProjektKraken asks you to confirm
  the resolved path and lets you revoke that approval later.
- A missing linked external database is never replaced with an empty database.
- Do not edit the `.kraken` file while the world is open.
- Use **File → Backup & Restore** before imports or large restructuring work.
- Use **Layouts → Reset Layout** if saved panels make the workspace difficult
  to use. This resets interface preferences, not the contents of your world.
