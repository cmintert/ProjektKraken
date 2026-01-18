"""Routing Service Module.

Provides route finding and path calculation for road networks.
Uses NetworkX for graph operations and A*/Dijkstra algorithms.
"""

import logging
from typing import Dict, List, Optional, Tuple

import networkx as nx

from src.core.road import RoadNetwork, RoadNode, RoadSegment
from src.services.spatial_service import SpatialService

logger = logging.getLogger(__name__)


class Route:
    """Represents a calculated route through a road network.

    Attributes:
        segment_ids: List of segment IDs in order.
        node_ids: List of node IDs in order.
        total_distance_px: Total distance in pixels.
        total_distance_m: Total distance in meters (if px_per_meter available).
        estimated_time_s: Estimated travel time in seconds.
        coords: Full coordinate path [[x, y], ...].
    """

    def __init__(
        self,
        segment_ids: List[str],
        node_ids: List[str],
        total_distance_px: float,
        coords: List[List[float]],
        px_per_meter: float = 1.0,
        avg_speed_m_per_s: float = 15.0,
    ):
        """Initializes a Route.

        Args:
            segment_ids: Segment IDs forming the route.
            node_ids: Node IDs forming the route.
            total_distance_px: Total distance in pixels.
            coords: Complete coordinate path.
            px_per_meter: Conversion factor from pixels to meters.
            avg_speed_m_per_s: Average travel speed in m/s (default: 15 m/s ≈ 54 km/h).
        """
        self.segment_ids = segment_ids
        self.node_ids = node_ids
        self.total_distance_px = total_distance_px
        self.coords = coords
        self.px_per_meter = px_per_meter

        # Calculate real-world distance and time
        self.total_distance_m = total_distance_px / px_per_meter
        self.estimated_time_s = self.total_distance_m / avg_speed_m_per_s

    def to_dict(self) -> Dict:
        """Converts route to dictionary representation.

        Returns:
            Dict: Route data.
        """
        return {
            "segment_ids": self.segment_ids,
            "node_ids": self.node_ids,
            "total_distance_px": self.total_distance_px,
            "total_distance_m": self.total_distance_m,
            "estimated_time_s": self.estimated_time_s,
            "coords": self.coords,
        }

    def to_geojson(self) -> Dict:
        """Converts route to GeoJSON LineString feature.

        Note: Coordinates are in pixel space, not geographic.
        For geographic export, apply inverse transform externally.

        Returns:
            Dict: GeoJSON feature.
        """
        return {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": self.coords},
            "properties": {
                "distance_px": self.total_distance_px,
                "distance_m": self.total_distance_m,
                "time_s": self.estimated_time_s,
                "segment_ids": self.segment_ids,
                "node_ids": self.node_ids,
            },
        }


