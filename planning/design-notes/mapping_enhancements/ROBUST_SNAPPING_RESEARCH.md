# Research: Robust Snapping Mechanism

## 1. Spatial Indexing
We do **not** need an external R-tree library.
`QGraphicsScene` has a built-in **Binary Space Partitioning (BSP) Index**.

- **Query**: `scene.items(QRectF(x-r, y-r, 2r, 2r))` efficiently finds all candidate items near the mouse cursor.
- **Performance**: O(log n) typically.
- **Recommendation**: Use `QGraphicsScene.items()` for candidate lookup.

## 2. Geometry Math (Point-to-Segment)
To snap to edges (roads/rivers), we need to calculate the distance from the mouse cursor $P$ to a line segment $AB$.

**Algorithm**:
1.  Project vector $AP$ onto $AB$.
2.  Calculate parameter $t = \frac{(P-A) \cdot (B-A)}{|B-A|^2}$.
3.  Clamp $t$ to $[0, 1]$.
4.  Closest point $C = A + t(B-A)$.
5.  If $|P-C| < \text{snap\_radius}$, then $C$ is a valid snap target.

## 3. Proposed Architecture: `SnappingManager`

A dedicated class to handle the complexity, distinct from `MapGraphicsView`.

### Class Responsibility
```python
class SnappingManager:
    def __init__(self, scene: QGraphicsScene, radius_px: int = 10):
        self.scene = scene
        self.radius_px = radius_px

    def snap_point(self, 
                   query_pos: QPointF, 
                   view_transform: QTransform, 
                   exclude_items: List[QGraphicsItem] = None) -> SnapResult:
        """
        1. Calculate scene_radius = radius_px / view_scale
        2. Candidates = scene.items(QRectF(query_pos +/- scene_radius))
        3. Iterate candidates:
             - Check vertex distance (Priority 1)
             - Check edge distance (Priority 2)
        4. Return closest SnapResult(pos, type, item)
        """
```

## 4. Visual Feedback
The `MapGraphicsView` should render a **Snap Indicator** (e.g., a yellow circle for vertices, a blue cross for edges) when `SnapResult` is valid.

## 5. Integration Plan
1.  Create `src/core/geometry_utils.py` (Math functions).
2.  Create `src/gui/utils/snapping_manager.py`.
3.  Update `MapGraphicsView` to delegate snapping logic to the manager during `mouseMoveEvent`.
