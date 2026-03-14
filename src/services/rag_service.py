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

        # Fill with semantic results, filtering by similarity threshold
        for item in semantic:
            # Skip low-score results to reduce context noise
            score = item.get("score", 0.0)
            if score < self.min_score:
                logger.debug(
                    f"RAG: Filtering low-score result "
                    f"'{item.get('name', '?')}' (score={score:.3f} "
                    f"< threshold={self.min_score})"
                )
                continue

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
        """Format results into compact text for the LLM.

        Uses a token-efficient format: one entry per block with minimal
        markup. Descriptions are truncated to keep context windows lean.
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
                    elif len(line) < 100:
                        attributes_parts.append(line)

            # Compact single-line header
            parts: List[str] = [f"{name} ({rtype})"]
            if tags_line:
                parts.append(f"[{tags_line}]")
            if attributes_parts:
                parts.append(" | ".join(attributes_parts))
            header = " — ".join(parts)

            if description:
                if len(description) > 300:
                    description = description[:297] + "..."
                context_parts.append(f"{header}\n{description}")
            else:
                context_parts.append(header)

        return "\n\n".join(context_parts)