class RoutingService:
    """Service for calculating routes through road networks.

    Uses NetworkX to build graphs and find optimal paths.
    Supports caching for performance.
    """

    def __init__(self, spatial_service: Optional[SpatialService] = None):
        """Initializes the RoutingService.

        Args:
            spatial_service: SpatialService instance (creates new if None).
        """
        self.spatial_service = spatial_service or SpatialService()
        self._graph_cache: Dict[str, nx.Graph] = {}  # map_id -> graph

    def load_network(
        self, map_id: str, road_network: RoadNetwork, force_rebuild: bool = False
    ) -> nx.Graph:
        """Loads a road network into a NetworkX graph.

        Args:
            map_id: Map identifier for caching.
            road_network: RoadNetwork to load.
            force_rebuild: Force rebuild even if cached.

        Returns:
            nx.Graph: NetworkX graph representation.
        """
        if not force_rebuild and map_id in self._graph_cache:
            logger.debug(f"Using cached graph for map {map_id}")
            return self._graph_cache[map_id]

        logger.info(
            f"Building graph for map {map_id}: "
            f"{len(road_network.nodes)} nodes, {len(road_network.segments)} segments"
        )

        graph = nx.Graph()

        # Add nodes with positions
        for node_id, node in road_network.nodes.items():
            graph.add_node(node_id, x=node.x, y=node.y, data=node)

        # Add edges (segments)
        for segment in road_network.segments:
            # Calculate weight (prefer shorter segments by default)
            weight = segment.length_px if segment.length_px > 0 else 1.0

            # Check for oneway attribute
            is_oneway = segment.attributes.get("oneway", False)

            if is_oneway:
                # Directed edge only
                graph.add_edge(
                    segment.start_node_id,
                    segment.end_node_id,
                    weight=weight,
                    segment=segment,
                )
            else:
                # Bidirectional edge
                graph.add_edge(
                    segment.start_node_id,
                    segment.end_node_id,
                    weight=weight,
                    segment=segment,
                )

        # Cache the graph
        self._graph_cache[map_id] = graph

        logger.debug(
            f"Graph built: {graph.number_of_nodes()} nodes, "
            f"{graph.number_of_edges()} edges"
        )

        return graph

    def invalidate_cache(self, map_id: Optional[str] = None) -> None:
        """Invalidates cached graphs.

        Args:
            map_id: Specific map to invalidate, or None for all.
        """
        if map_id:
            if map_id in self._graph_cache:
                del self._graph_cache[map_id]
                logger.debug(f"Invalidated graph cache for map {map_id}")
        else:
            self._graph_cache.clear()
            logger.debug("Invalidated all graph caches")

    def find_nearest_node(
        self, x: float, y: float, road_network: RoadNetwork, threshold: float = 50.0
    ) -> Optional[str]:
        """Finds the nearest node to a point.

        Args:
            x: Query point x.
            y: Query point y.
            road_network: Road network to search.
            threshold: Maximum distance threshold.

        Returns:
            Optional[str]: Node ID if found, else None.
        """
        nodes = [(node.x, node.y) for node in road_network.nodes.values()]
        node_ids = list(road_network.nodes.keys())

        idx = self.spatial_service.snap_to_nearest_node(x, y, nodes, threshold)

        if idx is not None:
            return node_ids[idx]
        return None

    def snap_point_to_segment(
        self, x: float, y: float, road_network: RoadNetwork, threshold: float = 50.0
    ) -> Optional[Tuple[str, float, float]]:
        """Snaps a point to the nearest road segment.

        Args:
            x: Query point x.
            y: Query point y.
            road_network: Road network to search.
            threshold: Maximum snap distance.

        Returns:
            Optional[Tuple[str, float, float]]: (segment_id, snap_x, snap_y) or None.
        """
        best_segment_id = None
        best_distance = threshold
        best_snap_x = 0.0
        best_snap_y = 0.0

        for segment in road_network.segments:
            if len(segment.coords) < 2:
                continue

            # Check each segment of the polyline
            for i in range(len(segment.coords) - 1):
                x1, y1 = segment.coords[i]
                x2, y2 = segment.coords[i + 1]

                dist, snap_x, snap_y = self.spatial_service.point_to_segment_distance(
                    x, y, x1, y1, x2, y2
                )

                if dist < best_distance:
                    best_distance = dist
                    best_segment_id = segment.id
                    best_snap_x = snap_x
                    best_snap_y = snap_y

        if best_segment_id:
            return (best_segment_id, best_snap_x, best_snap_y)
        return None

    def route_between_nodes(
        self,
        map_id: str,
        road_network: RoadNetwork,
        start_node_id: str,
        end_node_id: str,
        algorithm: str = "dijkstra",
    ) -> Optional[Route]:
        """Calculates route between two nodes.

        Args:
            map_id: Map identifier.
            road_network: Road network.
            start_node_id: Starting node ID.
            end_node_id: Ending node ID.
            algorithm: Routing algorithm ("dijkstra" or "astar").

        Returns:
            Optional[Route]: Route if path exists, else None.
        """
        graph = self.load_network(map_id, road_network)

        if start_node_id not in graph or end_node_id not in graph:
            logger.warning(f"Start or end node not in graph: {start_node_id}, {end_node_id}")
            return None

        try:
            if algorithm == "astar":
                # A* with Euclidean heuristic
                def heuristic(n1: str, n2: str) -> float:
                    node1 = road_network.get_node(n1)
                    node2 = road_network.get_node(n2)
                    if node1 and node2:
                        return self.spatial_service.distance(
                            node1.x, node1.y, node2.x, node2.y
                        )
                    return 0.0

                path = nx.astar_path(
                    graph, start_node_id, end_node_id, heuristic=heuristic, weight="weight"
                )
            else:
                # Dijkstra
                path = nx.shortest_path(
                    graph, start_node_id, end_node_id, weight="weight"
                )

            # Build route from path
            return self._build_route_from_path(path, graph, road_network)

        except nx.NetworkXNoPath:
            logger.warning(f"No path found between {start_node_id} and {end_node_id}")
            return None
        except Exception as e:
            logger.error(f"Error finding route: {e}")
            return None

    def route_between_points(
        self,
        map_id: str,
        road_network: RoadNetwork,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        snap_threshold: float = 50.0,
        algorithm: str = "dijkstra",
    ) -> Optional[Route]:
        """Calculates route between two arbitrary points.

        Snaps points to nearest nodes before routing.

        Args:
            map_id: Map identifier.
            road_network: Road network.
            start_x: Start point x.
            start_y: Start point y.
            end_x: End point x.
            end_y: End point y.
            snap_threshold: Maximum snap distance.
            algorithm: Routing algorithm.

        Returns:
            Optional[Route]: Route if path exists, else None.
        """
        # Snap to nearest nodes
        start_node_id = self.find_nearest_node(
            start_x, start_y, road_network, snap_threshold
        )
        end_node_id = self.find_nearest_node(end_x, end_y, road_network, snap_threshold)

        if not start_node_id or not end_node_id:
            logger.warning("Could not snap start or end point to network")
            return None

        return self.route_between_nodes(
            map_id, road_network, start_node_id, end_node_id, algorithm
        )

    def _build_route_from_path(
        self, path: List[str], graph: nx.Graph, road_network: RoadNetwork
    ) -> Route:
        """Builds a Route object from a node path.

        Args:
            path: List of node IDs.
            graph: NetworkX graph.
            road_network: Road network.

        Returns:
            Route: Complete route object.
        """
        segment_ids = []
        coords = []
        total_distance = 0.0

        # Get first node coordinates
        first_node = road_network.get_node(path[0])
        if first_node:
            coords.append([first_node.x, first_node.y])

        # Traverse path
        for i in range(len(path) - 1):
            node1_id = path[i]
            node2_id = path[i + 1]

            # Get edge data
            edge_data = graph.get_edge_data(node1_id, node2_id)
            if edge_data and "segment" in edge_data:
                segment = edge_data["segment"]
                segment_ids.append(segment.id)

                # Add segment coordinates (skip first to avoid duplication)
                if len(segment.coords) >= 2:
                    coords.extend(segment.coords[1:])

                total_distance += edge_data["weight"]

        # Get metadata
        px_per_meter = road_network.meta.get("px_per_meter", 1.0)

        return Route(
            segment_ids=segment_ids,
            node_ids=path,
            total_distance_px=total_distance,
            coords=coords,
            px_per_meter=px_per_meter,
        )
