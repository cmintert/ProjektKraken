"""Application Constants.

Stores default values for UI configuration and magic numbers.
"""

# Window Configuration
VERSION = "0.11.0"
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

# Editor Layout Constants
EDITOR_FORM_VERTICAL_SPACING = 12
EDITOR_SECTION_SPACING = 4
EDITOR_LIST_SPACING = 2
EDITOR_DETAILS_MIN_HEIGHT = 400
EDITOR_RELATION_LIST_MIN_HEIGHT = 80
EDITOR_ICON_BUTTON_SIZE = 32

# Relation Type Picker Constants
RELATION_PICKER_MIN_WIDTH = 250
RELATION_PICKER_MAX_WIDTH = 400
RELATION_PICKER_MIN_HEIGHT = 80
RELATION_PICKER_MAX_HEIGHT = 120

# Unified List Constants
UNIFIED_LIST_MIN_WIDTH = 250
UNIFIED_LIST_MIN_HEIGHT = 200
UNIFIED_LIST_PREFERRED_WIDTH = 350
UNIFIED_LIST_PREFERRED_HEIGHT = 500
UNIFIED_LIST_MESSAGE_TIMEOUT_MS = 3000
UNIFIED_LIST_DELETE_CONFIRM_TIMEOUT_MS = 1000

# Navigation Constants
NAVIGATION_SELECTION_DELAY_MS = (
    250  # Delay to allow drag operations to cancel selection
)

# ---------------------------------------------------------------------------
# Map Feature Constants
# ---------------------------------------------------------------------------

# Default visual style for map features (paths / regions)
MAP_FEATURE_DEFAULT_STROKE_COLOR = "#3498DB"
MAP_FEATURE_DEFAULT_STROKE_WIDTH = 2.0
MAP_FEATURE_DEFAULT_FILL_COLOR = "#3498DB40"  # 25% alpha
MAP_FEATURE_DEFAULT_DASH_PATTERN: list[float] = []  # solid line
MAP_FEATURE_REGION_STROKE_COLOR = "#2C3E50"
MAP_FEATURE_REGION_FILL_COLOR = "#3498DB30"

# Selection highlight
MAP_FEATURE_SELECTION_PEN_COLOR = "#FFFFFF"
MAP_FEATURE_SELECTION_PEN_WIDTH = 2.0

# Hit testing (click / hover detection margins)
MAP_FEATURE_HIT_AREA_MARGIN = 6  # extra pixels around stroke
MAP_FEATURE_MIN_HIT_AREA_WIDTH = 10  # minimum clickable pixel width

# Label styling
MAP_FEATURE_LABEL_FONT_FAMILY = "Segoe UI"
MAP_FEATURE_LABEL_FONT_SIZE = 9
MAP_FEATURE_LABEL_COLOR = "#333333"

# Feature item z-layer (between map background and point markers)
MAP_FEATURE_Z_VALUE = 8

# Hover tooltip debounce delay
MAP_FEATURE_HOVER_DEBOUNCE_MS = 100

# Click-vs-drag threshold (manhattan length in pixels)
MAP_FEATURE_CLICK_THRESHOLD_PX = 5

# Vertex editing handles
MAP_VERTEX_HANDLE_RADIUS = 5  # screen pixels (cosmetic)
MAP_VERTEX_HANDLE_COLOR = "#e74c3c"  # red
MAP_VERTEX_HANDLE_BORDER_COLOR = "#FFFFFF"
MAP_MIDPOINT_HANDLE_RADIUS = 4  # slightly smaller
MAP_MIDPOINT_HANDLE_COLOR = "#2ecc71"  # green
MAP_MIDPOINT_HANDLE_BORDER_COLOR = "#FFFFFF"
MAP_MIDPOINT_GHOST_OPACITY = 0.4
MAP_MIDPOINT_HOVER_OPACITY = 0.9

# Vertex editing style applied to the feature being edited
MAP_EDIT_DASH_PATTERN = [6, 3]  # dashed line during editing
MAP_EDIT_STROKE_COLOR = "#e67e22"  # orange highlight

# Snap radius for vertex snapping during editing (screen pixels)
MAP_SNAP_RADIUS_PX = 10.0

# Default map scale
MAP_DEFAULT_WIDTH_METERS = 1_000_000.0  # 1 000 km

# Zoom factor for mouse wheel
MAP_ZOOM_IN_FACTOR = 1.25
