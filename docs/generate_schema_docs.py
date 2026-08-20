#!/usr/bin/env python3
"""
Generate database schema documentation from the DatabaseService implementation.

This script extracts the SQL schema directly from the _init_schema() method
in src/services/db_service.py and generates:
1. A Mermaid ER diagram for visual representation
2. Markdown tables with detailed column information

The output is written to SCHEMA_REFERENCE.md and is automatically regenerated
during Sphinx builds to stay synchronized with code changes.
"""

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

_MIN_COLUMN_DEFINITION_PARTS = 2


def extract_schema_sql() -> str:
    """
    Extract the schema SQL from DatabaseService._init_schema() method.

    Returns:
        str: The SQL schema string from the _init_schema method.
    """
    # Path to db_service.py
    db_service_path = (
        Path(__file__).parent.parent / "src" / "services" / "db_service.py"
    )

    if not db_service_path.exists():
        raise FileNotFoundError(f"Could not find db_service.py at {db_service_path}")

    # Read the source code
    with open(db_service_path, "r", encoding="utf-8") as f:
        source = f.read()

    # Parse the AST
    tree = ast.parse(source)

    # Find the DatabaseService class
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "DatabaseService":
            # Find the _init_schema method
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "_init_schema":
                    # Look for the schema_sql variable assignment
                    for stmt in item.body:
                        if isinstance(stmt, ast.Assign):
                            for target in stmt.targets:
                                if (
                                    isinstance(target, ast.Name)
                                    and target.id == "schema_sql"
                                ):
                                    # Extract the string value
                                    if isinstance(stmt.value, ast.Constant):
                                        return stmt.value.value

    raise ValueError("Could not find schema_sql in DatabaseService._init_schema()")


def parse_create_table(sql: str) -> Tuple[str, List[Tuple[str, str, str]]]:
    """
    Parse a CREATE TABLE statement.

    Args:
        sql: The CREATE TABLE SQL statement.

    Returns:
        Tuple of (table_name, list of (column_name, type, constraints))
    """
    # Extract table name
    table_match = re.search(r"CREATE TABLE IF NOT EXISTS (\w+)", sql, re.IGNORECASE)
    if not table_match:
        return None, []

    table_name = table_match.group(1)

    # Extract column definitions (between parentheses)
    paren_content = re.search(r"\((.+)\)", sql, re.DOTALL)
    if not paren_content:
        return table_name, []

    content = paren_content.group(1)

    # Split by commas, but be careful with nested parentheses
    lines = [line.strip() for line in content.split("\n") if line.strip()]

    columns = []
    for line in lines:
        # Skip lines that are constraints or comments
        if line.startswith("--"):
            continue
        if line.upper().startswith(("PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK")):
            continue

        # Remove trailing comma
        line = line.rstrip(",")

        # Parse column definition
        parts = line.split(None, 2)  # Split into name, type, rest
        if len(parts) >= _MIN_COLUMN_DEFINITION_PARTS:
            col_name = parts[0]
            col_type = parts[1]
            constraints = (
                parts[2] if len(parts) > _MIN_COLUMN_DEFINITION_PARTS else ""
            )
            columns.append((col_name, col_type, constraints))

    return table_name, columns


def extract_foreign_keys(sql: str) -> List[Tuple[str, str, str]]:
    """
    Extract FOREIGN KEY constraints from SQL.

    Returns:
        List of (source_table, column, target_table)
    """
    fk_pattern = r"FOREIGN KEY\s*\((\w+)\)\s*REFERENCES\s+(\w+)\s*\((\w+)\)"
    matches = re.findall(fk_pattern, sql, re.IGNORECASE)
    return matches


def extract_indexes(schema_sql: str) -> List[Tuple[str, str]]:
    """
    Extract CREATE INDEX statements.

    Returns:
        List of (index_name, table_name)
    """
    index_pattern = (
        r"CREATE (?:UNIQUE )?INDEX IF NOT EXISTS (\w+)\s+ON\s+(\w+)\s*\("
    )
    matches = re.findall(index_pattern, schema_sql, re.IGNORECASE)
    return matches


def generate_mermaid_diagram(
    tables: Dict[str, List[Tuple[str, str, str]]],
    foreign_keys: List[Tuple[str, str, str, str]],
) -> str:
    """
    Generate a Mermaid ER diagram from the schema.

    Args:
        tables: Dictionary of table_name -> [(col_name, col_type, constraints)]
        foreign_keys: List of (source_table, source_col, target_table, target_col)

    Returns:
        str: Mermaid diagram code
    """
    lines = ["```{mermaid}", "erDiagram"]

    # Add tables with columns
    for table_name, columns in tables.items():
        lines.append(f"    {table_name} {{")
        for col_name, col_type, constraints in columns:
            # Determine if it's a primary key
            pk_marker = " PK" if "PRIMARY KEY" in constraints.upper() else ""
            fk_marker = " FK" if "FOREIGN KEY" in constraints.upper() else ""

            lines.append(f"        {col_type} {col_name}{pk_marker}{fk_marker}")
        lines.append("    }")
        lines.append("")

    # Add relationships
    for source_table, source_col, target_table, target_col in foreign_keys:
        # Many-to-one relationship
        lines.append(f'    {source_table} }}o--|| {target_table} : "{source_col}"')

    lines.append("```")
    return "\n".join(lines)


