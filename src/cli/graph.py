#!/usr/bin/env python3
"""Graph Data CLI.

Provides command-line tools for exporting graph data for visualization.

Usage:
    python -m src.cli.graph export --database world.kraken --out-file graph.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from src.cli.utils import validate_database_path
from src.services.db_service import DatabaseService
from src.services.graph_data_service import GraphDataService

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def export_graph(args: argparse.Namespace) -> int:
    """Export graph data to JSON."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        service = GraphDataService()

        # Parse tags filter
        tags = None
        if args.tags:
            tags = [t.strip() for t in args.tags.split(",") if t.strip()]

        # Parse relation types filter
        rel_types = None
        if args.rel_types:
            rel_types = [t.strip() for t in args.rel_types.split(",") if t.strip()]

        nodes, edges = service.get_graph_data(
            db_service=db_service,
            include_tags=tags,
            include_rel_types=rel_types,
        )

        output_file = Path(args.out_file).resolve()
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"nodes": nodes, "edges": edges}, f, indent=2)

        print(f"[OK] Graph data exported to: {output_file}")
        print(f"  Nodes: {len(nodes)}")
        print(f"  Edges: {len(edges)}")
        return 0

    except Exception as e:
        logger.error(f"Failed to export graph data: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def register_commands(subparsers: argparse._SubParsersAction) -> None:  # type: ignore
    """Register graph subcommands with a parent subparsers group.

    Args:
        subparsers: The subparsers action group from a parent ArgumentParser.

    """
    # Export
    export_p = subparsers.add_parser("export", help="Export graph data to JSON")
    export_p.add_argument("--database", "-d", required=True)
    export_p.add_argument("--out-file", "-o", required=True, help="Output JSON file")
    export_p.add_argument("--tags", help="Comma-separated list of tags to filter by")
    export_p.add_argument(
        "--rel-types", help="Comma-separated list of relation types to filter by"
    )
    export_p.set_defaults(func=export_graph)


def main() -> None:
    """Main CLI entry point for graph tools."""
    parser = argparse.ArgumentParser(description="Export ProjektKraken graph data")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    register_commands(subparsers)

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if hasattr(args, "database"):
        if not validate_database_path(args.database, allow_create=False):
            sys.exit(1)

    if hasattr(args, "func"):
        sys.exit(args.func(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
