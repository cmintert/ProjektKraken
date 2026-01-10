---
**Project:** ProjektKraken  
**Document:** GeoJSON and Shapely Migration Analysis  
**Date:** 2026-01-10  
**Status:** Technical Feasibility Study
---

# Migrating Marker Notation from Custom JSON to GeoJSON and/or Shapely

## Executive Summary

**Question:** Would it be hard and advisable to migrate marker notation from custom JSON to GeoJSON and/or Shapely?

**Answer:** Migration to **GeoJSON storage format** is **moderately difficult but advisable** for future-proofing. Adding **Shapely** as a geometry library is **low effort and highly advisable** for computational operations.

**Recommendation:**
1. **Phase 1 (2-3 weeks):** Add Shapely for geometry operations WITHOUT changing storage format
2. **Phase 2 (4-6 weeks, optional):** Migrate to GeoJSON storage if/when polygon/line features are added

**Key Insight:** You can use Shapely for geometry operations while keeping the current storage format. Full GeoJSON migration is only worthwhile if implementing polygon/line features.

---

## 1. Current State Analysis

### 1.1 Current Marker Data Model

**Python Model** (`src/core/marker.py`):
```python
@dataclass
class Marker:
    map_id: str
    object_id: str
    object_type: str
    x: float          # Normalized [0.0, 1.0]
    y: float          # Normalized [0.0, 1.0]
    id: str
    label: str
    attributes: Dict[str, Any]  # Flexible JSON
    created_at: float
    modified_at: float
```

**Database Storage** (`markers` table):
```sql
CREATE TABLE markers (
    id TEXT PRIMARY KEY,
    map_id TEXT NOT NULL,
    object_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    x REAL NOT NULL,           -- Single coordinate
    y REAL NOT NULL,           -- Single coordinate
    label TEXT,
    attributes TEXT,           -- JSON blob
    created_at REAL,
    modified_at REAL,
    FOREIGN KEY (map_id) REFERENCES maps(id) ON DELETE CASCADE
);
```

**Current Format Characteristics:**
- ✅ Simple and lightweight for point markers
- ✅ Direct column access (x, y) enables SQL queries
- ✅ Normalized coordinates [0.0, 1.0] are resolution-independent
- ❌ Not extensible to polygons/lines
- ❌ Not compatible with GIS tools
- ❌ No standard geometry operations

---

## 2. GeoJSON Migration Analysis

### 2.1 What is GeoJSON?

GeoJSON is an **open standard format (RFC 7946)** for encoding geographic data structures using JSON. It's the de facto standard for web mapping and is supported by virtually all GIS tools.

**Example - Current Marker as GeoJSON:**
```json
{
  "type": "Feature",
  "id": "marker-uuid-123",
  "geometry": {
    "type": "Point",
    "coordinates": [0.5, 0.5]
  },
  "properties": {
    "map_id": "map-uuid-456",
    "object_id": "entity-uuid-789",
    "object_type": "entity",
    "label": "Castle",
    "icon": "castle.svg",
    "color": "#FF5733",
    "created_at": 1704902400.0,
    "modified_at": 1704902400.0
  }
}
```

**Example - Polygon as GeoJSON:**
```json
{
  "type": "Feature",
  "id": "region-uuid-abc",
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9], [0.1, 0.1]]
    ]
  },
  "properties": {
    "name": "Kingdom of Atlantis",
    "fill": "#3498db",
    "stroke": "#2c3e50"
  }
}
```

### 2.2 Storage Options

#### Option A: Full GeoJSON in Database (TEXT column)

**Schema:**
```sql
CREATE TABLE map_features (
    id TEXT PRIMARY KEY,
    map_id TEXT NOT NULL,
    geojson TEXT NOT NULL,      -- Full GeoJSON Feature
    geometry_type TEXT NOT NULL, -- 'Point', 'LineString', 'Polygon'
    created_at REAL,
    modified_at REAL,
    FOREIGN KEY (map_id) REFERENCES maps(id) ON DELETE CASCADE
);

-- Index for querying by geometry type
CREATE INDEX idx_map_features_type ON map_features(map_id, geometry_type);
```

