"""
Regression test for Graph Lexicon Resolution.
Verifies that both project icons and default bundled icons are resolved correctly.
"""

import os
from pathlib import Path
from src.gui.widgets.graph_view.graph_builder import GraphBuilder
from src.app.constants import DEFAULT_MARKER_ICONS_PATH
from src.core.paths import get_resource_path


def test_resolve_lexicon_images_finds_default_icons(tmp_path):
    """
    Test that default icons are resolved correctly even if not in project root.
    """
    # 1. Setup a dummy world root
    project_root = tmp_path / "world"
    project_root.mkdir()

    # 2. Setup a lexicon with a default icon filename
    # 'building-castle.svg' is known to exist in default_assets/icons/markers
    lexicon = {"nodes": {"Person": {"icon": "building-castle.svg", "shape": "image"}}}

    # 3. Call resolution
    resolved = GraphBuilder.resolve_lexicon_images(lexicon, project_root)

    # 4. Verify
    person_style = resolved["nodes"]["Person"]
    assert "image" in person_style, "Image data URI should be present"
    assert person_style["image"].startswith(
        "data:image/svg+xml;base64,"
    ), "Should be a proper SVG data URI"


def test_resolve_lexicon_images_finds_project_icons(tmp_path):
    """
    Test that icons in the project root are resolved correctly.
    """
    # 1. Setup a world root and a custom icon
    project_root = tmp_path / "world"
    project_root.mkdir()

    assets_dir = project_root / "assets" / "images"
    assets_dir.mkdir(parents=True)

    icon_rel_path = "assets/images/custom_icon.svg"
    icon_full_path = project_root / icon_rel_path
    icon_full_path.write_text("<svg>Custom</svg>")

    # 2. Setup lexicon
    lexicon = {"nodes": {"Person": {"icon": icon_rel_path, "shape": "image"}}}

    # 3. Call resolution
    resolved = GraphBuilder.resolve_lexicon_images(lexicon, project_root)

    # 4. Verify
    person_style = resolved["nodes"]["Person"]
    assert "image" in person_style
    assert person_style["image"].startswith("data:image/svg+xml;base64,")
