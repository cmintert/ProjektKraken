"""
Application Constants.
Stores default values for UI configuration and magic numbers.
"""

# Window Configuration
WINDOW_TITLE = "Project Kraken - v0.6.0 (Beta)"
DEFAULT_WINDOW_WIDTH = 1280
DEFAULT_WINDOW_HEIGHT = 720
WINDOW_SETTINGS_KEY = "ChristianMintert"
WINDOW_SETTINGS_APP = "ProjektKraken"
SETTINGS_ACTIVE_DB_KEY = "active_world"  # Now stores world name, not filename
SETTINGS_LAYOUTS_KEY = "saved_layouts"
SETTINGS_LAST_ITEM_ID_KEY = "last_selected_item_id"
SETTINGS_LAST_ITEM_TYPE_KEY = "last_selected_item_type"
SETTINGS_AUTO_RELATION_KEY = "wiki/auto_create_relations"
SETTINGS_FILTER_CONFIG_KEY = "tag_filter_config"


# Dock Titles
# Dock Object Names
DOCK_OBJ_PROJECT = "ProjectExplorerDock"
DOCK_OBJ_EVENT_INSPECTOR = "EventInspectorDock"
DOCK_OBJ_ENTITY_INSPECTOR = "EntityInspectorDock"
DOCK_OBJ_TIMELINE = "TimelineDock"
DOCK_OBJ_LONGFORM = "LongformDock"
DOCK_OBJ_MAP = "MapDock"
DOCK_OBJ_AI_SEARCH = "AISearchDock"
DOCK_OBJ_GRAPH = "GraphDock"

# Dock Titles
DOCK_TITLE_PROJECT = "Project Explorer"
DOCK_TITLE_EVENT_INSPECTOR = "Event Inspector"
DOCK_TITLE_ENTITY_INSPECTOR = "Entity Inspector"
DOCK_TITLE_TIMELINE = "Timeline"
DOCK_TITLE_LONGFORM = "Longform Document"
DOCK_TITLE_MAP = "Map"
DOCK_TITLE_AI_SEARCH = "AI Search"
DOCK_TITLE_GRAPH = "Relationship Graph"

# Status Messages
STATUS_DB_INIT_FAIL = "Database Initialization Failed!"
STATUS_ERROR_PREFIX = "Error: "

# File Dialog Filters
SUPPORTED_IMAGE_FORMATS = ["png", "jpg", "jpeg", "bmp", "webp"]
IMAGE_FILE_FILTER = (
    f"Images ({' '.join([f'*.{ext}' for ext in SUPPORTED_IMAGE_FORMATS])})"
)
