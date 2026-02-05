# Installation Guide

This guide covers how to install and set up ProjektKraken on Windows, macOS, and Linux.

## System Requirements

### Minimum Requirements
- **OS**: Windows 10+, macOS 10.15+, or Linux (Ubuntu 20.04+ or equivalent)
- **RAM**: 4 GB
- **Storage**: 500 MB for application + space for your worlds
- **Display**: 1280x720 or higher resolution

### Recommended Requirements
- **RAM**: 8 GB or more
- **Storage**: 2 GB+ for comfortable usage
- **Display**: 1920x1080 or higher

### Optional Requirements
For AI features (Semantic Search, LLM Generation):
- **LM Studio** or compatible OpenAI-compatible API server
- **Additional RAM**: 4-8 GB for local AI models

## Installation Methods

### Method 1: Windows Executable (Recommended for Windows)

The easiest way to run ProjektKraken on Windows is using the pre-built executable.

1. **Download the Latest Release**
   - Visit [GitHub Releases](https://github.com/cmintert/ProjektKraken/releases)
   - Download `ProjektKraken-vX.X.X-windows.zip`

2. **Extract the Archive**
   - Extract the ZIP file to your desired location (e.g., `C:\ProjektKraken\`)
   - No installation wizard required - it's portable!

3. **Run ProjektKraken**
   - Double-click `ProjektKraken.exe`
   - The `worlds/` directory will be created automatically on first run

4. **Create a Shortcut** (Optional)
   - Right-click `ProjektKraken.exe`
   - Select **Send to → Desktop (create shortcut)**

**Note**: The application is portable. You can move the entire folder to a USB drive or another location without any configuration changes.

### Method 2: From Source (All Platforms)

Running from source gives you the latest features and allows for customization.

#### Step 1: Install Python

**Windows:**
1. Download Python 3.11+ from [python.org](https://www.python.org/downloads/)
2. During installation, check **"Add Python to PATH"**
3. Verify installation:
   ```bash
   python --version
   ```

**macOS:**
```bash
# Using Homebrew
brew install python@3.11
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# Fedora
sudo dnf install python3.11
```

#### Step 2: Clone the Repository

```bash
# Using Git
git clone https://github.com/cmintert/ProjektKraken.git
cd ProjektKraken
```

Or download and extract the ZIP from GitHub.

#### Step 3: Create Virtual Environment

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- PySide6 (Qt 6) - GUI framework
- NumPy - Numerical operations
- pytest - Testing framework
- And other required packages

#### Step 5: Run ProjektKraken

```bash
python launcher.py
```

Or:
```bash
python -m src.app.main
```

## Post-Installation Setup

### First Launch

1. **Launch the Application**
   - Windows: Run `ProjektKraken.exe` or `python launcher.py`
   - The application will create necessary directories

2. **Directory Structure Created**
   ```
   ProjektKraken/
   ├── ProjektKraken.exe (or source files)
   └── worlds/              # Created on first run
   ```

3. **User Settings Location**
   - Windows: `%APPDATA%\ProjektKraken\`
   - macOS: `~/Library/Application Support/ProjektKraken/`
   - Linux: `~/.local/share/ProjektKraken/`

### Optional: Set Up AI Features

If you want to use Semantic Search and LLM Generation:

1. **Install LM Studio**
   - Download from [lmstudio.ai](https://lmstudio.ai/)
   - Install and launch LM Studio

2. **Download an Embedding Model**
   - In LM Studio, search for "bge-small-en-v1.5" or similar
   - Download the model

3. **Start the Local Server**
   - In LM Studio, go to the "Local Server" tab
   - Select your embedding model
   - Start the server (default: http://localhost:8080)

4. **Configure Environment Variables** (Optional)
   
   **Windows:**
   ```cmd
   setx EMBED_PROVIDER lmstudio
   setx LMSTUDIO_EMBED_URL http://localhost:8080/v1/embeddings
   setx LMSTUDIO_MODEL bge-small-en-v1.5
   ```

   **macOS/Linux:**
   ```bash
   export EMBED_PROVIDER=lmstudio
   export LMSTUDIO_EMBED_URL=http://localhost:8080/v1/embeddings
   export LMSTUDIO_MODEL=bge-small-en-v1.5
   ```

5. **Build Search Index**
   ```bash
   python -m src.cli.index rebuild --database "worlds/My World/My World.kraken"
   ```

See the [User Guide](USER_GUIDE.md#semantic-search) for more details on AI features.

## Troubleshooting

### Application Won't Start

**Problem**: Application crashes immediately on launch

**Solution**: Reset your settings
```bash
python launcher.py --reset-settings
```

This clears window layout and preferences, allowing a fresh start.

### Missing Python Module Errors (Source Installation)

**Problem**: `ModuleNotFoundError: No module named 'PySide6'`

**Solution**: Ensure virtual environment is activated and dependencies installed
```bash
# Windows
.venv\Scripts\activate
pip install -r requirements.txt

# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
```

### Qt Platform Plugin Error (Linux)

**Problem**: `qt.qpa.plugin: Could not load the Qt platform plugin`

**Solution**: Install Qt dependencies
```bash
# Ubuntu/Debian
sudo apt install libxcb-xinerama0 libxcb-cursor0

# Fedora
sudo dnf install xcb-util-cursor
```

### High DPI Display Issues

**Problem**: UI appears too small or blurry

**Solution**: ProjektKraken has High DPI support enabled by default. If issues persist:
- Windows: Check display scaling in Settings → System → Display
- macOS: Should work automatically
- Linux: Set `QT_AUTO_SCREEN_SCALE_FACTOR=1` environment variable

### Permission Errors on Windows

**Problem**: "Access Denied" when running executable

**Solution**:
1. Right-click `ProjektKraken.exe`
2. Select **Properties → Security**
3. Ensure your user account has "Full Control"
4. Or run the executable from a location you own (not Program Files)

## Updating ProjektKraken

### Updating Executable Version

1. Download the new version from GitHub Releases
2. Extract to a new folder or replace the old files
3. Your `worlds/` folder is separate and safe
4. Copy your `worlds/` folder to the new location if needed

### Updating Source Installation

```bash
cd ProjektKraken
git pull origin main
.venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt --upgrade
```

## Uninstallation

### Executable Version

1. Delete the ProjektKraken folder
2. **Important**: Backup your `worlds/` folder first if you want to keep your data
3. Delete user settings (optional):
   - Windows: `%APPDATA%\ProjektKraken\`
   - macOS: `~/Library/Application Support/ProjektKraken/`
   - Linux: `~/.local/share/ProjektKraken/`

### Source Installation

1. Deactivate virtual environment: `deactivate`
2. Delete the repository folder
3. Delete user settings (optional, see above)

## Next Steps

- Create your first world: See [User Guide](USER_GUIDE.md#creating-a-new-world)
- Learn the interface: See [User Guide](USER_GUIDE.md#interface-overview)
- Explore workflows: See [Workflows](WORKFLOWS.md)

---

**Need Help?** Check the [FAQ](FAQ.md) or open an issue on [GitHub](https://github.com/cmintert/ProjektKraken/issues).
