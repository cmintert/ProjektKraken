#!/usr/bin/env python3
"""Unified CLI Entry Point for ProjektKraken.

Provides a centralized command-line interface that routes to all available
CLI tools (event, entity, relation, map, etc.).

Usage:
    python -m src.cli.cli --help
    python -m src.cli.cli event list --database world.kraken
    python -m src.cli.cli entity create --database world.kraken --name "Entity" --type character
    python -m src.cli.cli info show --database world.kraken
"""

import argparse
import logging
import sys

from src.cli import attachment, backup, calendar, entity, event, graph, index
from src.cli import info, longform, map as cli_map
from src.cli import obsidian, relation, timeline, wiki
from src.cli.utils import validate_database_path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Main unified CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ProjektKraken CLI Tools - Manage your worlds from the command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s event list --database world.kraken
  %(prog)s entity create --database world.kraken --name "John" --type character
  %(prog)s relation add --database world.kraken --source <id> --target <id> --type "knows"
  %(prog)s info show --database world.kraken
  %(prog)s graph export --database world.kraken --out-file graph.json

For help on a specific command:
  %(prog)s <command> --help
  %(prog)s event create --help
        """,
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="module", help="Available modules")

    # Register all CLI modules
    event_sp = subparsers.add_parser(
        "event", help="Manage events", aliases=["events"]
    )
    event_sp.add_argument("--verbose", "-v", action="store_true")
    event_subs = event_sp.add_subparsers(dest="command")
    event.register_commands(event_subs)

    entity_sp = subparsers.add_parser(
        "entity", help="Manage entities", aliases=["entities"]
    )
    entity_sp.add_argument("--verbose", "-v", action="store_true")
    entity_subs = entity_sp.add_subparsers(dest="command")
    entity.register_commands(entity_subs)

    relation_sp = subparsers.add_parser(
        "relation", help="Manage relations", aliases=["relations"]
    )
    relation_sp.add_argument("--verbose", "-v", action="store_true")
    relation_subs = relation_sp.add_subparsers(dest="command")
    relation.register_commands(relation_subs)

    map_sp = subparsers.add_parser("map", help="Manage maps")
    map_sp.add_argument("--verbose", "-v", action="store_true")
    map_subs = map_sp.add_subparsers(dest="command")
    cli_map.register_commands(map_subs)

    attachment_sp = subparsers.add_parser("attachment", help="Manage attachments")
    attachment_sp.add_argument("--verbose", "-v", action="store_true")
    attachment_subs = attachment_sp.add_subparsers(dest="command")
    attachment.register_commands(attachment_subs)

    calendar_sp = subparsers.add_parser("calendar", help="Manage calendars")
    calendar_sp.add_argument("--verbose", "-v", action="store_true")
    calendar_subs = calendar_sp.add_subparsers(dest="command")
    calendar.register_commands(calendar_subs)

    timeline_sp = subparsers.add_parser("timeline", help="Manage timeline settings")
    timeline_sp.add_argument("--verbose", "-v", action="store_true")
    timeline_subs = timeline_sp.add_subparsers(dest="command")
    timeline.register_commands(timeline_subs)

    wiki_sp = subparsers.add_parser("wiki", help="Manage wiki links")
    wiki_sp.add_argument("--verbose", "-v", action="store_true")
    wiki_subs = wiki_sp.add_subparsers(dest="command")
    wiki.register_commands(wiki_subs)

    index_sp = subparsers.add_parser("index", help="Manage search index")
    index_sp.add_argument("--verbose", "-v", action="store_true")
    index_subs = index_sp.add_subparsers(dest="command")
    index.register_commands(index_subs)

    longform_sp = subparsers.add_parser("longform", help="Manage longform documents")
    longform_sp.add_argument("--verbose", "-v", action="store_true")
    longform_subs = longform_sp.add_subparsers(dest="command")
    longform.register_commands(longform_subs)

    obsidian_sp = subparsers.add_parser("obsidian", help="Export to Obsidian")
    obsidian_sp.add_argument("--verbose", "-v", action="store_true")
    obsidian_subs = obsidian_sp.add_subparsers(dest="command")
    obsidian.register_commands(obsidian_subs)

    backup_sp = subparsers.add_parser("backup", help="Manage backups")
    backup_sp.add_argument("--verbose", "-v", action="store_true")
    backup_subs = backup_sp.add_subparsers(dest="command")
    backup.register_commands(backup_subs)

    graph_sp = subparsers.add_parser("graph", help="Export graph data")
    graph_sp.add_argument("--verbose", "-v", action="store_true")
    graph_subs = graph_sp.add_subparsers(dest="command")
    graph.register_commands(graph_subs)

    info_sp = subparsers.add_parser("info", help="Inspect database")
    info_sp.add_argument("--verbose", "-v", action="store_true")
    info_subs = info_sp.add_subparsers(dest="command")
    info.register_commands(info_subs)

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate database path if present
    if hasattr(args, "database"):
        # Determine if create is allowed
        allow_create = hasattr(args, "command") and args.command == "create"
        if not validate_database_path(args.database, allow_create=allow_create):
            sys.exit(1)

    # Execute command if one was specified
    if hasattr(args, "func"):
        sys.exit(args.func(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
