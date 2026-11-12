"""Published Longform adapter for the shared Kraken Markdown profile."""

from src.core.markdown_content import RenderTarget, parse_content, render_content
from src.core.markdown_html import allow_attribute as _allow_attribute
from src.core.markdown_html import is_safe_url as _is_safe_url

__all__ = ["render_longform_markdown", "_allow_attribute", "_is_safe_url"]


def render_longform_markdown(source: str) -> str:
    """Render local source with publication URL and generated-link protections."""
    return render_content(parse_content(source), RenderTarget.PUBLISHED)
