"""Sphinx configuration for the canonical ProjektKraken documentation."""

import tomllib
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as pyproject_file:
    pyproject = tomllib.load(pyproject_file)

project = "ProjektKraken"
author = ", ".join(
    entry["name"] for entry in pyproject["project"].get("authors", [])
)
release = pyproject["project"]["version"]
version = release
copyright = pyproject["project"].get("copyright", "2026, Christian Mintert")

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinxcontrib.mermaid",
]

root_doc = "index"
source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}

# Generated research is being removed separately and is deliberately never
# part of the published manual.
exclude_patterns = [
    "_build",
    "Gemini/**",
    "Thumbs.db",
    ".DS_Store",
]

myst_heading_anchors = 4
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
]

autosummary_generate = True
autodoc_typehints = "description"

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False

html_theme = "furo"
html_title = f"{project} {release}"
html_logo = "_static/kraken.webp"
html_static_path = ["_static"]
html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#7C3AED",
        "color-brand-content": "#7C3AED",
    },
    "dark_css_variables": {
        "color-brand-primary": "#A78BFA",
        "color-brand-content": "#A78BFA",
    },
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
}