def generate_markdown_tables(
    tables: Dict[str, List[Tuple[str, str, str]]], indexes: List[Tuple[str, str]]
) -> str:
    """
    Generate markdown tables for each database table.

    Args:
        tables: Dictionary of table_name -> [(col_name, col_type, constraints)]
        indexes: List of (index_name, table_name)

    Returns:
        str: Markdown tables
    """
    lines = ["## Table Definitions\n"]

    for table_name, columns in tables.items():
        lines.append(f"### `{table_name}`\n")

        # Create markdown table
        lines.append("| Column | Type | Constraints |")
        lines.append("|--------|------|-------------|")

        for col_name, col_type, constraints in columns:
            # Escape pipes in constraints
            constraints_clean = constraints.replace("|", "\\|")
            lines.append(f"| `{col_name}` | {col_type} | {constraints_clean} |")

        if table_name == "moving_features":
            lines.extend(
                [
                    "",
                    "`trajectory` stores an OGC MF-JSON `MovingPoint` with parallel "
                    "`coordinates` and `datetimes` arrays. For example:",
                    "",
                    "```json",
                    '{"type":"MovingPoint","coordinates":[[0.25,0.5],[0.75,0.5]],'
                    '"datetimes":[10.0,20.0],"interpolation":"Linear"}',
                    "```",
                    "",
                    "The parallel `properties` object may contain unrelated extension "
                    "data. Its `kraken_trajectory` member is versioned authoring "
                    "metadata schema version 2. `points` assign stable UUIDs and "
                    "classify each coordinate as a `timed` location or automatic "
                    "`route` point. `legs` connect consecutive timed locations with "
                    "a `linear` or `step` mode and `distance` timing.",
                    "",
                    "MF-JSON remains the fully dated playback projection. Missing, "
                    "unsupported, malformed, or inconsistent authoring metadata "
                    "makes the trajectory incompatible; it is logged and deleted "
                    "during map trajectory load.",
                ]
            )

        if table_name == "feature_geometry_states":
            lines.extend(
                [
                    "",
                    "Each row replaces a path or region's Base Geometry from "
                    "`effective_date` until a later row becomes applicable. The "
                    "stored anchor is recalculated from `geometry`; styles and "
                    "labels remain properties of the parent marker.",
                ]
            )

        # List indexes for this table
        table_indexes = [idx_name for idx_name, tbl in indexes if tbl == table_name]
        if table_indexes:
            lines.append(
                f"\n**Indexes:** {', '.join(f'`{idx}`' for idx in table_indexes)}\n"
            )
        else:
            lines.append("")

    return "\n".join(lines)


def build_document() -> str:
    """Build the complete generated schema reference."""
    schema_sql = extract_schema_sql()

    create_table_pattern = r"CREATE TABLE IF NOT EXISTS[^;]+"
    table_sqls = re.findall(create_table_pattern, schema_sql, re.IGNORECASE | re.DOTALL)

    tables = {}
    all_foreign_keys = []

    for table_sql in table_sqls:
        table_name, columns = parse_create_table(table_sql)
        if table_name:
            tables[table_name] = columns
            foreign_keys = extract_foreign_keys(table_sql)
            for foreign_key_column, target_table, target_column in foreign_keys:
                all_foreign_keys.append(
                    (
                        table_name,
                        foreign_key_column,
                        target_table,
                        target_column,
                    )
                )

    indexes = extract_indexes(schema_sql)
    mermaid = generate_mermaid_diagram(tables, all_foreign_keys)
    markdown_tables = generate_markdown_tables(tables, indexes)

    return "\n".join(
        [
            "# Database Schema Reference",
            "",
            "This file is generated from `DatabaseService._init_schema()`.",
            "Do not edit it manually.",
            "",
            "## Entity Relationship Diagram",
            "",
            mermaid,
            "",
            markdown_tables,
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    """Parse generator command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate the ProjektKraken database schema reference."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "reference" / "database-schema.md",
        help="Destination Markdown file.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the destination differs from generated content.",
    )
    return parser.parse_args()


def main() -> int:
    """Generate the schema reference or verify that it is current."""
    args = parse_args()
    output_path = args.output.resolve()
    print("Extracting database schema from DatabaseService...")

    try:
        content = build_document()
        if args.check:
            if not output_path.exists():
                print(f"Schema reference is missing: {output_path}", file=sys.stderr)
                return 1
            if output_path.read_text(encoding="utf-8") != content:
                print(
                    "Schema reference is out of date. "
                    "Run docs/generate_schema_docs.py.",
                    file=sys.stderr,
                )
                return 1
            print(f"Schema reference is current: {output_path}")
            return 0

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        print(f"Schema reference written to {output_path}")
        return 0

    except Exception as e:
        print(f"Schema generation failed: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