**Pros:**
- ✅ Industry standard format
- ✅ One column for all geometry types
- ✅ Easy export to GIS tools (QGIS, ArcGIS, Leaflet)
- ✅ Future-proof for any geometry type

**Cons:**
- ❌ Cannot query coordinates directly with SQL
- ❌ Requires JSON parsing for every read
- ❌ Harder to filter spatially without extensions
- ❌ Breaking change for existing data

#### Option B: Hybrid Approach (GeoJSON + Indexed Columns)

**Schema:**
```sql
CREATE TABLE map_features (
    id TEXT PRIMARY KEY,
    map_id TEXT NOT NULL,
    geojson TEXT NOT NULL,       -- Full GeoJSON
    geometry_type TEXT NOT NULL,
    -- Extracted for SQL queries (redundant but fast)
    bbox_min_x REAL,             -- Bounding box
    bbox_min_y REAL,
    bbox_max_x REAL,
    bbox_max_y REAL,
    created_at REAL,
    modified_at REAL,
    FOREIGN KEY (map_id) REFERENCES maps(id) ON DELETE CASCADE
);

CREATE INDEX idx_features_bbox ON map_features(
    bbox_min_x, bbox_min_y, bbox_max_x, bbox_max_y
);
```

**Pros:**
- ✅ Fast spatial queries using bounding box
- ✅ Full GeoJSON for compatibility
- ✅ Best of both worlds

**Cons:**
- ❌ Data redundancy
- ❌ Must maintain consistency between GeoJSON and bbox columns

#### Option C: Keep Current Format + Add GeoJSON Export

**No schema change. Add methods:**
```python
class Marker:
    def to_geojson_feature(self) -> Dict[str, Any]:
        """Export marker as GeoJSON Feature."""
        return {
            "type": "Feature",
            "id": self.id,
            "geometry": {
                "type": "Point",
                "coordinates": [self.x, self.y]
            },
            "properties": {
                "map_id": self.map_id,
                "object_id": self.object_id,
                "object_type": self.object_type,
                "label": self.label,
                **self.attributes
            }
        }
```

**Pros:**
- ✅ Zero migration effort
- ✅ Export capability for GIS tools
- ✅ No breaking changes

**Cons:**
- ❌ Not a true migration
- ❌ Still limited to points in storage

### 2.3 Migration Effort Estimate

#### Scenario 1: Add GeoJSON Export Only (Option C)

**Effort:** **1-2 days**

**Changes Required:**
1. Add `to_geojson_feature()` method to `Marker` class
2. Add `from_geojson_feature()` class method
3. Add export utility: `export_map_to_geojson(map_id: str) -> str`
4. Add tests

**Risk:** Low (no database changes)

#### Scenario 2: Full GeoJSON Storage Migration (Option A or B)

**Effort:** **4-6 weeks**

**Changes Required:**

**Week 1-2: Data Model & Schema**
- [ ] Create new `map_features` table (coexist with `markers`)
- [ ] Write migration script to convert markers → GeoJSON features
- [ ] Create new `MapFeature` data model
- [ ] Update `MapRepository` with dual-table support

**Week 3: Application Layer**
- [ ] Update all commands (CreateMarker, UpdateMarker, DeleteMarker)
- [ ] Add backwards compatibility layer
- [ ] Update UI to read from both tables during transition

**Week 4: Testing & Validation**
- [ ] Write comprehensive tests for GeoJSON parsing
- [ ] Test migration script on sample data
- [ ] Performance testing (GeoJSON parsing overhead)

**Week 5: Migration & Deployment**
- [ ] Run migration on production databases
- [ ] Verify data integrity
- [ ] Monitor performance

**Week 6: Cleanup**
- [ ] Remove old `markers` table after transition period
- [ ] Update documentation
- [ ] Remove compatibility shims

**Risk:** Medium-High (database migration, breaking changes)

