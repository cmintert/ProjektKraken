# Strategy: Road Networks & River Tributaries

## 1. River Tributaries (Distinct Entities)
**Recommendation**: Use the **Entity-Relation** model.
Since tributaries (e.g., "River Gladden") are logically distinct from the main river ("River Anduin"), they should be separate Entities.

**How to handle:**
1. Create "River Anduin" (Path).
2. Create "River Gladden" (Path).
3. Create a **Relation**: `Gladden` -> `flows_into` -> `Anduin`.

**Future Feature**:
- **"Highlight Relations" mode**: When you click Anduin, we can highlight all upstream tributaries on the map.

## 2. Road Networks (Same Entity, Branching Paths)
**Current Limitation**:
- The Database enforces a **1:1 limit**: One Entity can have only *one* Marker/Path on a map.
- `PathItem` currently only supports a single continuous line.

**Recommendation**: Implement **Multi-path Geometry**.
Instead of forcing you to split "The King's Road" into "Segment A" and "Segment B", we should update `PathItem` to support **MultiLineStrings**.

### Proposed Change
Update `PathItem` and `RegionItem` to accept a list-of-lists geometry:
```python
# Current
geometry = [{x:0, y:0}, {x:1, y:1}]

# Proposed (Multi-Path)
geometry = [
  [{x:0, y:0}, {x:1, y:1}], # Main road
  [{x:0.5, y:0.5}, {x:0.8, y:0.2}] # Fork/Branch
]
```

**Workflow:**
1. Draw the main road.
2. Select the road.
3. Click a new tool **"Add Segment"**.
4. Draw the branch.
5. Both segments are stored under the single "King's Road" entity.
