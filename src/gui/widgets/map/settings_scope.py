"""Detached, read-only descriptions of map setting ownership."""

from dataclasses import dataclass

from src.core.map import VECTOR_LAYER_TYPES, MapLayerNode
from src.core.map_constants import MAP_LAYER_TYPE_GROUP


@dataclass(frozen=True)
class SettingsScope:
    """Creator-facing identity and the scope of one settings target."""

    kind: str
    heading: str
    description: str
    location: str
    opacity: str
    visibility: str
    zoom: str

    @property
    def properties_label(self) -> str:
        """Return the action label for this target type."""
        owner = "Feature" if self.kind in {"Marker", "Path", "Region"} else self.kind
        return f"{owner} properties…"


def _path(root: MapLayerNode, node_id: str) -> list[MapLayerNode]:
    if root.id == node_id:
        return [root]
    for child in root.children:
        found = _path(child, node_id)
        if found:
            return [root, *found]
    return []


def _contents(node: MapLayerNode) -> tuple[int, int]:
    features = layers = 0
    for child in node.children:
        if child.virtual:
            continue
        features += child.layer_type in VECTOR_LAYER_TYPES
        layers += child.layer_type in {"raster", "basemap"}
        nested_features, nested_layers = _contents(child)
        features += nested_features
        layers += nested_layers
    return features, layers


def zoom_caption(node: MapLayerNode) -> str:
    """Describe stored zoom bounds without converting legacy zoom units."""
    maximum = "unlimited" if node.max_zoom == float("inf") else f"{node.max_zoom:g}"
    basis = (
        "relative to Fit to Map"
        if node.attributes.get("zoom_basis") == "fit_ratio"
        else "absolute view scale (legacy)"
    )
    return f"{node.min_zoom:g}–{maximum}, {basis}"


def settings_scope(
    node: MapLayerNode, root: MapLayerNode | None = None
) -> SettingsScope:
    """Describe a tree snapshot without retaining nodes or changing authored state."""
    kind = {
        "marker": "Marker",
        "path": "Path",
        "region": "Region",
        "group": "Group",
        "raster": "Raster layer",
        "basemap": "Base map",
    }.get(node.layer_type, "Map item")
    ancestors = _path(root, node.id)[1:-1] if root is not None else []
    groups = [
        parent for parent in ancestors if parent.layer_type == MAP_LAYER_TYPE_GROUP
    ]
    location = (
        "In: " + " / ".join(parent.name for parent in groups)
        if groups
        else "At map level"
    )
    description = "Changes this map feature only."
    if node.layer_type == MAP_LAYER_TYPE_GROUP:
        features, layers = _contents(node)
        feature_word = "feature" if features == 1 else "features"
        layer_word = "map layer" if layers == 1 else "map layers"
        description = (
            f"Contains {features} {feature_word} and {layers} {layer_word}. "
            "Applies to all contents, including items added later."
        )
    elif node.layer_type not in VECTOR_LAYER_TYPES:
        description = "Changes this map surface only."
    opacity = "; ".join(f"{parent.name}: {parent.opacity:.0%}" for parent in groups)
    visibility = "; ".join(
        f"{parent.name}: {'shown' if parent.visible else 'hidden'}" for parent in groups
    )
    zoom = "; ".join(f"{parent.name}: {zoom_caption(parent)}" for parent in groups)
    return SettingsScope(
        kind, f"{kind}: {node.name}", description, location, opacity, visibility, zoom
    )
