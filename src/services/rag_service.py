"""RAG Service Module.

Handles retrieval augmented generation logic, including:
- Query cleaning and intent extraction
- Hybrid search (Lexical + Semantic) via SearchService
- Context formatting for LLM consumption
"""

import logging
import re
import sqlite3
from contextlib import closing
from typing import Any, Dict, List, Optional

from src.services.search_service import create_search_service

logger = logging.getLogger(__name__)

_MAX_CLEAN_QUERY_CHARS = 300
_MAX_ATTRIBUTE_LINE_CHARS = 100
_MAX_DESCRIPTION_CHARS = 300
_ELLIPSIS_CHARS = 3


def retrieval_exclusion_kwargs(
    object_type: Optional[str], object_id: Optional[str], exclude_names: List[str]
) -> Dict[str, Any]:
    """Prefer exact subject identity, falling back to legacy name exclusions."""
    if object_type in {"entity", "event"} and object_id:
        return {"exclude_object": (object_type, object_id)}
    return {"exclude_names": list(exclude_names)}


class RAGService:
    """Service for retrieving and formatting world knowledge for LLM context."""

    # Minimum similarity score for semantic results. Results below this
    # threshold are considered noise and are filtered out to prevent
    # irrelevant context from being injected into the prompt.
    DEFAULT_MIN_SCORE: float = 0.25

    def __init__(self, db_path: str, min_score: Optional[float] = None) -> None:
        """Initialize RAG Service.

        Args:
            db_path: Path to the SQLite database.
            min_score: Minimum similarity score for semantic results
                (0.0–1.0). Results below this threshold are discarded.
                Defaults to DEFAULT_MIN_SCORE.

        """
        self.db_path = db_path
        self.min_score = min_score if min_score is not None else self.DEFAULT_MIN_SCORE

    def search(
        self, query: str, top_k: int = 3, object_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search and return structured results.

        Args:
            query: Raw user query.
            top_k: Maximum additional semantic results after direct mentions.
            object_type: Optional filter ('entity' or 'event').

        Returns:
            List of result dicts with keys: id, name, type, score, text_content, etc.

        """
        if not self.db_path:
            return []

        try:
            # Connect strictly for reading
            with closing(
                sqlite3.connect(self.db_path, check_same_thread=False)
            ) as conn:
                conn.row_factory = sqlite3.Row
                search_service = create_search_service(conn)
                cleaned_query = self._clean_query(query)
                logger.debug(
                    "RAG search query_chars=%d cleaned_chars=%d object_type=%s",
                    len(query),
                    len(cleaned_query),
                    object_type or "all",
                )
                lexical_results = (
                    search_service.search_by_name(query, object_type=object_type)
                    if hasattr(search_service, "search_by_name")
                    else []
                )
                # Request enough semantic candidates to replace any that overlap
                # direct mentions; the merged budget still adds at most top_k.
                semantic_results = search_service.query(
                    cleaned_query,
                    top_k=max(0, top_k) + len(lexical_results),
                    object_type=object_type,
                )
                merged = self._merge_results(
                    lexical_results,
                    semantic_results,
                    top_k,
                )
                logger.debug(
                    "RAG search lexical_hits=%d semantic_hits=%d merged_hits=%d",
                    len(lexical_results),
                    len(semantic_results),
                    len(merged),
                )
                return merged

        except Exception as error:
            logger.error("RAG search failed error_type=%s", type(error).__name__)
            return []

    # Maximum number of relations to include per entity in RAG context.
    _MAX_RELATIONS_PER_ENTITY: int = 5

    def get_context(
        self,
        prompt: str,
        top_k: int = 3,
        exclude_names: Optional[List[str]] = None,
        exclude_object: Optional[tuple[str, str]] = None,
    ) -> str:
        """Retrieve and format context based on the user prompt.

        Performs:
        1. Query cleaning (stripping inputs)
        2. Hybrid search (Name match + Semantic match)
        3. Relation enrichment (directed SPO triples per result entity)
        4. Result formatting (with attributes, tags, and relations)

        Args:
            prompt: User's raw prompt/task.
            top_k: Maximum additional semantic results after direct mentions.
            exclude_names: Optional list of names to exclude from results (e.g., current entity).
            exclude_object: Exact world object type and ID to exclude.

        Returns:
            str: Formatted context block for the LLM.

        """
        results = self.search(prompt, top_k=top_k)

        if exclude_object:
            results = [
                r
                for r in results
                if (r.get("object_type"), r.get("object_id")) != exclude_object
            ]

        # Filter exclusions
        if exclude_names:
            # Case-insensitive filtering
            lower_excludes = {n.lower() for n in exclude_names if n}
            results = [
                r for r in results if r.get("name", "").lower() not in lower_excludes
            ]

        if not results:
            return ""

        # Enrich each result with directed relation lines fetched from the DB.
        relation_map = self._fetch_relations_for_results(results)

        return self._format_results(results, relation_map=relation_map)

    def _fetch_relations_for_results(
        self, results: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """Fetch directed relation lines for each result entity.

        Opens a short-lived read connection to the DB, queries the ``relations``
        table for each result whose ``object_id`` (or ``id``) looks like an
        entity record, and returns a mapping of entity-id → list of SPO-formatted
        relation strings.

        Args:
            results: Search result dicts as returned by :meth:`search`.

        Returns:
            Dict mapping entity id → list of SPO relation strings (may be empty
            for events or entities with no relations).

        """
        if not self.db_path:
            return {}

        relation_map: Dict[str, List[str]] = {}
        try:
            with closing(
                sqlite3.connect(self.db_path, check_same_thread=False)
            ) as conn:
                conn.row_factory = sqlite3.Row
                for r in results:
                    if r.get("object_type") != "entity":
                        continue
                    entity_id = r.get("object_id", "")
                    entity_name = r.get("name", entity_id)
                    if not entity_id:
                        continue
                    relation_map[entity_id] = self._spo_lines_for_entity(
                        conn, entity_id, entity_name
                    )
        except Exception as e:
            logger.warning(f"RAG: failed to fetch entity relations: {e}")
        return relation_map

    def _spo_lines_for_entity(
        self, conn: sqlite3.Connection, entity_id: str, entity_name: str
    ) -> List[str]:
        """Return up to _MAX_RELATIONS_PER_ENTITY SPO-formatted relation strings.

        Queries both outgoing (source_id=entity_id) and incoming
        (target_id=entity_id) relations, joining with the entities table to
        resolve names.

        Args:
            conn: Open SQLite connection.
            entity_id: UUID of the entity whose relations to fetch.
            entity_name: Display name of the entity (used in SPO triples).

        Returns:
            List of strings like ``"EntityA --rel_type--> EntityB"``.

        """
        query = """
            SELECT
                r.source_id,
                COALESCE(s.name, r.source_id) AS source_name,
                r.rel_type,
                r.target_id,
                COALESCE(t.name, r.target_id) AS target_name
            FROM relations r
            LEFT JOIN entities s ON r.source_id = s.id
            LEFT JOIN entities t ON r.target_id = t.id
            WHERE r.source_id = ? OR r.target_id = ?
            LIMIT ?
        """
        try:
            rows = conn.execute(
                query, (entity_id, entity_id, self._MAX_RELATIONS_PER_ENTITY)
            ).fetchall()
        except Exception as e:
            logger.debug(f"RAG: relation query failed for {entity_id}: {e}")
            return []

        lines = []
        for row in rows:
            src = row["source_name"] if row["source_id"] != entity_id else entity_name
            tgt = row["target_name"] if row["target_id"] != entity_id else entity_name
            lines.append(f"{src} --{row['rel_type']}--> {tgt}")
        return lines

    def _clean_query(self, prompt: str) -> str:
        """Remove instructional noise from prompt to improve semantic search."""
        # Common prefixes/instructions
        patterns = [
            r"^Task:\s*",
            r"^Write\s+(a|an|the)?\s*",
            r"^Describe\s+(a|an|the)?\s*",
            r"^Tell\s+me\s+about\s*",
            r"^Generate\s*",
            r"^Create\s*",
        ]

        cleaned = prompt.strip()
        for p in patterns:
            cleaned = re.sub(p, "", cleaned, flags=re.IGNORECASE).strip()

        # If we stripped everything (unlikely), revert
        if not cleaned:
            return prompt

        # Truncate to reasonable length for embedding (focus on subject)
        return cleaned[:_MAX_CLEAN_QUERY_CHARS]

    def _merge_results(
        self,
        lexical: List[Dict[str, Any]],
        semantic: List[Dict[str, Any]],
        target_k: int,
    ) -> List[Dict[str, Any]]:
        """Keep all unique direct mentions, then up to ``target_k`` semantic hits.

        Source order is stable within each group. Embedding-row IDs are never
        used as world object identity.
        """
        seen_objects: set[tuple[str, str]] = set()
        merged: List[Dict[str, Any]] = []

        for item in lexical:
            object_type = item.get("object_type")
            object_id = item.get("object_id")
            if not isinstance(object_type, str) or not object_type:
                continue
            if not isinstance(object_id, str) or not object_id:
                continue
            key = (object_type, object_id)
            if key in seen_objects:
                continue
            merged.append({**item, "_match_type": "Direct Mention"})
            seen_objects.add(key)

        semantic_added = 0
        for item in semantic:
            if item.get("score", 0.0) < self.min_score:
                continue
            object_type = item.get("object_type")
            object_id = item.get("object_id")
            if not isinstance(object_type, str) or not object_type:
                continue
            if not isinstance(object_id, str) or not object_id:
                continue
            key = (object_type, object_id)
            if key in seen_objects:
                continue
            if semantic_added >= max(0, target_k):
                break
            merged.append({**item, "_match_type": "Semantic"})
            seen_objects.add(key)
            semantic_added += 1

        return merged

    def _format_results(
        self,
        results: List[Dict[str, Any]],
        relation_map: Optional[Dict[str, List[str]]] = None,
    ) -> str:
        """Format results into compact text for the LLM.

        Uses a token-efficient format: one entry per block with minimal
        markup. Descriptions are truncated to keep context windows lean.
        When *relation_map* is provided, directed SPO relation lines are
        appended after the description block.

        Args:
            results: Search result dicts as returned by :meth:`search`.
            relation_map: Optional mapping of entity-id → list of SPO relation
                strings, as produced by :meth:`_fetch_relations_for_results`.

        Returns:
            str: Formatted context block for the LLM.

        """
        context_parts: List[str] = []

        for r in results:
            name = r.get("name", "Unknown")
            rtype = r.get("type", "Unknown")

            text_content = r.get("text_content", "")

            description = ""
            attributes_parts: List[str] = []
            tags_line = ""

            if text_content:
                for line in text_content.split("\n\n"):
                    if line.startswith("Description: "):
                        description = line[len("Description: ") :].strip()
                    elif line.startswith("Tags: "):
                        tags_line = line[len("Tags: ") :].strip()
                    elif line.startswith(("Name:", "Type:", "Date:", "Duration:")):
                        continue
                    elif len(line) < _MAX_ATTRIBUTE_LINE_CHARS:
                        attributes_parts.append(line)

            # Compact single-line header
            parts: List[str] = [f"{name} ({rtype})"]
            if tags_line:
                parts.append(f"[{tags_line}]")
            if attributes_parts:
                parts.append(" | ".join(attributes_parts))
            header = " — ".join(parts)

            entry_lines: List[str] = [header]
            if description:
                if len(description) > _MAX_DESCRIPTION_CHARS:
                    description = (
                        description[: _MAX_DESCRIPTION_CHARS - _ELLIPSIS_CHARS] + "..."
                    )
                entry_lines.append(description)

            # Append SPO relation lines if available for this entity.
            if relation_map:
                entity_id = r.get("object_id", "")
                rel_lines = relation_map.get(entity_id, [])
                if rel_lines:
                    entry_lines.append(
                        "Relations (A --rel--> B means A [rel] B):\n"
                        + "\n".join(f"  {ln}" for ln in rel_lines)
                    )

            context_parts.append("\n".join(entry_lines))

        return "\n\n".join(context_parts)
