---
description: Build the ProjektKraken desktop application
---

This workflow describes how to package ProjektKraken into a standalone Windows executable.

### Prerequisites

1.  Ensure you are in the project root.
2.  Ensure your virtual environment is active and all dependencies are installed.
    ```pwsh
    pip install -r requirements.txt
    pip install pyinstaller
    ```

### Build Steps

// turbo
1. Run PyInstaller with the provided spec file:
   ```pwsh
   pyinstaller ProjektKraken.spec
   ```

### Post-Build

1.  The executable and its dependencies will be in the `dist/ProjektKraken/` folder.
2.  Run `dist/ProjektKraken/ProjektKraken.exe` to start the application.

### Updating the Build

If you add new assets or source folders:
1.  Update `added_files` in `ProjektKraken.spec` if needed.
2.  Rerun the build command.
