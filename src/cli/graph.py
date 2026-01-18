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

        data = service.get_graph_data(
            db_service=db_service,
            include_tags=tags,
            include_rel_types=None,  # No arg support yet for relation types
        )

        output_file = Path(args.out_file)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"✓ Graph data exported to: {output_file}")
        print(f"  Nodes: {len(data.get('nodes', []))}")
        print(f"  Edges: {len(data.get('edges', []))}")
        return 0

    except Exception as e:
        logger.error(f"Failed to export graph data: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def main() -> None:
    """Main CLI entry point for graph tools."""
    parser = argparse.ArgumentParser(description="Export ProjektKraken graph data")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Export
    export_p = subparsers.add_parser("export", help="Export graph data to JSON")
    export_p.add_argument("--database", "-d", required=True)
    export_p.add_argument("--out-file", "-o", required=True, help="Output JSON file")
    export_p.add_argument("--tags", help="Comma-separated list of tags to filter by")
    export_p.set_defaults(func=export_graph)

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
