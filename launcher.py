"""
ProjektKraken Launcher.
Entry point for PyInstaller to ensure correct package resolution.
"""

import os
import sys

# Add src to path just in case, though root launcher usually solves this
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from src.app.main import main

if __name__ == "__main__":
    main()
