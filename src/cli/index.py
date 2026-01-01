#!/usr/bin/env python3
"""
Semantic Search Index Management CLI.

Provides command-line tools for building, querying, and managing
the semantic search index.

Usage:
    python -m src.cli.index rebuild --database world.kraken
    python -m src.cli.index rebuild --database world.kraken --type entity
    python -m src.cli.index query --database world.kraken \
        --text "find the wizard"
    python -m src.cli.index index-object --database world.kraken \
        --type entity --id <uuid>
"""

import argparse
import json
import logging
import sys

from src.cli.utils import validate_database_path
from src.services.db_service import DatabaseService
from src.services.search_service import create_search_service

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def rebuild_index(args: argparse.Namespace) -> int:
    """
    Rebuild the semantic search index.

    Args:
        args: Command-line arguments.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        # Determine object types to index
        if args.type == "all":
            object_types = ["entity", "event"]
        else:
            object_types = [args.type]

        excluded = None
        if args.excluded_attributes:
            excluded = [
                a.strip() for a in args.excluded_attributes.split(",") if a.strip()
            ]

        print(f"Rebuilding index for: {', '.join(object_types)}")
        print(f"Provider: {args.provider}")
        if args.model:
            print(f"Model: {args.model}")

        # Create search service
        assert db_service._connection is not None, "Database not connected"
        search_service = create_search_service(
            db_service._connection, provider_name=args.provider, model=args.model
        )

        # Rebuild index
        counts = search_service.rebuild_index(
            object_types=object_types, excluded_attributes=excluded
        )

        print("\n✓ Index rebuild complete:")
        for obj_type, count in counts.items():
            print(f"  {obj_type}: {count} objects indexed")

        return 0

    except Exception as e:
        logger.error(f"Failed to rebuild index: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def delete_object(args: argparse.Namespace) -> int:
    """
    Delete embeddings for a single object.

    Args:
        args: Command-line arguments.

    Returns:
        int: Exit code.
    """
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        print(f"Deleting embeddings for {args.type} {args.id}")
        if args.model:
            print(f"Model: {args.model}")

        # Create search service
        assert db_service._connection is not None, "Database not connected"
        search_service = create_search_service(
            db_service._connection, provider_name="lmstudio", model=args.model
        )

        search_service.delete_index_for_object(
            object_type=args.type, object_id=args.id, model=args.model
        )

        print(f"✓ Deleted embeddings for {args.type} {args.id}")
        return 0

    except Exception as e:
        logger.error(f"Failed to delete object embeddings: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def index_object(args: argparse.Namespace) -> int:
    """
    Index a single object.

    Args:
        args: Command-line arguments.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        print(f"Indexing {args.type} {args.id}")
        print(f"Provider: {args.provider}")
        if args.model:
            print(f"Model: {args.model}")

        # Create search service
        assert db_service._connection is not None, "Database not connected"
        search_service = create_search_service(
            db_service._connection, provider_name=args.provider, model=args.model
        )

        excluded = None
        if args.excluded_attributes:
            excluded = [
                a.strip() for a in args.excluded_attributes.split(",") if a.strip()
            ]

        # Index the object
        if args.type == "entity":
            search_service.index_entity(args.id, excluded_attributes=excluded)
        elif args.type == "event":
            search_service.index_event(args.id, excluded_attributes=excluded)
        else:
            print(f"✗ Unknown object type: {args.type}")
            return 1

        print(f"✓ Indexed {args.type} {args.id}")
        return 0

    except Exception as e:
        logger.error(f"Failed to index object: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def query_index(args: argparse.Namespace) -> int:
    """
    Query the semantic search index.

    Args:
        args: Command-line arguments.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        if args.verbose:
            print(f"Query: {args.text}")
            print(f"Type filter: {args.type or 'all'}")
            print(f"Top-k: {args.top_k}")
            print(f"Provider: {args.provider}")
            if args.model:
                print(f"Model: {args.model}")
            print()

        # Create search service
        assert db_service._connection is not None, "Database not connected"
        search_service = create_search_service(
            db_service._connection, provider_name=args.provider, model=args.model
        )

        # Query
        results = search_service.query(
            text=args.text,
            object_type=args.type,
            top_k=args.top_k,
            model=args.model,
        )

        # Output results
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            if not results:
                print("No results found.")
                return 0

            print(f"Found {len(results)} results:\n")
            for i, result in enumerate(results, 1):
                print(f"{i}. {result['name']} ({result['type']})")
                print(f"   Score: {result['score']:.4f}")
                print(f"   Type: {result['object_type']}")
                print(f"   ID: {result['object_id']}")
                print()

        return 0

    except Exception as e:
        logger.error(f"Failed to query index: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Semantic Search Index Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Global options
    parser.add_argument(
        "-d", "--database", required=True, help="Path to .kraken database file"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Rebuild command
    rebuild_parser = subparsers.add_parser(
        "rebuild", help="Rebuild the semantic search index"
    )
    rebuild_parser.add_argument(
        "--type",
        choices=["entity", "event", "all"],
        default="all",
        help="Object type to index (default: all)",
    )
    rebuild_parser.add_argument(
        "--provider",
        choices=["lmstudio", "sentence-transformers"],
        default="lmstudio",
        help="Embedding provider (default: lmstudio)",
    )
    rebuild_parser.add_argument(
        "--model", help="Model name override (uses env var if not specified)"
    )
    rebuild_parser.add_argument(
        "--excluded-attributes",
        help="Comma-separated list of attributes to exclude from indexing",
    )

    # Index-object command
    index_parser = subparsers.add_parser("index-object", help="Index a single object")
    index_parser.add_argument(
        "--type",
        choices=["entity", "event"],
        required=True,
        help="Object type",
    )
    index_parser.add_argument(
        "--id",
        required=True,
        help="Object UUID",
    )
    index_parser.add_argument(
        "--provider",
        choices=["lmstudio", "sentence-transformers"],
        default="lmstudio",
        help="Embedding provider (default: lmstudio)",
    )
    index_parser.add_argument(
        "--model", help="Model name override (uses env var if not specified)"
    )
    index_parser.add_argument(
        "--excluded-attributes",
        help="Comma-separated list of attributes to exclude from indexing",
    )

    # Query command
    query_parser = subparsers.add_parser(
        "query", help="Query the semantic search index"
    )
    query_parser.add_argument(
        "--text",
        required=True,
        help="Query text",
    )
    query_parser.add_argument(
        "--type",
        choices=["entity", "event"],
        help="Filter by object type (default: search all)",
    )
    query_parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of results to return (default: 10)",
    )
    query_parser.add_argument(
        "--provider",
        choices=["lmstudio", "sentence-transformers"],
        default="lmstudio",
        help="Embedding provider (default: lmstudio)",
    )
    query_parser.add_argument(
        "--model", help="Model name override (uses env var if not specified)"
    )
    query_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    # Delete-object command
    del_obj_parser = subparsers.add_parser(
        "delete-object", help="Delete embeddings for a single object"
    )
    del_obj_parser.add_argument(
        "--type",
        choices=["entity", "event"],
        required=True,
        help="Object type",
    )
    del_obj_parser.add_argument(
        "--id",
        required=True,
        help="Object UUID",
    )
    del_obj_parser.add_argument(
        "--model", help="Model name override (if expecting specific model deletion)"
    )

    # Parse arguments
    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate database path
    if not validate_database_path(args.database):
        print(f"✗ Database file not found: {args.database}")
        return 1

    # Execute command
    if args.command == "rebuild":
        return rebuild_index(args)
    elif args.command == "index-object":
        return index_object(args)
    elif args.command == "query":
        return query_index(args)
    elif args.command == "delete-object":
        return delete_object(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