**Rollback Strategy:**
- Keep old `markers` table for 3 months
- Add feature flag to toggle between old/new storage
- Maintain dual-write during transition

---

## 3. Shapely Integration Analysis

### 3.1 What is Shapely?

Shapely is a **Python library for geometric operations** built on GEOS (Geometry Engine Open Source). It provides:
- Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon
- Spatial predicates (intersects, contains, touches, within)
- Geometric operations (buffer, union, intersection, difference)
- Coordinate transformations

### 3.2 Integration Approach

**Installation:**
```bash
pip install shapely>=2.0.0
```

**Usage Example - Current Markers:**
```python
from shapely.geometry import Point, Polygon

# Convert marker to Shapely Point
marker = Marker(map_id="...", object_id="...", x=0.5, y=0.5, ...)
point = Point(marker.x, marker.y)

# Define a region as a polygon
region = Polygon([(0.1, 0.1), (0.9, 0.1), (0.5, 0.9)])

# Test if marker is in region
if region.contains(point):
    print(f"Marker {marker.label} is inside the region")

# Calculate distance between two markers
marker2 = Marker(..., x=0.7, y=0.8, ...)
point2 = Point(marker2.x, marker2.y)
distance = point.distance(point2)
print(f"Distance: {distance:.3f} normalized units")
```

**Integration Points:**

1. **Coordinate System** (`src/gui/widgets/map/coordinate_system.py`):
```python
from shapely.geometry import Point

class MapCoordinateSystem:
    def to_shapely_point(self, x: float, y: float) -> Point:
        """Convert normalized coordinates to Shapely Point."""
        return Point(x, y)
    
    def point_in_polygon(self, point: Point, polygon: Polygon) -> bool:
        """Test if a point is inside a polygon."""
        return polygon.contains(point)
```

2. **Marker Model** (`src/core/marker.py`):
```python
from shapely.geometry import Point

@dataclass
class Marker:
    # ... existing fields ...
    
    def to_shapely(self) -> Point:
        """Convert marker to Shapely Point geometry."""
        return Point(self.x, self.y)
    
    @classmethod
    def from_shapely(cls, point: Point, **kwargs) -> "Marker":
        """Create marker from Shapely Point geometry."""
        return cls(x=point.x, y=point.y, **kwargs)
```

### 3.3 Benefits of Shapely Integration

**Immediate Benefits (Even Without Storage Migration):**

1. **Spatial Queries:**
   - "Find all markers within 0.1 units of this point"
   - "Which markers are inside this region?"
   - "Find the nearest marker to this location"

2. **Geometry Operations:**
   - Buffer zones around markers
   - Convex hulls of marker clusters
   - Distance calculations
   - Line of sight checks

3. **Future-Proofing:**
   - Ready for polygon/line features
   - Unified API for all geometry types
   - Battle-tested algorithms

4. **Interoperability:**
   - Can read/write GeoJSON via Shapely
   - Can convert to WKT/WKB formats
   - Compatible with GeoPandas, Fiona, Rasterio

### 3.4 Integration Effort Estimate

**Effort:** **2-3 weeks**

**Week 1: Foundation**
- [ ] Add `shapely>=2.0.0` to requirements.txt
- [ ] Create `ShapelyConverter` utility class
- [ ] Add `to_shapely()` and `from_shapely()` methods to `Marker`
- [ ] Write unit tests for conversions

**Week 2: Integration**
- [ ] Extend `MapCoordinateSystem` with Shapely operations
- [ ] Add spatial query methods to `MapRepository`
- [ ] Update map view to use Shapely for hit testing
- [ ] Add distance/bearing calculations

**Week 3: Features & Testing**
- [ ] Add "Find Nearby" feature to UI
- [ ] Implement marker clustering algorithm
- [ ] Performance testing with 1000+ markers
- [ ] Documentation and examples

**Risk:** Low (additive, no breaking changes)

**Dependencies:** None (Shapely has no external binary dependencies on modern systems)

---

## 4. Recommended Migration Strategy

### Phase 1: Add Shapely (2-3 weeks) ⭐ **RECOMMENDED NOW**

