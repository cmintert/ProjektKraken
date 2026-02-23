"""Map Widget Package.

Provides map visualization components organized into separate modules.

Sub-components of MapGraphicsView:
    - DrawingTool: Path/region drawing mode
    - VertexEditor: Vertex editing with handles and snapping
    - MarkerManager: CRUD for markers and features
    - TrajectoryRenderer: Trajectory path and keyframes
    - InteractionHandler: Context menus, drag-drop, dialogs
"""

from src.gui.dialogs.icon_picker_dialog import IconPickerDialog
from src.gui.widgets.map.drawing_tool import DrawingTool
from src.gui.widgets.map.interaction_handler import InteractionHandler
from src.gui.widgets.map.label_manager import LabelManager
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.map.marker_item import MarkerItem
from src.gui.widgets.map.marker_manager import MarkerManager
from src.gui.widgets.map.trajectory_renderer import TrajectoryRenderer
from src.gui.widgets.map.vertex_editor import VertexEditor

__all__ = [
    "DrawingTool",
    "IconPickerDialog",
    "InteractionHandler",
    "LabelManager",
    "MapGraphicsView",
    "MarkerItem",
    "MarkerManager",
    "TrajectoryRenderer",
    "VertexEditor",
]
