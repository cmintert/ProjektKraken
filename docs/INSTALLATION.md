# Installation Guide

**Version:** 0.18.6 (Beta)
**Last Updated:** July 2026

This guide covers installation, system requirements, and initial setup for ProjektKraken.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation Methods](#installation-methods)
3. [First-Time Setup](#first-time-setup)
4. [Verification](#verification)
5. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| **Operating System** | Windows 10+, macOS 10.15+, or Linux (Ubuntu 20.04+) |
| **Python** | 3.13+ (for source installation) |
| **RAM** | 4 GB minimum, 8 GB recommended |
| **Storage** | 500 MB for application, additional space for worlds |
| **Display** | 1280x720 minimum, 1920x1080 recommended |

### Recommended for Optimal Performance

- **CPU**: Multi-core processor for better graph rendering
- **RAM**: 16 GB for large worlds (10,000+ entities)
- **Storage**: SSD for faster database operations
- **Display**: 2560x1440 or higher for multi-panel workflows

---

## Installation Methods

### Option 1: Windows Executable (Recommended for End Users)

The easiest way to install ProjektKraken on Windows.

**Steps:**

1. **Download** the latest release from [GitHub Releases](https://github.com/cmintert/ProjektKraken/releases)
   - Download `ProjektKraken-v0.18.6-Windows.zip`

2. **Extract** the archive to your desired location
   ```
   C:\ProjektKraken\
   ```

3. **Run** the executable
   - Double-click `ProjektKraken.exe`
   - Windows may show a security warning (click "More info" → "Run anyway")

4. **Create Desktop Shortcut** (optional)
   - Right-click `ProjektKraken.exe` → "Send to" → "Desktop (create shortcut)"

**Portable Architecture:**  
ProjektKraken stores all worlds in a `worlds/` folder next to the executable. You can move the entire folder to another location or computer without issues.

---

### Option 2: Python Source Installation (For Developers)

For developers who want to modify the code or run from source.

#### Prerequisites

- Python 3.13 or higher
- pip package manager
- Git (optional, for cloning)

#### Steps

1. **Clone or Download** the repository

   ```bash
   git clone https://github.com/cmintert/ProjektKraken.git
   cd ProjektKraken
   ```

   Or download and extract the ZIP from GitHub.

2. **Create Virtual Environment** (recommended)

   ```bash
   python -m venv .venv
   ```

3. **Activate Virtual Environment**

   - **Windows:**
     ```bash
     .venv\Scripts\activate
     ```

   - **macOS/Linux:**
     ```bash
     source .venv/bin/activate
     ```

4. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

5. **Run Application on Windows**

   ```powershell
   .\start-kraken.cmd
   ```

   Double-clicking `start-kraken.cmd` does the same thing. It prefers the local
   `.venv`, checks Python and required runtime modules, and displays a useful error
   if startup fails.

   On any platform, the underlying entry point is:

   ```bash
   python -m src.app.main
   ```

The current `requirements.txt` includes the application, testing, documentation,
quality, and packaging dependencies used by this repository.

---

### Option 3: Building from Source (Advanced)

Create a standalone executable using PyInstaller.

#### Prerequisites

- Python 3.13+
- All dependencies installed
- PyInstaller

#### Steps

1. **Install PyInstaller**

   ```bash
   pip install pyinstaller
   ```

2. **Build Executable**

   ```bash
   pyinstaller ProjektKraken.spec
   ```

3. **Locate Executable**

   The built executable will be in:
   ```
   dist/ProjektKraken/ProjektKraken.exe  (Windows)
   dist/ProjektKraken/ProjektKraken      (macOS/Linux)
   ```

4. **Bundle Assets** (if needed)

   Copy required assets:
   - `themes.json`
   - `default_assets/` folder

---

## First-Time Setup

### Initial Launch

1. **Launch ProjektKraken**
   - Double-click the executable or `start-kraken.cmd`

2. **Welcome Screen**
   - You'll see the main window with an empty project explorer
   - The `worlds/` directory is automatically created

### Creating Your First World

1. **Create New World**
   - Click **File → New World** (Ctrl+N)
   - Or click the "+" button in the Project Explorer

2. **Enter World Details**
   - **Name**: e.g., "My Fantasy World"
   - **Description**: Optional brief description
   - Click **Create**

3. **World Structure Created**
   ```
   worlds/
   └── My Fantasy World/
       ├── world.json           # World manifest
       ├── My Fantasy World.kraken  # SQLite database
       └── assets/              # Assets folder
           ├── images/          # Full-size images
           ├── thumbnails/      # Thumbnails
           └── .trash/          # Deleted files (for undo)
   ```

### User Preferences Location

ProjektKraken stores user preferences (window layouts, settings, backups) in:

- **Windows**: `%APPDATA%\ProjektKraken\`
- **macOS**: `~/Library/Application Support/ProjektKraken/`
- **Linux**: `~/.local/share/ProjektKraken/`

---

## Verification

### Verify Installation

1. **Check Version**
   - Open ProjektKraken
   - Go to **Help → About**
   - Verify version is **0.18.6**

2. **Test Basic Functionality**
   - Create a new world
   - Create a test event (**Events → New Event**)
   - Create a test entity (**Entities → New Entity**)
   - Link them together (drag entity onto event)

3. **Check Database**
   - Navigate to `worlds/[World Name]/`
   - Verify `.kraken` database file exists
   - Open with any SQLite viewer (optional)

### Verify Python Installation (Source Only)

```bash
# Check Python version
python --version
# Should show Python 3.13.x or higher

# Check Python and all required runtime modules
python launcher.py --check

# Run tests (optional)
pytest tests/
```

---

## Troubleshooting

### Common Issues

#### Windows: "Windows protected your PC" Warning

**Problem**: Windows SmartScreen blocks the executable.

**Solution**:
1. Click "More info"
2. Click "Run anyway"
3. This is expected for unsigned executables

#### Missing Dependencies Error

**Problem**: ImportError or ModuleNotFoundError.

**Solution**:
```bash
pip install -r requirements.txt --force-reinstall
```

#### Python Version Too Old

**Problem**: "Python 3.13 or higher required".

**Solution**:
1. Download Python 3.13+ from [python.org](https://python.org)
2. During installation, check "Add Python to PATH"
3. Restart terminal and verify: `python --version`

#### Database Lock Error

**Problem**: "database is locked" error.

**Solution**:
1. Close all ProjektKraken instances
2. Check for orphaned processes: Task Manager (Windows) or Activity Monitor (macOS)
3. Delete `.kraken-shm` and `.kraken-wal` files in world folder
4. Reopen ProjektKraken

#### High DPI Scaling Issues

**Problem**: Blurry or oversized UI on high-DPI displays.

**Solution**:
ProjektKraken automatically handles DPI scaling. If issues persist:

- **Windows**: Right-click `ProjektKraken.exe` → Properties → Compatibility → Change high DPI settings → Override scaling behavior
- **Linux**: Set `QT_AUTO_SCREEN_SCALE_FACTOR=1` environment variable

#### Crash on Startup

**Problem**: Application crashes immediately on launch.

**Solution**:
1. **Check Logs**:
   - Source checkout: `<project folder>\logs\kraken.log`
   - Packaged application: `<folder containing ProjektKraken.exe>\logs\kraken.log`
   - Preflight/startup failures: the adjacent `logs\startup_error.log`

2. **Reset Settings**:
   - Windows source checkout: `start-kraken.cmd --reset-settings`
   - Cross-platform source checkout: `python launcher.py --reset-settings`
   - This clears QSettings-managed preferences, including the saved window layout
     and active database selection. It does not delete worlds.

3. **Reinstall**:
   - Delete application folder
   - Re-extract from ZIP or reinstall

#### Cannot Create World

**Problem**: "Failed to create world" error.

**Solution**:
1. Verify write permissions to `worlds/` folder
2. Check disk space (minimum 100 MB free)
3. Try creating world in a different location

---

## Platform-Specific Notes

### Windows

- **Antivirus**: Some antivirus programs may flag ProjektKraken. Add it to your exceptions list.
- **Long Paths**: If world names are very long, enable long path support in Windows 10+.

### macOS

- **Gatekeeper**: First launch requires right-click → Open (if built locally).
- **Permissions**: May need to grant file system access in System Preferences → Security & Privacy.

### Linux

- **Desktop Integration**: Create `.desktop` file for application launcher:

  ```ini
  [Desktop Entry]
  Type=Application
  Name=ProjektKraken
  Exec=/path/to/ProjektKraken
  Icon=/path/to/icon.png
  Categories=Utility;Office;
  ```

- **Qt Platform**: If UI issues occur, try setting:
  ```bash
  export QT_QPA_PLATFORM=xcb
  ```

---

## Next Steps

After installation:

1. **[Read the User Guide](USER_GUIDE.md)** - Learn core concepts and features
2. **[Explore Workflows](WORKFLOWS.md)** - Step-by-step guides for common tasks
3. **[Check FAQ](FAQ.md)** - Common questions and tips

---

## Getting Help

- **Documentation**: Full docs at [docs/INDEX.md](INDEX.md)
- **Issues**: Report problems on [GitHub Issues](https://github.com/cmintert/ProjektKraken/issues)
- **Discussions**: Ask questions on [GitHub Discussions](https://github.com/cmintert/ProjektKraken/discussions)

---

**Navigation:**  
[← Back to Index](INDEX.md) • [User Guide →](USER_GUIDE.md)
