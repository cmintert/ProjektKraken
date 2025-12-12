"""
Longform Document Builder Service.

Provides functions to build, manipulate, and export a single live longform
document assembled from Events and Entities. Stores per-record metadata in
the attributes JSON column under attributes.longform.<doc_id>.

Key Features:
- Single live document (doc_id = "default")
- Float/gap positioning system (100, 200, 300...)
- Parent-child nesting with depth tracking
- Title overrides
- Canonical content edits update underlying Event/Entity
- Export to Markdown with ID markers

All operations work with the attributes JSON column, loading and dumping
in Python layer to maintain SQLite compatibility.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlite3 import Connection

logger = logging.getLogger(__name__)

# Constants
DOC_ID_DEFAULT = "default"
DEFAULT_POSITION_GAP = 100.0

# Security: Whitelist of valid table names to prevent SQL injection
VALID_TABLES = ("events", "entities")


def _validate_table_name(table: str) -> None:
    """
    Validate table name against whitelist to prevent SQL injection.

    This function ensures that table names used in f-string SQL queries
    are safe. While parameterized queries (?) protect against injection
    in data values, table names cannot be parameterized in standard SQL.
    Therefore, we validate them against a strict whitelist.

    Args:
        table: Table name to validate.

    Raises:
        ValueError: If table name is not in the whitelist.
    """
    if table not in VALID_TABLES:
        raise ValueError(
            f"Invalid table name: {table}. Must be one of {VALID_TABLES}"
        )


def _safe_json_loads(json_str: str) -> dict:
    """
    Safely load JSON string, returning empty dict on failure.

    Args:
        json_str: JSON string to parse.

    Returns:
        dict: Parsed JSON or empty dict if parsing fails.
    """
    if not json_str:
        return {}
    try:
        result = json.loads(json_str)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse JSON: {e}. Returning empty dict.")
        return {}


def _get_longform_meta(
    attributes: dict, doc_id: str = DOC_ID_DEFAULT
) -> Optional[dict]:
    """
    Extract longform metadata from attributes dict.

    Args:
        attributes: The attributes dictionary.
        doc_id: Document ID to extract metadata for.

    Returns:
        Optional[dict]: Longform metadata dict or None if not present.
    """
    lf_data = attributes.get("longform")
    if not isinstance(lf_data, dict):
        return None
    return lf_data.get(doc_id)


def _set_longform_meta(
    attributes: dict, meta: dict, doc_id: str = DOC_ID_DEFAULT
) -> dict:
    """
    Set longform metadata in attributes dict.

    Args:
        attributes: The attributes dictionary to modify.
        meta: The longform metadata to set.
        doc_id: Document ID to set metadata for.

    Returns:
        dict: Updated attributes dictionary.
    """
    if "longform" not in attributes or not isinstance(attributes["longform"], dict):
        attributes["longform"] = {}
    attributes["longform"][doc_id] = meta
    return attributes


def read_all_longform_items(
    conn: Connection, doc_id: str = DOC_ID_DEFAULT
) -> List[Dict[str, Any]]:
    """
    Read all events and entities that have longform metadata.

    Args:
        conn: SQLite connection.
        doc_id: Document ID to filter by.

    Returns:
        List[Dict]: List of items with keys: table, id, name, content,
                    attributes (dict), meta (dict).
    """
    items = []

    # Read events
    cursor = conn.execute("SELECT id, name, description, attributes FROM events")
    for row in cursor.fetchall():
        row_dict = dict(row)
        attrs = _safe_json_loads(row_dict.get("attributes", "{}"))
        meta = _get_longform_meta(attrs, doc_id)
        if meta:
            items.append(
                {
                    "table": "events",
                    "id": row_dict["id"],
                    "name": row_dict["name"],
                    "content": row_dict.get("description", ""),
                    "attributes": attrs,
                    "meta": meta,
                }
            )

    # Read entities
    cursor = conn.execute("SELECT id, name, description, attributes FROM entities")
    for row in cursor.fetchall():
        row_dict = dict(row)
        attrs = _safe_json_loads(row_dict.get("attributes", "{}"))
        meta = _get_longform_meta(attrs, doc_id)
        if meta:
            items.append(
                {
                    "table": "entities",
                    "id": row_dict["id"],
                    "name": row_dict["name"],
                    "content": row_dict.get("description", ""),
                    "attributes": attrs,
                    "meta": meta,
                }
            )

    return items

    items = read_all_longform_items(conn, doc_id)
    return items


def ensure_all_items_indexed(conn: Connection, doc_id: str = DOC_ID_DEFAULT) -> None:
    """
    Ensure all events and entities in the database are present in the longform document.
    Missing items are added to the end of the document, sorted alphabetically.

    Args:
        conn: SQLite connection.
        doc_id: Document ID.
    """
    # 1. Identify existing items and find max position
    existing_ids = set()
    max_position = 0.0

    # We can reuse read_all_longform_items to get current state
    current_items = read_all_longform_items(conn, doc_id)
    for item in current_items:
        existing_ids.add(item["id"])
        pos = item["meta"].get("position", 0.0)
        if pos > max_position:
            max_position = pos

    # 2. Find missing items
    missing_items = []

    # Check Events
    cursor = conn.execute("SELECT id, name FROM events")
    for row in cursor.fetchall():
        if row["id"] not in existing_ids:
            missing_items.append(
                {"table": "events", "id": row["id"], "name": row["name"]}
            )

    # Check Entities
    cursor = conn.execute("SELECT id, name FROM entities")
    for row in cursor.fetchall():
        if row["id"] not in existing_ids:
            missing_items.append(
                {"table": "entities", "id": row["id"], "name": row["name"]}
            )

    if not missing_items:
        return

    # 3. Sort missing items alphabetically
    missing_items.sort(key=lambda x: x["name"].lower())

    # 4. Append to document
    # Start gap from max_position. If max_position is 0 (empty doc), start at 100.
    start_position = max_position if max_position > 0 else 0.0

    logger.info(
        f"Auto-populating {len(missing_items)} items to longform doc '{doc_id}'"
    )

    for idx, item in enumerate(missing_items):
        new_pos = start_position + ((idx + 1) * DEFAULT_POSITION_GAP)

        insert_or_update_longform_meta(
            conn,
            item["table"],
            item["id"],
            position=new_pos,
            doc_id=doc_id,
            # Default to top-level
            parent_id=None,
            depth=0,
        )


def build_longform_sequence(
    conn: Connection, doc_id: str = DOC_ID_DEFAULT
) -> List[Dict[str, Any]]:
    """
    Build an ordered sequence of longform items for rendering.

    Computes heading_level based on parent-child relationships and depth.
    Returns items in reading order.

    Automatically adds missing DB items to the end of the document.

    Args:
        conn: SQLite connection.
        doc_id: Document ID to build sequence for.

    Returns:
        List[Dict]: Ordered list of items with heading_level computed.
                    Each item includes: table, id, name, content, meta, heading_level.
    """
    # 0. Sync check: ensure everything is in the doc
    ensure_all_items_indexed(conn, doc_id)

    items = read_all_longform_items(conn, doc_id)

    # Build parent-child map
    children_map: Dict[Optional[str], List[Dict]] = {}
    for item in items:
        parent_id = item["meta"].get("parent_id")
        if parent_id not in children_map:
            children_map[parent_id] = []
        children_map[parent_id].append(item)

    # Sort children by position
    for parent_id in children_map:
        children_map[parent_id].sort(key=lambda x: x["meta"].get("position", 0.0))

    # Recursively build sequence
    def _walk(parent_id: Optional[str], current_depth: int = 0) -> List[Dict]:
        """Walk the tree and build ordered sequence."""
        result = []
        if parent_id not in children_map:
            return result

        for item in children_map[parent_id]:
            # Compute heading level (1-6, capped)
            item_depth = item["meta"].get("depth", 0)
            heading_level = min(max(item_depth + 1, 1), 6)

            # Create output item
            output_item = {
                "table": item["table"],
                "id": item["id"],
                "name": item["name"],
                "content": item["content"],
                "meta": item["meta"],
                "heading_level": heading_level,
            }
            result.append(output_item)

            # Recursively add children
            result.extend(_walk(item["id"], item_depth + 1))

        return result

    return _walk(None, 0)


def insert_or_update_longform_meta(
    conn: Connection,
    table: str,
    row_id: str,
    *,
    position: Optional[float] = ...,  # Use Ellipsis as sentinel
    parent_id: Optional[str] = ...,
    depth: Optional[int] = ...,
    title_override: Optional[str] = ...,
    doc_id: str = DOC_ID_DEFAULT,
) -> None:
    """
    Insert or update longform metadata for a specific row.

    Loads current attributes, updates longform metadata, and writes back.

    Args:
        conn: SQLite connection.
        table: Table name ("events" or "entities").
        row_id: Row ID to update.
        position: Optional position value (float). Use ... to skip updating.
        parent_id: Optional parent ID. Use ... to skip updating, None to clear.
        depth: Optional depth value (int). Use ... to skip updating.
        title_override: Optional title override. Use ... to skip updating.
        doc_id: Document ID.

    Raises:
        ValueError: If table is invalid or row not found.
    """
    _validate_table_name(table)

    # Read current attributes
    # Security: table name validated above, row_id is parameterized
    cursor = conn.execute(f"SELECT attributes FROM {table} WHERE id = ?", (row_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Row {row_id} not found in {table}")

    attrs = _safe_json_loads(row["attributes"])
    meta = _get_longform_meta(attrs, doc_id) or {}

    # Update metadata fields (only if not sentinel)
    if position is not ...:
        meta["position"] = position
    if parent_id is not ...:
        meta["parent_id"] = parent_id
    if depth is not ...:
        meta["depth"] = depth
    if title_override is not ...:
        meta["title_override"] = title_override

    # Set updated metadata
    attrs = _set_longform_meta(attrs, meta, doc_id)

    # Write back
    # Security: table name validated above, values are parameterized
    conn.execute(
        f"UPDATE {table} SET attributes = ? WHERE id = ?",
        (json.dumps(attrs), row_id),
    )
    conn.commit()
    logger.debug(f"Updated longform metadata for {table}.{row_id}")


def place_between_siblings_and_set_parent(
    conn: Connection,
    target_table: str,
    target_id: str,
    prev_sibling: Optional[Tuple[str, str]],
    next_sibling: Optional[Tuple[str, str]],
    parent_id: Optional[str],
    doc_id: str = DOC_ID_DEFAULT,
) -> None:
    """
    Place an item between two siblings and set its parent.

    Computes a gap position between prev_sibling and next_sibling.
    If no siblings, assigns a default position.

    Args:
        conn: SQLite connection.
        target_table: Table of the item to move.
        target_id: ID of the item to move.
        prev_sibling: Tuple of (table, id) for previous sibling, or None.
        next_sibling: Tuple of (table, id) for next sibling, or None.
        parent_id: Parent ID to set.
        doc_id: Document ID.
    """
    _validate_table_name(target_table)

    prev_pos = None
    next_pos = None

    # Get previous sibling position
    if prev_sibling:
        prev_table, prev_id = prev_sibling
        _validate_table_name(prev_table)
        # Security: table names validated above, IDs are parameterized
        cursor = conn.execute(
            f"SELECT attributes FROM {prev_table} WHERE id = ?", (prev_id,)
        )
        row = cursor.fetchone()
        if row:
            attrs = _safe_json_loads(row["attributes"])
            meta = _get_longform_meta(attrs, doc_id)
            if meta:
                prev_pos = meta.get("position")

    # Get next sibling position
    if next_sibling:
        next_table, next_id = next_sibling
        _validate_table_name(next_table)
        # Security: table name validated above, ID is parameterized
        cursor = conn.execute(
            f"SELECT attributes FROM {next_table} WHERE id = ?", (next_id,)
        )
        row = cursor.fetchone()
        if row:
            attrs = _safe_json_loads(row["attributes"])
            meta = _get_longform_meta(attrs, doc_id)
            if meta:
                next_pos = meta.get("position")

    # Compute new position
    if prev_pos is not None and next_pos is not None:
        new_position = (prev_pos + next_pos) / 2.0
    elif prev_pos is not None:
        new_position = prev_pos + DEFAULT_POSITION_GAP
    elif next_pos is not None:
        new_position = next_pos - DEFAULT_POSITION_GAP
    else:
        # No siblings, use default
        new_position = DEFAULT_POSITION_GAP

    # Compute depth from parent
    depth = 0
    if parent_id:
        # Find parent in either table
        # Security: Iterating over hardcoded table list, IDs are parameterized
        for parent_table in VALID_TABLES:
            cursor = conn.execute(
                f"SELECT attributes FROM {parent_table} WHERE id = ?", (parent_id,)
            )
            row = cursor.fetchone()
            if row:
                attrs = _safe_json_loads(row["attributes"])
                meta = _get_longform_meta(attrs, doc_id)
                if meta:
                    depth = meta.get("depth", 0) + 1
                break

    # Update target
    insert_or_update_longform_meta(
        conn,
        target_table,
        target_id,
        position=new_position,
        parent_id=parent_id,
        depth=depth,
        doc_id=doc_id,
    )


def reindex_document_positions(conn: Connection, doc_id: str = DOC_ID_DEFAULT) -> None:
    """
    Reindex all positions to 100, 200, 300... in document order.

    Rebuilds the sequence and assigns clean positions with DEFAULT_POSITION_GAP.
    Useful to avoid float exhaustion after many insertions.

    Args:
        conn: SQLite connection.
        doc_id: Document ID.
    """
    sequence = build_longform_sequence(conn, doc_id)

    for idx, item in enumerate(sequence):
        new_position = (idx + 1) * DEFAULT_POSITION_GAP
        insert_or_update_longform_meta(
            conn,
            item["table"],
            item["id"],
            position=new_position,
            doc_id=doc_id,
        )

    logger.info(f"Reindexed {len(sequence)} items in document {doc_id}")


def promote_item(
    conn: Connection, table: str, row_id: str, doc_id: str = DOC_ID_DEFAULT
) -> None:
    """
    Promote an item (reduce depth, change parent to parent's parent).

    Equivalent to Shift+Tab in an outline editor.

    Args:
        conn: SQLite connection.
        table: Table name.
        row_id: Row ID to promote.
        doc_id: Document ID.
    """
    _validate_table_name(table)

    # Read current metadata
    # Security: table name validated above, row_id is parameterized
    cursor = conn.execute(f"SELECT attributes FROM {table} WHERE id = ?", (row_id,))
    row = cursor.fetchone()
    if not row:
        logger.warning(f"Cannot promote: row {row_id} not found in {table}")
        return

    attrs = _safe_json_loads(row["attributes"])
    meta = _get_longform_meta(attrs, doc_id)
    if not meta:
        logger.warning(f"Cannot promote: no longform metadata for {table}.{row_id}")
        return

    current_parent_id = meta.get("parent_id")
    current_depth = meta.get("depth", 0)

    if current_depth == 0:
        logger.info(f"Cannot promote: {table}.{row_id} is already at top level")
        return

    # Find parent's parent
    new_parent_id = None
    if current_parent_id:
        # Security: Iterating over hardcoded table list, IDs are parameterized
        for parent_table in VALID_TABLES:
            cursor = conn.execute(
                f"SELECT attributes FROM {parent_table} WHERE id = ?",
                (current_parent_id,),
            )
            parent_row = cursor.fetchone()
            if parent_row:
                parent_attrs = _safe_json_loads(parent_row["attributes"])
                parent_meta = _get_longform_meta(parent_attrs, doc_id)
                if parent_meta:
                    new_parent_id = parent_meta.get("parent_id")
                break

    # Update metadata
    new_depth = max(current_depth - 1, 0)
    insert_or_update_longform_meta(
        conn,
        table,
        row_id,
        parent_id=new_parent_id,
        depth=new_depth,
        doc_id=doc_id,
    )
    logger.debug(f"Promoted {table}.{row_id} from depth {current_depth} to {new_depth}")


def demote_item(
    conn: Connection, table: str, row_id: str, doc_id: str = DOC_ID_DEFAULT
) -> None:
    """
    Demote an item (increase depth, make it child of previous sibling).

    Equivalent to Tab in an outline editor.

    Args:
        conn: SQLite connection.
        table: Table name.
        row_id: Row ID to demote.
        doc_id: Document ID.
    """
    _validate_table_name(table)

    # Read current metadata
    # Security: table name validated above, row_id is parameterized
    cursor = conn.execute(f"SELECT attributes FROM {table} WHERE id = ?", (row_id,))
    row = cursor.fetchone()
    if not row:
        logger.warning(f"Cannot demote: row {row_id} not found in {table}")
        return

    attrs = _safe_json_loads(row["attributes"])
    meta = _get_longform_meta(attrs, doc_id)
    if not meta:
        logger.warning(f"Cannot demote: no longform metadata for {table}.{row_id}")
        return

    current_parent_id = meta.get("parent_id")
    current_position = meta.get("position", 0.0)

    # Find previous sibling (same parent, position < current)
    items = read_all_longform_items(conn, doc_id)
    siblings = [
        item
        for item in items
        if item["meta"].get("parent_id") == current_parent_id
        and item["meta"].get("position", 0.0) < current_position
    ]
    siblings.sort(key=lambda x: x["meta"].get("position", 0.0), reverse=True)

    if not siblings:
        logger.info(f"Cannot demote: no previous sibling for {table}.{row_id}")
        return

    # Previous sibling becomes new parent
    prev_sibling = siblings[0]
    new_parent_id = prev_sibling["id"]
    new_depth = prev_sibling["meta"].get("depth", 0) + 1

    insert_or_update_longform_meta(
        conn,
        table,
        row_id,
        parent_id=new_parent_id,
        depth=new_depth,
        doc_id=doc_id,
    )
    logger.debug(f"Demoted {table}.{row_id} to be child of {new_parent_id}")


def remove_from_longform(
    conn: Connection, table: str, row_id: str, doc_id: str = DOC_ID_DEFAULT
) -> None:
    """
    Remove longform metadata from a row.

    The row remains in the database but is no longer part of the longform document.

    Args:
        conn: SQLite connection.
        table: Table name.
        row_id: Row ID.
        doc_id: Document ID.
    """
    _validate_table_name(table)

    # Security: table name validated above, row_id is parameterized
    cursor = conn.execute(f"SELECT attributes FROM {table} WHERE id = ?", (row_id,))
    row = cursor.fetchone()
    if not row:
        logger.warning(f"Cannot remove: row {row_id} not found in {table}")
        return

    attrs = _safe_json_loads(row["attributes"])
    if "longform" in attrs and doc_id in attrs["longform"]:
        del attrs["longform"][doc_id]
        # Clean up empty longform dict
        if not attrs["longform"]:
            del attrs["longform"]

    # Security: table name validated above, values are parameterized
    conn.execute(
        f"UPDATE {table} SET attributes = ? WHERE id = ?",
        (json.dumps(attrs), row_id),
    )
    conn.commit()
    logger.debug(f"Removed longform metadata from {table}.{row_id}")


def export_longform_to_markdown(conn: Connection, doc_id: str = DOC_ID_DEFAULT) -> str:
    """
    Export the longform document to Markdown format.

    Includes HTML comments with ID markers for traceability.

    Args:
        conn: SQLite connection.
        doc_id: Document ID.

    Returns:
        str: Markdown-formatted document.
    """
    sequence = build_longform_sequence(conn, doc_id)

    lines = []
    lines.append(f"# Longform Document: {doc_id}\n")

    for item in sequence:
        # Add ID marker comment
        lines.append(
            f"<!-- PK-LONGFORM id={item['id']} table={item['table']} doc={doc_id} -->\n"
        )

        # Add heading
        heading_level = item["heading_level"]
        title = item["meta"].get("title_override") or item["name"]
        heading = "#" * heading_level + " " + title
        lines.append(heading + "\n")

        # Add content
        content = item.get("content", "").strip()
        if content:
            lines.append("\n" + content + "\n")

        lines.append("\n")

    return "".join(lines)
