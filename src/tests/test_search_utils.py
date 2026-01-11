from typing import Any, Optional

from src.core.search_utils import SearchUtils


class MockEntity:
    """Mock Entity class for testing."""

    def __init__(
        self,
        name: str,
        type_: str,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize mock entity."""
        self.name = name
        self.type = type_
        self.description = description
        self.tags = tags or []
        self.attributes = attributes or {}


def test_search_dict_name_match() -> None:
    """Test search matches on name field in dict."""
    item = {"name": "Graph Node", "type": "entity"}
    assert SearchUtils.matches_search(item, "Graph")
    assert SearchUtils.matches_search(item, "node")
    assert not SearchUtils.matches_search(item, "missing")


def test_search_dict_tags_match() -> None:
    """Test search matches on tags field in dict."""
    item = {"name": "Hero", "tags": ["protagonist", "brave"]}
    assert SearchUtils.matches_search(item, "protag")
    assert SearchUtils.matches_search(item, "brave")


def test_search_object_compatibility() -> None:
    """Ensure objects still work with SearchUtils."""
    obj = MockEntity(name="Ancient Relic", type_="item", tags=["magic"])
    assert SearchUtils.matches_search(obj, "Relic")
    assert SearchUtils.matches_search(obj, "magic")


def test_search_dict_attributes() -> None:
    """Test search matches on attributes field in dict."""
    item = {"name": "Test", "attributes": {"color": "red", "size": "large"}}
    assert SearchUtils.matches_search(item, "red")
    assert SearchUtils.matches_search(item, "large")


def test_search_empty() -> None:
    """Test empty search returns True."""
    item = {"name": "Something"}
    assert SearchUtils.matches_search(item, "")
    assert SearchUtils.matches_search(item, None)
