"""Unit tests for the reasoning filter module.

Tests cover complete tag pairs, unclosed/truncated tags, pipe-delimited tags,
tags with attributes, edge cases, and whitespace normalisation.
"""

from src.services.reasoning_filter import filter_reasoning_tags

# ---------------------------------------------------------------------------
# Complete standard tag pairs
# ---------------------------------------------------------------------------


class TestCompleteStandardTags:
    """Tests for complete XML-style tag pairs like <think>...</think>."""

    def test_simple_think_tag(self) -> None:
        """Basic <think>...</think> removal."""
        text = "<think>internal reasoning</think>The actual answer."
        assert filter_reasoning_tags(text) == "The actual answer."

    def test_thinking_tag(self) -> None:
        """<thinking>...</thinking> removal (Claude style)."""
        text = "<thinking>Let me consider...</thinking>Here is the answer."
        assert filter_reasoning_tags(text) == "Here is the answer."

    def test_reasoning_tag(self) -> None:
        """<reasoning>...</reasoning> removal."""
        text = "<reasoning>Step 1... Step 2...</reasoning>Final result."
        assert filter_reasoning_tags(text) == "Final result."

    def test_scratchpad_tag(self) -> None:
        """<scratchpad>...</scratchpad> removal."""
        text = "<scratchpad>notes here</scratchpad>The answer is 42."
        assert filter_reasoning_tags(text) == "The answer is 42."

    def test_reflection_tag(self) -> None:
        """<reflection>...</reflection> removal."""
        text = "<reflection>I need to reconsider</reflection>Corrected answer."
        assert filter_reasoning_tags(text) == "Corrected answer."

    def test_thought_tag(self) -> None:
        """<thought>...</thought> removal."""
        text = "<thought>hmm...</thought>Result."
        assert filter_reasoning_tags(text) == "Result."

    def test_multiline_content(self) -> None:
        """Tags spanning multiple lines should be removed."""
        text = (
            "<think>\nLet me think about this.\n"
            "There are many factors.\n"
            "I'll consider each one.\n</think>\n"
            "The Eldertree stands tall in the forest."
        )
        assert filter_reasoning_tags(text) == (
            "\nThe Eldertree stands tall in the forest."
        )

    def test_multiple_tag_blocks(self) -> None:
        """Multiple separate reasoning blocks should all be removed."""
        text = (
            "<think>first block</think>Part one. <think>second block</think>Part two."
        )
        assert filter_reasoning_tags(text) == "Part one. Part two."

    def test_case_insensitive(self) -> None:
        """Tag matching should be case-insensitive."""
        text = "<Think>reasoning</Think>Answer."
        assert filter_reasoning_tags(text) == "Answer."

        text2 = "<THINKING>stuff</THINKING>Result."
        assert filter_reasoning_tags(text2) == "Result."

    def test_tags_with_attributes(self) -> None:
        """Tags with attributes should still be matched."""
        text = '<think type="internal">reasoning</think>Answer.'
        assert filter_reasoning_tags(text) == "Answer."

    def test_tags_with_whitespace(self) -> None:
        """Tags with whitespace around the name should be matched."""
        text = "< think >reasoning</ think >Answer."
        assert filter_reasoning_tags(text) == "Answer."


# ---------------------------------------------------------------------------
# Pipe-delimited tag pairs (Qwen-3 style)
# ---------------------------------------------------------------------------


class TestPipeDelimitedTags:
    """Tests for pipe-delimited tags like <|think|>...<|/think|>."""

    def test_simple_pipe_think(self) -> None:
        """Basic <|think|>...<|/think|> removal."""
        text = "<|think|>reasoning here<|/think|>The answer."
        assert filter_reasoning_tags(text) == "The answer."

    def test_pipe_thinking(self) -> None:
        """<|thinking|>...<|/thinking|> removal."""
        text = "<|thinking|>Let me consider<|/thinking|>Result."
        assert filter_reasoning_tags(text) == "Result."

    def test_pipe_multiline(self) -> None:
        """Pipe tags with multiline content."""
        text = (
            "<|think|>\n"
            "Step 1: analyze\n"
            "Step 2: synthesize\n"
            "<|/think|>\n"
            "The kingdom fell in the third age."
        )
        assert filter_reasoning_tags(text) == (
            "\nThe kingdom fell in the third age."
        )


# ---------------------------------------------------------------------------
# Unclosed / truncated tags (THE critical fix)
# ---------------------------------------------------------------------------