**Goal:** Gain geometry capabilities without breaking changes

**Implementation:**
1. Add Shapely to dependencies
2. Create geometry utility layer
3. Add optional methods to existing classes
4. Add spatial query features to UI

**Benefits:**
- ✅ Immediate value (spatial queries, distance calculations)
- ✅ No database migration required
- ✅ No breaking changes
- ✅ Lays foundation for future geometry features

**Example Use Cases:**
- "Show me all events within 100km of this city"
- "Find the 5 nearest entities to this location"
- "Calculate travel distance along a path"

### Phase 2: Add GeoJSON Export (1 week) ⭐ **RECOMMENDED NOW**

**Goal:** Enable interoperability with GIS tools

**Implementation:**
1. Add `to_geojson_feature()` to Marker
2. Add map export command: `python -m src.cli.map export --map-id <id> --output map.geojson`
3. Add "Export to GeoJSON" button in UI

**Benefits:**
- ✅ Users can open maps in QGIS, ArcGIS, Google Earth
- ✅ Enable data exchange with other tools
- ✅ No storage changes required

### Phase 3: GeoJSON Storage (4-6 weeks) ⚠️ **ONLY IF NEEDED**

**Goal:** Full GeoJSON storage for polygon/line features

**Trigger:** User requests polygon/line features

**Implementation:**
1. Create `map_features` table with GeoJSON column
2. Implement migration script with rollback
3. Add dual-table support during transition
4. Gradually deprecate old `markers` table

**Benefits:**
- ✅ Unified storage for all geometry types
- ✅ Industry standard format
- ✅ Ready for advanced GIS features

**When to Do This:**
- ONLY if implementing polygon/line features
- Current point-based system doesn't need this

---

## 5. Cost-Benefit Analysis

### Option: Do Nothing

**Effort:** 0 weeks  
**Cost:** $0  
**Benefits:** None  
**Risks:** Limited to point markers forever

**Verdict:** ❌ Not recommended (missed opportunities)

### Option: Shapely Only (Phase 1)

**Effort:** 2-3 weeks  
**Cost:** ~$5,000 (1 developer @ $2k/week)  
**Benefits:**
- Spatial queries and operations
- Foundation for future geometry
- Better user features (find nearby, distance)

**ROI:** High (immediate features with low effort)

**Verdict:** ✅ **HIGHLY RECOMMENDED**

### Option: Shapely + GeoJSON Export (Phase 1 + 2)

**Effort:** 3-4 weeks  
**Cost:** ~$7,000  
**Benefits:**
- All Shapely benefits
- GIS tool interoperability
- Data portability

**ROI:** High (enables professional workflows)

**Verdict:** ✅ **HIGHLY RECOMMENDED**

### Option: Full GeoJSON Storage Migration (All Phases)

**Effort:** 7-10 weeks  
**Cost:** ~$16,000  
**Benefits:**
- All above benefits
- True polygon/line support
- Future-proof architecture

**ROI:** Medium (only valuable if polygon/line features are needed)

**Verdict:** ⚠️ **WAIT UNTIL POLYGON/LINE FEATURES ARE CONFIRMED**

---

## 6. Technical Risks & Mitigations

### Risk 1: Shapely Installation Issues

**Risk:** Shapely requires GEOS binary, may fail on some systems

**Mitigation:**
- Shapely 2.0+ bundles wheels with GEOS for Windows/Mac/Linux
- Fallback to pure-Python operations if Shapely unavailable
- Document installation troubleshooting

**Likelihood:** Low (Shapely 2.0+ is well-packaged)

### Risk 2: Performance with Large Datasets

**Risk:** JSON parsing overhead for GeoJSON storage

**Mitigation:**
- Use hybrid storage with bbox indexes
- Implement spatial indexing (R-tree)
- Lazy load geometries only when needed

**Likelihood:** Medium (1000+ features may be slow)

### Risk 3: Migration Data Loss

**Risk:** Bugs in migration script corrupt data

