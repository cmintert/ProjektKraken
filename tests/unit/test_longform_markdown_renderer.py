"""Regression tests for safe longform Markdown rendering."""

import pytest

from src.webserver.markdown_renderer import (
    _allow_attribute,
    _is_safe_url,
    render_longform_markdown,
)


@pytest.mark.parametrize(
    "payload",
    [
        '<script>globalThis.__krakenXss = true</script><p>after</p>',
        '<img src="https://attacker.invalid/x" onerror="alert(1)">after',
        '<iframe srcdoc="<script>alert(1)</script>"></iframe>',
        '<object data="https://attacker.invalid/x"></object>',
        '<svg><script>alert(1)</script><a onload="alert(2)"></a></svg>',
        '<a href="javascript:alert(1)" onclick="alert(2)">hostile</a>',
        '<div><svg><script>alert(1)</script></svg><p title="broken',
        '<!--<img src=x onerror=alert(1)>--><script>broken',
    ],
)
def test_author_html_is_removed_before_rendering(payload: str) -> None:
    rendered = render_longform_markdown(payload)
    lowered = rendered.lower()

    for forbidden in (
        "<script",
        "<img",
        "<iframe",
        "<object",
        "<svg",
        "onerror",
        "onclick",
        "onload",
        "javascript:",
        "srcdoc",
    ):
        assert forbidden not in lowered


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        " javaScript:alert(1)",
        "java\tscript:alert(1)",
        "java&#x09;script:alert(1)",
        "java&#115;cript:alert(1)",
        "java%73cript%3Aalert(1)",
        "java%2573cript%253Aalert(1)",
        "javascript\\:alert(1)",
        "//attacker.invalid/path",
        "https:\\attacker.invalid/path",
        "https://user:password@example.com/path",
        "https://example.com:bad/path",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "/relative/path",
        "relative/path",
        "#",
        "",
    ],
)
def test_dangerous_or_malformed_urls_are_rejected(url: str) -> None:
    assert _is_safe_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/path?q=value#fragment",
        "http://localhost:8000/path",
        "mailto:reader@example.com",
        "#section-2",
    ],
)
def test_supported_urls_are_accepted(url: str) -> None:
    assert _is_safe_url(url) is True


def test_element_attributes_are_explicitly_scoped() -> None:
    assert _allow_attribute("a", "href", "https://example.com") is True
    assert _allow_attribute("a", "data-target", "Chapter") is True
    assert _allow_attribute("a", "data-arbitrary", "value") is False
    assert _allow_attribute("p", "data-target", "Chapter") is False
    assert _allow_attribute("a", "class", "wikilink") is True
    assert _allow_attribute("a", "class", "attacker-class") is False
    assert _allow_attribute("a", "target", "_blank") is False
    assert _allow_attribute("code", "class", "language-python") is True
    assert _allow_attribute("code", "class", "language-python evil") is False


def test_normal_markdown_and_wiki_links_survive() -> None:
    source = """# Heading

**Bold** and *italic* with [[Target|Wiki label]].

- One
- Two

| A | B |
| - | - |
| 1 | 2 |

```python
print("safe")
```

[Web](https://example.com) and [mail](mailto:reader@example.com).
"""

    rendered = render_longform_markdown(source)

    assert "<h1>Heading</h1>" in rendered
    assert "<strong>Bold</strong>" in rendered
    assert "<em>italic</em>" in rendered
    assert '<a class="wikilink" data-target="Target">Wiki label</a>' in rendered
    assert "<ul>" in rendered
    assert "<table>" in rendered
    assert '<code class="language-python">' in rendered
    assert '<a href="https://example.com">Web</a>' in rendered
    assert '<a href="mailto:reader@example.com">mail</a>' in rendered


def test_obfuscated_markdown_links_lose_navigation_authority() -> None:
    source = " ".join(
        [
            "[mixed](JaVaScRiPt:alert(1))",
            "[entity](java&#115;cript:alert(1))",
            "[percent](java%73cript%3Aalert(1))",
            "[backslash](https:\\attacker.invalid/path)",
        ]
    )

    rendered = render_longform_markdown(source)

    assert "javascript" not in rendered.lower()
    assert "attacker.invalid" not in rendered
    assert "href=" not in rendered


def test_author_markdown_cannot_forge_server_wikilink_attributes() -> None:
    rendered = render_longform_markdown(
        "[Forged](https://example.com){.wikilink data-target=Target}"
    )

    assert '<a href="https://example.com">Forged</a>' in rendered
    assert "class=" not in rendered
    assert 'data-target="' not in rendered
