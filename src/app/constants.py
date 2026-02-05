"""Application Constants.

Stores default values for UI configuration and magic numbers.
"""

# Window Configuration
VERSION = "0.10.3"
WINDOW_TITLE = f"Project Kraken - v{VERSION} (Beta)"
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
SETTINGS_LAYOUT_VERSION_KEY = "layout_version"

# Layout Version (increment when layout structure changes incompatibly)
LAYOUT_VERSION = "1.0.0"


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
DOCK_OBJ_HISTORY = "HistoryDock"

# Dock Titles
DOCK_TITLE_PROJECT = "Project Explorer"
DOCK_TITLE_EVENT_INSPECTOR = "Event Inspector"
DOCK_TITLE_ENTITY_INSPECTOR = "Entity Inspector"
DOCK_TITLE_TIMELINE = "Timeline"
DOCK_TITLE_LONGFORM = "Longform Document"
DOCK_TITLE_MAP = "Map"
DOCK_TITLE_AI_SEARCH = "AI Search"
DOCK_TITLE_GRAPH = "Relationship Graph"
DOCK_TITLE_HISTORY = "History"

# Status Messages
STATUS_DB_INIT_FAIL = "Database Initialization Failed!"
STATUS_ERROR_PREFIX = "Error: "


# File Dialog Filters
SUPPORTED_IMAGE_FORMATS = ["png", "jpg", "jpeg", "bmp", "webp"]
IMAGE_FILE_FILTER = (
    f"Images ({' '.join([f'*.{ext}' for ext in SUPPORTED_IMAGE_FORMATS])})"
)

# Autosave Configuration
AUTOSAVE_DELAY_MS = 2000  # 2 seconds

# UI Timing Constants
# Delays for deferred initialization and UI updates
UI_INIT_DELAY_MS = 100  # Initial delay for completing app initialization
UI_DOCK_RESTORE_DELAY_MS = 100  # Delay for restoring critical docks
UI_OPTIONAL_DOCK_DELAY_MS = 500  # Delay for restoring optional docks
UI_LAYOUT_GUARD_DELAY_MS = 100  # Delay for layout constraint resets
UI_SEARCH_INDEX_REFRESH_DELAY_MS = 100  # Delay for search index status refresh
UI_CLEANUP_DELAY_MS = 200  # Delay for cleanup operations

# Provider Retry Configuration
PROVIDER_RETRY_WAIT_TIME_S = 1.0  # Wait time between provider retries

# Temporal Visualization Constants
# Used for dulling/desaturating future events and markers
TEMPORAL_FUTURE_OPACITY = 0.7  # Opacity for future events (0.0-1.0)
TEMPORAL_FUTURE_SATURATION_FACTOR = 0.8  # Saturation multiplier for future events
TEMPORAL_FUTURE_LIGHTNESS_BOOST = 0.1  # Lightness increase for future events
