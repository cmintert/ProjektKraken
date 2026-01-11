"""
Search Utility Module.

Provides shared search logic for filtering domain objects (Entities, Events)
based on text matching against various properties.
"""

from typing import Any


class SearchUtils:
    """Helper class for text-based object searching."""

    @staticmethod
    def matches_search(obj: Any, search_term: str) -> bool:
        """
        Checks if an object or dictionary matches the search term.
        Performs full text search on name, type, description, tags, and attributes.

        Args:
            obj: The object to check (Entity, Event, or dict).
            search_term: The text to search for.

        Returns:
            bool: True if the object matches the search term (or term is empty).
        """
        if not search_term:
            return True

        term = search_term.lower().strip()
        if not term:
            return True

        # Helper to get value from obj or dict
        def get_val(key: str) -> Any:
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)

        # 1. Name
        name = get_val("name")
        if name and term in name.lower():
            return True

        # 2. Type
        obj_type = get_val("type")
        if obj_type and term in obj_type.lower():
            return True

        # 3. Description
        description = get_val("description")
        if description and term in description.lower():
            return True

        # 4. Tags
        tags = get_val("tags")
        if tags:
            for tag in tags:
                if term in tag.lower():
                    return True

        # 5. String Attributes
        attributes = get_val("attributes")
        if attributes:
            # Handle dict attributes
            if isinstance(attributes, dict):
                for value in attributes.values():
                    if isinstance(value, str) and term in value.lower():
                        return True

        return False
