"""
Link Resolver Service.

Handles resolution of ID-based wiki links to current entity/event names.
Provides caching and broken link detection.
"""

import logging
from typing import Dict, List, Optional, Tuple

from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


class LinkResolver:
    """
    Resolves wiki link IDs to current entity/event names.

    Maintains a cache for performance and provides broken link detection.
    """

    def __init__(self, db_service: DatabaseService) -> None:
        """
        Initializes the LinkResolver.

        Args:
            db_service: Database service for looking up entities/events.
        """
        self.db_service = db_service
        self._cache: Dict[str, Tuple[str, str]] = {}  # id -> (name, type)

    def resolve(self, target_id: str) -> Optional[Tuple[str, str]]:
        """
        Resolves a target ID to its current name and type.

        Args:
            target_id: The UUID of the target entity or event.

        Returns:
            Optional[Tuple[str, str]]: (name, type) if found, None if broken.
        """
        # Check cache first
        if target_id in self._cache:
            return self._cache[target_id]

        # Try to find as entity
        entity = self.db_service.get_entity(target_id)
        if entity:
            result = (entity.name, "entity")
            self._cache[target_id] = result
            return result

        # Try to find as event
        event = self.db_service.get_event(target_id)
        if event:
            result = (event.name, "event")
            self._cache[target_id] = result
            return result

        # Not found - broken link
        logger.warning(f"Broken link detected: ID {target_id} not found")
        return None

    def invalidate_cache(self, target_id: Optional[str] = None) -> None:
        """
        Invalidates the resolution cache.

        Args:
            target_id: If provided, invalidates only this ID.
                       If None, clears entire cache.
        """
        if target_id:
            self._cache.pop(target_id, None)
        else:
            self._cache.clear()

    def get_display_name(
        self, target_id: str, fallback_name: Optional[str] = None
    ) -> str:
        """
        Gets the display name for a link, with fallback for broken links.

        Args:
            target_id: The UUID of the target.
            fallback_name: Name to display if link is broken.

        Returns:
            str: The current name, or fallback with warning indicator.
        """
        result = self.resolve(target_id)
        if result:
            return result[0]  # Return current name

        # Broken link - use fallback or show ID
        if fallback_name:
            return f"{fallback_name} [BROKEN]"
        return f"[BROKEN LINK: {target_id[:8]}...]"

    def find_broken_links(self, text: str) -> List[str]:
        """
        Finds all broken links in the given text.

        Args:
            text: Text content to scan for broken links.

        Returns:
            list[str]: List of broken link IDs.
        """
        from src.services.text_parser import WikiLinkParser

        candidates = WikiLinkParser.extract_links(text)
        broken = []

        for candidate in candidates:
            if candidate.is_id_based and candidate.target_id:
                if self.resolve(candidate.target_id) is None:
                    broken.append(candidate.target_id)

        return broken