class TestUnclosedTags:
    """Tests for unclosed/truncated reasoning tags — the main bug fix."""

    def test_unclosed_think_tag(self) -> None:
        """Unclosed <think> (output truncated by max_tokens)."""
        text = "<think>Let me reason about this carefully. The entity has..."
        assert filter_reasoning_tags(text) == ""

    def test_unclosed_with_preceding_content(self) -> None:
        """Content before an unclosed <think> should be preserved."""
        text = (
            "The Eldertree is ancient. "
            "<think>Now I need to describe more about the tree "
            "and its significance in the lore"
        )
        assert filter_reasoning_tags(text) == "The Eldertree is ancient. "

    def test_unclosed_thinking_tag(self) -> None:
        """Unclosed <thinking> tag."""
        text = "Intro. <thinking>Let me analyze this request thoroughly..."
        assert filter_reasoning_tags(text) == "Intro. "

    def test_unclosed_pipe_tag(self) -> None:
        """Unclosed pipe-delimited tag."""
        text = "<|think|>Starting my analysis of the situation..."
        assert filter_reasoning_tags(text) == ""

    def test_unclosed_pipe_with_preceding_content(self) -> None:
        """Content before an unclosed pipe tag should be preserved."""
        text = "Here is the answer. <|think|>Let me verify that..."
        assert filter_reasoning_tags(text) == "Here is the answer. "

    def test_closed_tag_followed_by_unclosed(self) -> None:
        """A closed block followed by an unclosed block."""
        text = (
            "<think>first analysis</think>"
            "The castle was built in the second age. "
            "<think>Let me add more detail about the construction"
        )
        expected = "The castle was built in the second age. "
        assert filter_reasoning_tags(text) == expected

    def test_real_world_truncation(self) -> None:
        """Simulate real-world scenario where max_tokens cuts mid-thought."""
        text = (
            "<think>\n"
            "The user wants a description of the Sunken Library.\n"
            "I should include:\n"
            "- Its location beneath the Silver Lake\n"
            "- The magical wards that protect the books\n"
            "- The spectral librarians\n"
            "\n"
            "Let me craft a vivid description that captures the "
            "otherworldly atmosphere of this place.\n"
            "</think>\n"
            "\n"
            "Beneath the still waters of the Silver Lake lies the Sunken "
            "Library, a vast repository of arcane knowledge preserved by "
            "ancient enchantments. Spectral librarians drift between the "
            "shelves, their translucent forms illuminated by"
        )
        result = filter_reasoning_tags(text)
        assert "Beneath the still waters" in result
        assert "I should include" not in result
        assert "<think>" not in result

    def test_unclosed_after_newlines(self) -> None:
        """Unclosed tag with lots of newlines (common in thinking output)."""
        text = (
            "<think>\n\n"
            "Analysis:\n"
            "- Point one\n"
            "- Point two\n\n"
            "I think the best approach is"
        )
        assert filter_reasoning_tags(text) == ""


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_string(self) -> None:
        """Empty input returns empty output."""
        assert filter_reasoning_tags("") == ""

    def test_no_tags(self) -> None:
        """Text without any reasoning tags is returned unchanged."""
        text = "The kingdom prospered under wise rule."
        assert filter_reasoning_tags(text) == text

    def test_empty_tag_pair(self) -> None:
        """Empty tag pair is removed cleanly."""
        text = "<think></think>Content."
        assert filter_reasoning_tags(text) == "Content."

    def test_only_reasoning(self) -> None:
        """When the entire output is a reasoning block."""
        text = "<think>This is all reasoning and nothing else.</think>"
        assert filter_reasoning_tags(text) == ""

    def test_nested_angle_brackets(self) -> None:
        """Angle brackets in reasoning content (e.g. code snippets)."""
        text = "<think>if x > 0 and y < 10: do_thing()</think>Result."
        assert filter_reasoning_tags(text) == "Result."

    def test_html_like_content_preserved(self) -> None:
        """Non-reasoning HTML-like tags should NOT be removed."""
        text = "<b>Bold text</b> and <i>italic</i> content."
        assert (
            filter_reasoning_tags(text) == "<b>Bold text</b> and <i>italic</i> content."
        )

    def test_whitespace_is_preserved(self) -> None:
        """Whitespace outside reasoning blocks must be preserved exactly."""
        text = (
            "<think>reasoning</think>\n\n\n\n\n"
            "First paragraph.\n\n\n\n\n"
            "Second paragraph."
        )
        expected = "\n\n\n\n\nFirst paragraph.\n\n\n\n\nSecond paragraph."
        assert filter_reasoning_tags(text) == expected

    def test_visible_reply_format_is_byte_for_byte_unchanged(self) -> None:
        """Markdown, wiki links, Unicode, and outer whitespace survive."""
        text = "  # Heading\n\n[[Abyss]] — *unchanged*\n\n\n  "
        assert filter_reasoning_tags(text) == text

    def test_inner_monologue_tag(self) -> None:
        """<inner_monologue> tag should be filtered."""
        text = "<inner_monologue>thinking aloud</inner_monologue>Answer."
        assert filter_reasoning_tags(text) == "Answer."

    def test_internal_tag(self) -> None:
        """<internal> tag should be filtered."""
        text = "<internal>private notes</internal>Public answer."
        assert filter_reasoning_tags(text) == "Public answer."

    def test_mixed_formats(self) -> None:
        """Mix of standard and pipe-delimited tags."""
        text = (
            "<think>standard reasoning</think>"
            "Middle content. "
            "<|thinking|>pipe reasoning<|/thinking|>"
            "End content."
        )
        assert filter_reasoning_tags(text) == "Middle content. End content."
