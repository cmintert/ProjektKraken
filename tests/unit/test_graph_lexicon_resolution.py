"""
Regression test for stable-ID Graph Lexicon resolution.
"""

from src.gui.widgets.graph_view.graph_builder import GraphBuilder


def test_resolve_lexicon_images_finds_default_icons(tmp_path):
    """
    Test that default icons are resolved correctly even if not in project root.
    """
    # 1. Setup a dummy world root
    project_root = tmp_path / "world"
    project_root.mkdir()

    # 2. Setup a lexicon with a bundled stable icon ID
    lexicon = {
        "nodes": {"Person": {"icon_id": "place.castle", "shape": "image"}}
    }

    # 3. Call resolution
    resolved = GraphBuilder.resolve_lexicon_images(lexicon, project_root)

    # 4. Verify
    person_style = resolved["nodes"]["Person"]
    assert "image" in person_style, "Image data URI should be present"
    assert person_style["image"].startswith("data:image/svg+xml;base64,"), (
        "Should be a proper SVG data URI"
    )


def test_resolve_lexicon_images_finds_project_icons(tmp_path):
    """
    Test that icons in the project root are resolved correctly.
    """
    # 1. Setup a world root and a custom icon
    project_root = tmp_path / "world"
    project_root.mkdir()

    assets_dir = project_root / "assets" / "images"
    assets_dir.mkdir(parents=True)

    uuid_hex = "0123456789abcdef0123456789abcdef"
    icon_rel_path = f"assets/images/icon_{uuid_hex}.svg"
    icon_full_path = project_root / icon_rel_path
    icon_full_path.write_text("<svg>Custom</svg>")

    # 2. Setup lexicon
    lexicon = {
        "nodes": {
            "Person": {"icon_id": f"custom.{uuid_hex}", "shape": "image"}
        }
    }

    # 3. Call resolution
    resolved = GraphBuilder.resolve_lexicon_images(lexicon, project_root)

    # 4. Verify
    person_style = resolved["nodes"]["Person"]
    assert "image" in person_style
    assert person_style["image"].startswith("data:image/svg+xml;base64,")
