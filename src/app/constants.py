"""
Application Constants.
Stores default values for UI configuration and magic numbers.
"""

# Window Configuration
WINDOW_TITLE = "Project Kraken - v0.2.0 (Editor Phase)"
DEFAULT_WINDOW_WIDTH = 1280
DEFAULT_WINDOW_HEIGHT = 720
WINDOW_SETTINGS_KEY = "Antigravity"
WINDOW_SETTINGS_APP = "ProjectKraken_v0.3.1"

# Dock Titles
# Dock Object Names
DOCK_OBJ_PROJECT = "ProjectExplorerDock"
DOCK_OBJ_EVENT_INSPECTOR = "EventInspectorDock"
DOCK_OBJ_ENTITY_INSPECTOR = "EntityInspectorDock"
DOCK_OBJ_TIMELINE = "TimelineDock"
DOCK_OBJ_LONGFORM = "LongformDock"
DOCK_OBJ_MAP = "MapDock"

# Dock Titles
DOCK_TITLE_PROJECT = "Project Explorer"
DOCK_TITLE_EVENT_INSPECTOR = "Event Inspector"
DOCK_TITLE_ENTITY_INSPECTOR = "Entity Inspector"
DOCK_TITLE_TIMELINE = "Timeline"
DOCK_TITLE_LONGFORM = "Longform Document"
DOCK_TITLE_MAP = "Map"

# Status Messages
STATUS_DB_INIT_FAIL = "Database Initialization Failed!"
STATUS_ERROR_PREFIX = "Error: "

# File Dialog Filters
SUPPORTED_IMAGE_FORMATS = ["png", "jpg", "jpeg", "bmp", "webp"]
IMAGE_FILE_FILTER = f"Images ({' '.join(['*.' + ext for ext in SUPPORTED_IMAGE_FORMATS])})"
