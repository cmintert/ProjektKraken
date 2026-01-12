# Distribution Guide

This guide describes how to build and distribute **ProjektKraken**.

## Build Type: Folder (Onedir)

We build the application as a **Folder** (not a single file). This ensures that the `assets` folder remains accessible and editable by the user, and that themes/data are easily inspected.

### Prerequisites

- Python 3.10+
- `pip install -r requirements.txt` (including `pyinstaller`)

### How to Build

Run the following command in the project root:

```powershell
pyinstaller ProjektKraken.spec --clean --noconfirm
```

This will create a `dist/ProjektKraken` folder.

### How to Distribute

1.  Navigate to the `dist` folder.
2.  **Zip the `ProjektKraken` folder**.
3.  Share the `.zip` file.

> [!IMPORTANT]
> **Do not move the .exe file out of its folder.**
> The executable depends on the libraries and assets next to it.
> To run it from the Desktop, users must **Create a Shortcut** to `ProjektKraken.exe` and move the shortcut to the Desktop.

### Directory Structure

The built folder looks like this (PyInstaller 6+):

```
ProjektKraken/
├── ProjektKraken.exe      <-- The main executable
└── _internal/             <-- Dependencies and resources
    ├── assets/            <-- Default assets
    ├── themes.json        <-- Default themes
    └── src/
        └── resources/
```

### Verification
After building, verify that `themes.json` exists in `dist/ProjektKraken/_internal`. 
**Note**: You can place a custom `themes.json` next to the `.exe` to override the defaults.
