"""RAG Service Module.

Handles retrieval augmented generation logic, including:
- Query cleaning and intent extraction
- Hybrid search (Lexical + Semantic) via SearchService
- Context formatting for LLM consumption
"""

import logging
import re
import sqlite3
from typing import Any, Dict, List, Optional

from src.services.search_service import create_search_service

logger = logging.getLogger(__name__)


class RAGService:
    """Service for retrieving and formatting world knowledge for LLM context."""

    def __init__(self, db_path: str) -> None:
        """Initialize RAG Service.

        Args:
            db_path: Path to the SQLite database.

        """
        self.db_path = db_path

    def search(
        self, query: str, top_k: int = 3, object_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search and return structured results.

        Args:
            query: Raw user query.
            top_k: Number of semantic results to retrieve.
            object_type: Optional filter ('entity' or 'event').

        Returns:
            List of result dicts with keys: id, name, type, score, text_content, etc.

        """
        if not self.db_path:
            return []

        try:
            # Connect strictly for reading
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row

            search_service = create_search_service(conn)

            # 1. Clean Query
            cleaned_query = self._clean_query(query)
            logger.debug(
                f"Original Prompt: {query[:50]}... -> Cleaned: {cleaned_query}"
            )

            # 2. Hybrid Search
            # A. Semantic Search
            # We use the cleaned query for better semantic/topical matching
            semantic_results = search_service.query(
                cleaned_query, top_k=top_k, object_type=object_type
            )

            # B. Lexical Search (Name Matching)
            # Only perform if looking for Entities or All (Events usually less name-centric but possible)
            lexical_results = []
            if hasattr(search_service, "search_by_name"):
                # Use raw prompt/query to find names mentioned
                lexical_results = search_service.search_by_name(
                    query, object_type=object_type
                )

            # 3. Merge Results
            final_results = self._merge_results(
                lexical_results, semantic_results, top_k
            )

            conn.close()
            return final_results

        except Exception as e:
            logger.error(f"RAG search failed: {e}", exc_info=True)
            return []

    def get_context(
        self, prompt: str, top_k: int = 3, exclude_names: Optional[List[str]] = None
    ) -> str:
        """Retrieve and format context based on the user prompt.

        Performs:
        1. Query cleaning (stripping inputs)
        2. Hybrid search (Name match + Semantic match)
        3. Result formatting (with attributes and tags)

        Args:
            prompt: User's raw prompt/task.
            top_k: Number of semantic results to retrieve (min).
            exclude_names: Optional list of names to exclude from results (e.g., current entity).

        Returns:
            str: Formatted context block for the LLM.

        """
        results = self.search(prompt, top_k=top_k)

        # Filter exclusions
        if exclude_names:
            # Case-insensitive filtering
            lower_excludes = {n.lower() for n in exclude_names if n}
            results = [
                r for r in results if r.get("name", "").lower() not in lower_excludes
            ]

        if not results:
            return ""

        # 4. Format
        return self._format_results(results)

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
        return cleaned[:300]

    def _merge_results(
        self,
        lexical: List[Dict[str, Any]],
        semantic: List[Dict[str, Any]],
        target_k: int,
    ) -> List[Dict[str, Any]]:
        """Merge lexical and semantic results, prioritizing lexical."""
        seen_ids = set()
        merged = []

        # Prioritize exact name matches
        for item in lexical:
            if item["id"] not in seen_ids:
                item["_match_type"] = "Direct Mention"
                merged.append(item)
                seen_ids.add(item["id"])

        # Fill with semantic results
        for item in semantic:
            # handle differences in structure if any (search_service.query returns specific dicts)
            # assuming object_id or id is the key.
            # search_service.query uses 'object_id' for UUID, 'id' for embedding UUID (usually)
            # Wait, search_service.query returns: id (embedding), object_id (entity/event uuid)
            # Let's use object_id as uniqueness key
            unique_key = item.get("object_id")
            if unique_key and unique_key not in seen_ids:
                item["_match_type"] = "Semantic"
                merged.append(item)
                seen_ids.add(unique_key)

            if len(merged) >= target_k + len(
                lexical
            ):  # Allow some overflow for lexical
                break

        return merged

    def _format_results(self, results: List[Dict[str, Any]]) -> str:
        """Format results into Markdown for the LLM."""
        context_parts = ["### World Knowledge (RAG Data):"]

        for r in results:
            name = r.get("name", "Unknown")
            rtype = r.get("type", "Unknown")
            match_type = r.get("_match_type", "Semantic")

            # Metadata/Attributes
            # r.get("metadata", {})  # Unused
            # We want to show attributes if available
            # The search_service.query returns 'metadata' dict, but attributes might be buried or on disk?
            # Current `query` implementation retrieves 'metadata' column which is json dumped.
            # Does 'metadata' contain attributes?
            # In index_entity/event: metadata = {"name": ..., "type": ...}
            # It does NOT contain all attributes.
            # To get attributes, we might need the TEXT SNIPPET which contains key: value pairs.
            # OR we fetch from DB. Fetching from DB is cleaner but heavier.
            # Accessing text_content (snippet) is easier.

            text_content = r.get("text_content", "")

            # Simple parser to get relevant lines from text snippet
            # Snippet format: Name: X\nType: Y\n[Tags: ...]\n[Description: ...]\nKey: Value...

            description = ""
            attributes_lines = []
            tags_line = ""

            if text_content:
                lines = text_content.split("\n\n")  # Snippets use double newline join?
                # Check build_text_for_entity: "\n\n".join(parts)
                # Yes.
                for line in lines:
                    if line.startswith("Description: "):
                        description = line.replace("Description: ", "").strip()
                    elif line.startswith("Tags: "):
                        tags_line = line.replace("Tags: ", "").strip()
                    elif (
                        line.startswith("Name:")
                        or line.startswith("Type:")
                        or line.startswith("Date:")
                        or line.startswith("Duration:")
                    ):
                        continue  # Already have these or don't need repetition
                    else:
                        # Likely an attribute
                        # Limit length of attributes?
                        if len(line) < 100:
                            attributes_lines.append(line)

            # Assemble block
            # **Name** (Type) [Direct Mention?]
            header = f"**{name}** ({rtype})"
            if match_type == "Direct Mention":
                header += " *(Direct Mention)*"

            block = [header]

            if tags_line:
                block.append(f"Tags: {tags_line}")

            if attributes_lines:
                # Format attributes compactly? "Status: Alive | Location: Jail"
                # Or list. Let's try pipe separator for compactness
                block.append("Attributes: " + " | ".join(attributes_lines))

            if description:
                # Truncate overly long descriptions
                if len(description) > 500:
                    description = description[:497] + "..."
                block.append(f"Description: {description}")

            context_parts.append("\n".join(block))

        return "\n\n".join(context_parts) + "\n\n"
