"""
Main Application Module (Legacy Shim).

This module has been refactored:
- MainWindow class is now in src.app.main_window
- Application entry point is now in src.app.entry

This shim preserves backward compatibility for existing imports.
"""

# Re-export MainWindow for backward compatibility
from src.app.main_window import MainWindow  # noqa: F401

# Re-export entry point functions
from src.app.entry import cleanup_app, main  # noqa: F401

# Support direct execution
if __name__ == "__main__":
    main()
