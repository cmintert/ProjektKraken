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

import ast
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


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
        if len(parts) >= 2:
            col_name = parts[0]
            col_type = parts[1]
            constraints = parts[2] if len(parts) > 2 else ""
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
    index_pattern = r"CREATE INDEX IF NOT EXISTS (\w+) ON (\w+)\s*\("
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
    lines = ["```mermaid", "erDiagram"]

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

        # List indexes for this table
        table_indexes = [idx_name for idx_name, tbl in indexes if tbl == table_name]
        if table_indexes:
            lines.append(
                f"\n**Indexes:** {', '.join(f'`{idx}`' for idx in table_indexes)}\n"
            )
        else:
            lines.append("")

    return "\n".join(lines)


def main():
    """Main function to generate schema documentation."""
    print("Extracting database schema from DatabaseService...")

    try:
        # Extract schema SQL
        schema_sql = extract_schema_sql()

        # Parse all CREATE TABLE statements
        create_table_pattern = r"CREATE TABLE IF NOT EXISTS[^;]+"
        table_sqls = re.findall(
            create_table_pattern, schema_sql, re.IGNORECASE | re.DOTALL
        )

        tables = {}
        all_foreign_keys = []

        for table_sql in table_sqls:
            table_name, columns = parse_create_table(table_sql)
            if table_name:
                tables[table_name] = columns

                # Extract foreign keys from this table
                fks = extract_foreign_keys(table_sql)
                for fk_col, target_table, target_col in fks:
                    all_foreign_keys.append(
                        (table_name, fk_col, target_table, target_col)
                    )

        # Extract indexes
        indexes = extract_indexes(schema_sql)

        print(f"Found {len(tables)} tables and {len(indexes)} indexes")

        # Generate Mermaid diagram
        mermaid = generate_mermaid_diagram(tables, all_foreign_keys)

        # Generate markdown tables
        md_tables = generate_markdown_tables(tables, indexes)

        # Write output
        output_path = Path(__file__).parent / "SCHEMA_REFERENCE.md"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# Database Schema Reference\n\n")
            f.write(
                "**This file is auto-generated from the DatabaseService implementation.**\n\n"
            )
            f.write("Do not edit this file manually. ")
            f.write("To update the schema, modify `src/services/db_service.py` ")
            f.write("and rebuild the documentation.\n\n")
            f.write("## Entity Relationship Diagram\n\n")
            f.write(mermaid)
            f.write("\n\n")
            f.write(md_tables)

        print(f"✓ Schema documentation written to {output_path}")
        return 0

    except Exception as e:
        print(f"✗ Error generating schema documentation: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
