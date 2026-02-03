# Running Tests

## Requirements

ProjektKraken tests require Qt/OpenGL libraries for PySide6:

### Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install -y \
    libegl1 \
    libgl1 \
    libxkbcommon-x11-0 \
    libdbus-1-3 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-render-util0 \
    libxcb-xinerama0
```

### Fedora/RHEL:
```bash
sudo dnf install -y \
    mesa-libEGL \
    mesa-libGL \
    libxkbcommon-x11 \
    dbus-libs
```

### MacOS:
No additional libraries needed (Qt bundled).

### Windows:
No additional libraries needed (Qt bundled).

## Running Tests

Once dependencies are installed:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_unified_list_features.py

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run only unit tests
pytest tests/unit/

# Run headless (Linux only, requires libraries above)
QT_QPA_PLATFORM=offscreen pytest
```

## GitHub Actions / CI

For CI environments, add this step before running tests:

```yaml
- name: Install Qt dependencies
  run: |
    sudo apt-get update
    sudo apt-get install -y libegl1 libgl1 libxkbcommon-x11-0 libdbus-1-3
    
- name: Run tests
  run: |
    export QT_QPA_PLATFORM=offscreen
    pytest --cov=src
```

## Docker

```dockerfile
FROM python:3.12

# Install Qt dependencies
RUN apt-get update && apt-get install -y \
    libegl1 \
    libgl1 \
    libxkbcommon-x11-0 \
    libdbus-1-3 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Run tests headless
ENV QT_QPA_PLATFORM=offscreen
CMD ["pytest"]
```

## Troubleshooting

### Error: `libEGL.so.1: cannot open shared object file`

**Solution:** Install the Qt/OpenGL libraries listed above.

### Error: `cannot connect to X server`

**Solution:** Use offscreen rendering:
```bash
export QT_QPA_PLATFORM=offscreen
pytest
```

### Tests hang or freeze

**Solution:** Check if a display server is blocking. Use offscreen mode or install xvfb:
```bash
sudo apt-get install xvfb
xvfb-run pytest
```