**Mitigation:**
- Test migration on copies first
- Keep old table for 3 months
- Implement validation checks
- Version control for database schema

**Likelihood:** Low (with proper testing)

### Risk 4: Breaking Changes for Users

**Risk:** Existing databases incompatible with new format

**Mitigation:**
- Auto-migration on first launch
- Backwards compatibility layer
- Clear upgrade path in documentation
- Feature flag to toggle formats

**Likelihood:** Medium (migration always has risks)

---

## 7. Performance Benchmarks (Estimated)

### Current System (Point Markers)

| Operation | Current | With Shapely | With GeoJSON Storage |
|-----------|---------|--------------|----------------------|
| Load 100 markers | 5ms | 8ms (+60%) | 15ms (+200%) |
| Load 1000 markers | 40ms | 60ms (+50%) | 120ms (+200%) |
| Distance calc | N/A | 0.1ms | 0.1ms |
| Spatial query (find nearby) | N/A | 2ms | 5ms |
| Export to GeoJSON | N/A | 10ms | 5ms (already JSON) |

**Conclusion:** Shapely adds minimal overhead. GeoJSON storage has ~2x parsing cost but is acceptable for <1000 features.

---

## 8. Implementation Checklist

### Phase 1: Shapely Integration (2-3 weeks)

**Week 1: Foundation**
- [ ] Add `shapely>=2.0.0` to requirements.txt
- [ ] Create `src/core/geometry_utils.py` with conversion functions
- [ ] Add `to_shapely()` method to `Marker` class
- [ ] Write unit tests for Shapely conversions
- [ ] Document Shapely usage patterns

**Week 2: Coordinate System**
- [ ] Extend `MapCoordinateSystem` with Shapely methods:
  - [ ] `point_in_polygon(point, polygon) -> bool`
  - [ ] `distance_between(p1, p2) -> float`
  - [ ] `buffer_point(point, radius) -> Polygon`
- [ ] Add spatial query methods to `MapRepository`:
  - [ ] `find_markers_near(x, y, radius) -> List[Marker]`
  - [ ] `find_markers_in_polygon(vertices) -> List[Marker]`
- [ ] Write integration tests

**Week 3: UI Features**
- [ ] Add "Find Nearby" context menu item
- [ ] Add distance measurement tool
- [ ] Display distances in status bar
- [ ] Add marker clustering for zoomed-out views
- [ ] User documentation

### Phase 2: GeoJSON Export (1 week)

**Tasks:**
- [ ] Add `to_geojson_feature()` to `Marker` class
- [ ] Add `from_geojson_feature()` class method
- [ ] Create `export_map_to_geojson(map_id, output_path)` utility
- [ ] Add CLI command: `python -m src.cli.map export`
- [ ] Add "Export to GeoJSON" button in map widget toolbar
- [ ] Write tests for GeoJSON import/export
- [ ] Add QGIS import tutorial to documentation

### Phase 3: GeoJSON Storage (4-6 weeks, OPTIONAL)

**Only proceed if polygon/line features are confirmed!**

**Week 1-2: Schema & Migration**
- [ ] Design `map_features` table schema
- [ ] Write migration script with validation
- [ ] Test migration on sample databases
- [ ] Implement rollback mechanism

**Week 3: Application Layer**
- [ ] Create `MapFeature` data model
- [ ] Update `MapRepository` for dual-table support
- [ ] Add feature flag: `USE_GEOJSON_STORAGE`
- [ ] Update all commands to support both formats

**Week 4-5: Testing**
- [ ] Unit tests for GeoJSON parsing
- [ ] Integration tests for repository
- [ ] Performance benchmarks
- [ ] User acceptance testing

**Week 6: Deployment**
- [ ] Run migration in production
- [ ] Monitor errors and performance
- [ ] Deprecation plan for old format

---

## 9. Alternatives Considered

### Alternative 1: PostGIS

**What:** PostgreSQL with spatial extensions

**Pros:**
- Industrial-strength spatial database
- Advanced spatial indexes (R-tree, GiST)
- Native spatial queries

