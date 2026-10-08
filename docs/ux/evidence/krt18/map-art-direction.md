# Northwatch map art

Created 2026-10-08 with the built-in image generator. Final asset:
`assets/demo/northwatch.png` (1536 × 1024). The world generator copies this image
into each portable world's `assets/maps/` directory. It is illustration content,
with no application controls or baked historical borders.

## Final generation prompt

Create a beautiful illustrated fantasy cartographic base map for an interactive
worldbuilding demo called The Northwatch March. Landscape canvas exactly 3:2
aspect ratio, top-down medieval ink and muted watercolor on warm pale parchment,
exquisite restrained penwork, hand-drawn mountains, forests, small fields,
rivers, coastline, compass rose in the upper right, thin decorative border.
Make geography strongly legible and airy so software overlays remain visible.
Critical spatial specification in normalized image coordinates (x from left,
y from top): Ashford is a small walled western capital centered at (0.28,0.72);
Northwatch Keep is a fortified northern eastern coastal fortress centered at
(0.72,0.32). A winding River Ash runs generally north-to-south around x=0.50,
crossing between the two places, with a bridge near (0.50,0.52). Coastline near
x=.85 on the east, Grey Sea fills the far-right 15%; all x=.18 to .82, y=.22 to
.82 must be land, so the east coast should be x>=.86. A winding road links
Ashford through the bridge to Northwatch. Low mountains in upper-left and
lower-east, muted wooded groves scattered, no extra named settlements.
Exact text labels only: 'THE NORTHWATCH MARCH' in elegant small upper-left
cartouche, 'Ashford' near its city, 'Northwatch Keep' near its fortress,
'River Ash' and 'Grey Sea'. Neutral timeless geography only: absolutely no
political borders, no territory fills, no flags, no troop or army figures,
no arrows, no dates, no ruler names, no extra invented text or UI. The live
app will supply historical border and army overlays. Beautiful polished map
asset, readable at desktop size; do not include a legend or explanatory
instructions.

## Integration decisions

Generated positions are approximate, so geographic overlays are schematic.
The army's bridge waypoint uses (0.49, 0.52); the kingdom's western outline
follows the river approximately, and its expanded outline approaches the coast.
The settlement markers sit near the illustrated settlements. The image remains
unchanged; changing history uses normal persisted geometry, trajectories and
event-linked entity state. No image edit or recoloring was performed afterward.
