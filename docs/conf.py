# Configuration file for the Sphinx documentation builder.
import os
import sys
import tomllib
from typing import Any

sys.path.insert(0, os.path.abspath(".."))
sys.path.insert(0, os.path.abspath("../src"))

with open("../pyproject.toml", "rb") as f:
    pyproject = tomllib.load(f)

project = "Project Kraken"
copyright = pyproject["project"].get("copyright", "2025, Christian Mintert")
author = ", ".join([a["name"] for a in pyproject["project"].get("authors", [])])
release = pyproject["project"]["version"]
version = release


# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",  # Support for Google Style Docstrings
    "sphinx.ext.viewcode",
    "sphinx.ext.githubpages",
    "myst_parser",  # Support for Markdown files
    "sphinxcontrib.mermaid",  # Support for Mermaid diagrams
]

# Markdown support
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for Napoleon ----------------------------------------------------
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# -- Options for HTML output -------------------------------------------------
html_theme = "furo"
html_static_path = ["_static"]

# Furo theme options
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


# -- Auto-generate schema documentation --------------------------------------
def setup(app: Any) -> None:
    """
    Sphinx setup hook to auto-generate schema documentation.

    Runs the schema extraction script before building the documentation
    to ensure the schema reference is always up-to-date with the code.
    """
    import subprocess
    from pathlib import Path

    schema_script = Path(__file__).parent / "generate_schema_docs.py"
    if schema_script.exists():
        print("Generating database schema documentation...")
        result = subprocess.run(
            [sys.executable, str(schema_script)], capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Warning: Schema generation failed: {result.stderr}")
        else:
            print(result.stdout)