**Cons:**
- ❌ Requires PostgreSQL server (not SQLite)
- ❌ Complex deployment
- ❌ Overkill for worldbuilding tool

**Verdict:** ❌ Not suitable (SQLite is a project requirement)

### Alternative 2: SpatiaLite

**What:** SQLite with spatial extension

**Pros:**
- SQLite-based (single file)
- Native spatial queries
- R-tree indexes

**Cons:**
- ❌ Requires binary extension (deployment complexity)
- ❌ Not available on all platforms
- ❌ More complex than pure Python

**Verdict:** ⚠️ Consider for future if spatial queries become critical

### Alternative 3: Pure Python Geometry

**What:** Implement geometry operations manually

**Pros:**
- No dependencies
- Full control

**Cons:**
- ❌ Reinventing the wheel
- ❌ Bug-prone
- ❌ Slower than GEOS

**Verdict:** ❌ Not recommended (Shapely is mature and fast)

---

## 10. Recommendations Summary

### Immediate Actions (Now)

1. **✅ ADD SHAPELY** (2-3 weeks, ~$5k)
   - Low risk, high value
   - Enables spatial features immediately
   - No breaking changes

2. **✅ ADD GEOJSON EXPORT** (1 week, ~$2k)
   - Enables GIS tool interoperability
   - Adds professional credibility
   - No breaking changes

### Future Actions (When Polygon/Line Features are Requested)

3. **⚠️ MIGRATE TO GEOJSON STORAGE** (4-6 weeks, ~$10k)
   - Only if polygon/line features are confirmed
   - Requires careful planning and testing
   - Breaking change (needs migration)

### DO NOT DO

- ❌ Full storage migration without polygon/line use cases
- ❌ PostGIS (too complex)
- ❌ Custom geometry library (don't reinvent the wheel)

---

## 11. Next Steps

### To Proceed with Shapely Integration (Recommended)

1. **Get approval** from team/stakeholders
2. **Create feature branch:** `feature/shapely-integration`
3. **Week 1:** Install Shapely, add conversion methods, write tests
4. **Week 2:** Extend coordinate system, add spatial queries
5. **Week 3:** Add UI features, documentation, deploy
6. **Review:** Gather user feedback on spatial features

### To Proceed with GeoJSON Export (Recommended)

1. **Get approval** from team/stakeholders
2. **Create feature branch:** `feature/geojson-export`
3. **Days 1-2:** Implement `to_geojson_feature()` methods
4. **Days 3-4:** Add CLI export command and tests
5. **Day 5:** Add UI export button and documentation
6. **Deploy:** Release as new feature

### To Proceed with GeoJSON Storage (Only if Needed)

1. **STOP!** First confirm polygon/line features are actually needed
2. **Review** polygon/line requirements with users
3. **Prototype** basic polygon rendering (1 week spike)
4. **If approved:** Follow 6-week migration plan above

---

## 12. Conclusion

**Is migration to GeoJSON/Shapely hard?**
- **Shapely integration:** No, relatively easy (2-3 weeks)
- **GeoJSON export:** No, very easy (1 week)
- **GeoJSON storage:** Moderate difficulty (4-6 weeks)

**Is migration advisable?**
- **Shapely:** ✅ YES - High value, low risk, do it now
- **GeoJSON export:** ✅ YES - Professional feature, easy to add
- **GeoJSON storage:** ⚠️ ONLY IF POLYGON/LINE FEATURES ARE CONFIRMED

**Total Recommended Investment:**
- **Phase 1 + 2:** 3-4 weeks (~$7,000) for Shapely + GeoJSON export
- **Phase 3:** Wait and see (only if polygon/line features are needed)

**Key Insight:** You don't need to migrate storage to gain Shapely's benefits. Add Shapely as a computational layer while keeping the current storage format. This gives you 80% of the benefits with 20% of the effort.

---

**Document Status:** Ready for Review  
**Author:** GitHub Copilot  
**Reviewers:** @cmintert
**Recommended Priority:** High (Phase 1), Medium (Phase 2), Low (Phase 3)
