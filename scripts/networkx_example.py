#!/usr/bin/env python3
"""
NetworkX Graph Analysis Example for ProjektKraken Relations.

This script demonstrates how to:
1. Create a world with weighted relations
2. Export relations to a NetworkX graph
3. Perform graph analysis (centrality, shortest paths, etc.)
4. Use relation attributes (weight, confidence) in analysis

Usage:
    python scripts/networkx_example.py [--database path/to/world.kraken]

If no database is provided, creates an in-memory example.
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.entities import Entity
from src.core.events import Event
from src.services.db_service import DatabaseService


def create_example_world(db_service: DatabaseService) -> None:
    """
    Create an example world with characters and weighted relations.

    Creates a simple social network of characters with various
    relationship strengths (alliances, rivalries, etc.).
    """
    print("Creating example world...")

    # Create characters
    characters = [
        Entity(name="Queen Elara", type="character"),
        Entity(name="Lord Theron", type="character"),
        Entity(name="General Marcus", type="character"),
        Entity(name="Merchant Lyra", type="character"),
        Entity(name="Scholar Darian", type="character"),
    ]

    for char in characters:
        db_service.insert_entity(char)

    # Create weighted relations
    relations = [
        # Alliances (high weight = strong bond)
        (characters[0].id, characters[1].id, "allied_with", {
            "weight": 0.9,
            "confidence": 1.0,
            "notes": "Long-standing political alliance"
        }),
        (characters[0].id, characters[2].id, "commands", {
            "weight": 0.85,
            "confidence": 1.0,
            "notes": "Military chain of command"
        }),
        (characters[1].id, characters[3].id, "trades_with", {
            "weight": 0.7,
            "confidence": 0.9,
            "notes": "Regular trading partner"
        }),

        # Weaker connections
        (characters[3].id, characters[4].id, "associates_with", {
            "weight": 0.5,
            "confidence": 0.8,
            "notes": "Occasional collaboration"
        }),
        (characters[2].id, characters[4].id, "consults", {
            "weight": 0.6,
            "confidence": 0.85,
            "notes": "Strategic advisor relationship"
        }),

        # Rivalries (low weight)
        (characters[1].id, characters[2].id, "rivals", {
            "weight": 0.3,
            "confidence": 1.0,
            "notes": "Political tension"
        }),
    ]

    for source_id, target_id, rel_type, attrs in relations:
        db_service.insert_relation(source_id, target_id, rel_type, attrs)

    print(f"✓ Created {len(characters)} characters and {len(relations)} relations")


def export_to_networkx(db_service: DatabaseService):
    """
    Export ProjektKraken relations to a NetworkX graph.

    Demonstrates how to use relation attributes for graph analysis.
    Requires: pip install networkx matplotlib (optional)
    """
    try:
        import networkx as nx
    except ImportError:
        print("ERROR: NetworkX not installed. Install with: pip install networkx")
        return None

    print("\nExporting to NetworkX graph...")

    # Create directed graph
    G = nx.DiGraph()

    # Add all entities as nodes
    entities = db_service.get_all_entities()
    for entity in entities:
        # entity is an Entity dataclass
        G.add_node(
            entity.id,
            name=entity.name,
            type=entity.type
        )

    # Add all relations as edges
    all_entities = db_service.get_all_entities()
    for entity in all_entities:
        relations = db_service.get_relations(entity.id)
        for rel in relations:
            # Extract attributes
            attrs = rel.get("attributes", {})
            weight = attrs.get("weight", 1.0)
            confidence = attrs.get("confidence", 1.0)

            # Add edge with attributes
            # Note: We pass weight and confidence separately, then other attrs
            edge_attrs = {k: v for k, v in attrs.items() if k not in ["weight", "confidence"]}
            G.add_edge(
                rel["source_id"],
                rel["target_id"],
                type=rel["rel_type"],
                weight=weight,
                confidence=confidence,
                **edge_attrs
            )

    print(f"✓ Created graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
    return G


def analyze_graph(G) -> None:
    """Perform basic graph analysis using NetworkX."""
    if G is None:
        return

    import networkx as nx

    print("\n" + "="*60)
    print("GRAPH ANALYSIS")
    print("="*60)

    # Basic statistics
    print(f"\nBasic Statistics:")
    print(f"  Nodes: {G.number_of_nodes()}")
    print(f"  Edges: {G.number_of_edges()}")
    print(f"  Density: {nx.density(G):.3f}")

    # Degree centrality (who is most connected?)
    print(f"\nDegree Centrality (most connected characters):")
    centrality = nx.degree_centrality(G)
    sorted_centrality = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
    for node_id, score in sorted_centrality[:3]:
        name = G.nodes[node_id]["name"]
        print(f"  {name}: {score:.3f}")

    # Weighted degree (sum of edge weights)
    print(f"\nWeighted Influence (sum of relationship strengths):")
    for node in G.nodes():
        name = G.nodes[node]["name"]
        # Sum weights of outgoing edges
        total_weight = sum(
            G[node][neighbor].get("weight", 1.0)
            for neighbor in G.successors(node)
        )
        print(f"  {name}: {total_weight:.2f}")

    # PageRank (importance considering network structure and weights)
    try:
        print(f"\nPageRank (network importance):")
        pagerank = nx.pagerank(G, weight="weight")
        sorted_pagerank = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)
        for node_id, score in sorted_pagerank[:3]:
            name = G.nodes[node_id]["name"]
            print(f"  {name}: {score:.3f}")
    except ImportError:
        print(f"\nPageRank: (requires scipy - install with: pip install scipy)")
    except Exception as e:
        print(f"\nPageRank: Error - {e}")

    # Find shortest weighted path between two nodes
    print(f"\nExample: Shortest Weighted Path")
    nodes = list(G.nodes())
    if len(nodes) >= 2:
        source = nodes[0]
        target = nodes[-1]
        source_name = G.nodes[source]["name"]
        target_name = G.nodes[target]["name"]

        try:
            # Use inverse weight (higher weight = shorter distance)
            path = nx.shortest_path(
                G, source, target,
                weight=lambda u, v, d: 1.0 / d.get("weight", 0.1)
            )
            path_names = [G.nodes[n]["name"] for n in path]
            print(f"  From {source_name} to {target_name}:")
            print(f"  Path: {' → '.join(path_names)}")
        except nx.NetworkXNoPath:
            print(f"  No path from {source_name} to {target_name}")

    # Strongly connected components
    print(f"\nStrongly Connected Components:")
    components = list(nx.strongly_connected_components(G))
    for i, comp in enumerate(components, 1):
        names = [G.nodes[n]["name"] for n in comp]
        print(f"  Component {i}: {', '.join(names)}")


def visualize_graph(G) -> None:
    """
    Visualize the graph using matplotlib.

    Note: This requires a display. Skip in headless environments.
    """
    if G is None:
        return

    try:
        import matplotlib.pyplot as plt
        import networkx as nx
    except ImportError:
        print("\nVisualization requires matplotlib: pip install matplotlib")
        return

    print("\n" + "="*60)
    print("VISUALIZATION")
    print("="*60)

    # Create figure
    plt.figure(figsize=(12, 8))

    # Use spring layout for positioning
    pos = nx.spring_layout(G, k=2, iterations=50)

    # Draw nodes
    nx.draw_networkx_nodes(
        G, pos,
        node_color='lightblue',
        node_size=3000,
        alpha=0.9
    )

    # Draw edges with varying thickness based on weight
    edges = G.edges()
    weights = [G[u][v].get("weight", 0.5) * 3 for u, v in edges]
    nx.draw_networkx_edges(
        G, pos,
        edge_color='gray',
        width=weights,
        alpha=0.6,
        arrows=True,
        arrowsize=20,
        arrowstyle='->'
    )

    # Draw labels
    labels = {node: G.nodes[node]["name"] for node in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, font_size=10)

    # Draw edge labels (relation types)
    edge_labels = {
        (u, v): G[u][v]["type"]
        for u, v in G.edges()
    }
    nx.draw_networkx_edge_labels(
        G, pos, edge_labels,
        font_size=8,
        font_color='red'
    )

    plt.title("ProjektKraken Relations Network\n(Edge thickness = relationship strength)")
    plt.axis('off')
    plt.tight_layout()

    # Try to save
    output_path = "relation_graph.png"
    try:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"✓ Graph saved to {output_path}")
    except Exception as e:
        print(f"✗ Could not save graph: {e}")

    # Try to show (will fail in headless environments)
    try:
        plt.show()
    except Exception:
        print("  (Display not available - graph saved to file only)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="NetworkX graph analysis example for ProjektKraken relations"
    )
    parser.add_argument(
        "--database", "-d",
        help="Path to .kraken database (if omitted, creates in-memory example)"
    )
    parser.add_argument(
        "--no-viz", action="store_true",
        help="Skip visualization (useful in headless environments)"
    )

    args = parser.parse_args()

    # Connect to database
    if args.database:
        print(f"Loading database: {args.database}")
        db_service = DatabaseService(args.database)
        db_service.connect()
    else:
        print("Creating in-memory example database...")
        db_service = DatabaseService(":memory:")
        db_service.connect()
        create_example_world(db_service)

    # Export to NetworkX
    G = export_to_networkx(db_service)

    # Analyze
    if G:
        analyze_graph(G)

        # Visualize (optional)
        if not args.no_viz:
            visualize_graph(G)

    # Cleanup
    db_service.close()


if __name__ == "__main__":
    main()
