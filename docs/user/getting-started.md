# Getting Started

## What this does

Each ProjektKraken world is a portable folder containing its lore database,
manifest, and assets. You can move or back up the whole folder without
separating its content.

Install Kraken, open a world, then use the [Northwatch tutorial](northwatch-tutorial.md)
to see how its history changes. For the storage model and the limits of a
database-only backup, see [portability and recovery](portability-and-recovery.md).

## Install and launch

### Windows

1. Open [ProjektKraken Releases](https://github.com/cmintert/ProjektKraken/releases)
   and download both files with the
   same version:
   - `ProjektKraken-0.20.1-beta1-windows-x64.zip`
   - `ProjektKraken-0.20.1-beta1-windows-x64.zip.sha256`
2. Put these two files in a folder of their own. Open PowerShell in that
   folder and run:

   ```powershell
   Get-FileHash *.zip `
     -Algorithm SHA256
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

The filenames above illustrate 0.20.1 beta 1. Use the exact filename of the
release you download and read its release notes before updating an existing
installation. For a source checkout, follow the
[developer setup](https://github.com/cmintert/ProjektKraken/blob/main/docs/developer/development.md).

(help-world-manage)=

## Create or open a world

1. Open **File → Manage Databases…**.
2. Choose **Create New** and enter the new world's details, or choose
   **Add World Folder** and select an existing complete world folder.
3. Select the world in the list and choose **Select & Restart**. Resolve any
   unfinished work before accepting the restart.
4. The active world name appears in the application title.

Registration leaves the folder where it is. If the configured database is
missing, obtain the complete world instead of treating a new empty world as
recovery. **Cancel** closes World Manager without switching worlds.

World folders are stored under `worlds/` in portable installations:

```text
worlds/
└── My World/
    ├── world.json
    ├── My World.kraken
    └── assets/
```

## First workflow

Follow [Explore a changing kingdom](northwatch-tutorial.md) to compare two
dates in a prepared world. To start writing your own world instead, follow
{ref}`Create an event or entity <help-authoring-create>`, then
{ref}`Add details <help-authoring-details>`. The creation and editing procedures
remain in that chapter so their save and recovery instructions have one home.

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

## Interface control reference

These explanations describe the software operation. Inspecting a control does not run it or read your entered values.

(help-inspect-src-gui-dialogs-database-manager-dialog-databasemanagerdialog-init-self-db-list)=

**Worlds** — Choose the managed world for the adjacent world-management actions. Select
and Restart deliberately switches to it.

(help-inspect-src-gui-dialogs-database-manager-dialog-databasemanagerdialog-init-self-btn-create)=

**Create New** — Create a new world in the default worlds folder.

(help-inspect-src-gui-dialogs-database-manager-dialog-databasemanagerdialog-init-self-btn-add-folder)=

**Add World Folder** — Register an existing complete world folder without moving it.

(help-inspect-src-gui-dialogs-database-manager-dialog-databasemanagerdialog-init-self-btn-open-folder)=

**Open Folder** — Open the selected world's folder, or the default worlds folder.

(help-inspect-src-gui-dialogs-database-manager-dialog-databasemanagerdialog-init-self-btn-link-external)=

**Link External DB** — Use a selected external .kraken database for the selected world.

(help-inspect-src-gui-dialogs-database-manager-dialog-databasemanagerdialog-init-self-btn-revoke-external)=

**Revoke External DB** — Remove approval for the selected world's external database.

(help-inspect-src-gui-dialogs-database-manager-dialog-databasemanagerdialog-init-self-btn-delete)=

**Delete** — Delete the selected managed world after confirmation. This is world
management, not an ordinary undoable entry deletion; keep a recovery copy first.

(help-inspect-src-gui-dialogs-database-manager-dialog-databasemanagerdialog-init-self-btn-select)=

**Select &amp;&amp; Restart** — Make the selected world active, then restart to open it.

(help-inspect-src-gui-dialogs-database-manager-dialog-databasemanagerdialog-init-self-btn-close)=

**Cancel** — Close World Manager without changing worlds.

(help-inspect-src-app-ui-manager-uimanager-create-file-menu-db-action)=

**Manage worlds** — Create, register, delete or choose a world. Switching worlds is
deliberate and separate from ordinary content undo.
