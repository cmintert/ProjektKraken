"""Unit tests for PromptBuilder service.

Tests prompt construction, variable substitution, context formatting,
and the data-before-task ordering that reduces recency bias.
"""


from src.services.prompt_builder import DEFAULT_SYSTEM_PROMPT, PromptBuilder


class TestPromptBuilder:
    """Tests for PromptBuilder class."""

    def test_default_system_prompt(self) -> None:
        """Test that PromptBuilder falls back to DEFAULT_SYSTEM_PROMPT."""
        builder = PromptBuilder()
        result = builder.construct_prompt("ctx", "task")
        assert result["system"] == DEFAULT_SYSTEM_PROMPT

    def test_custom_system_prompt(self) -> None:
        """Test that PromptBuilder uses a custom system prompt."""
        builder = PromptBuilder(system_prompt="Custom persona.")
        result = builder.construct_prompt("ctx", "task")
        assert result["system"] == "Custom persona."

    def test_build_context_string_basic(self) -> None:
        """Test context string with standard fields."""
        builder = PromptBuilder()
        ctx = {
            "name": "Eldrath",
            "type": "Character",
            "lore_date": "100.5",
            "existing_description": "A wandering sorcerer.",
        }
        result = builder.build_context_string(ctx)
        assert "Name: Eldrath" in result
        assert "Type: Character" in result
        assert "Lore Date: 100.5" in result
        assert "Description: A wandering sorcerer." in result

    def test_build_context_string_extra_fields(self) -> None:
        """Test context string includes additional custom fields."""
        builder = PromptBuilder()
        ctx = {"name": "Foo", "custom_attribute": "bar"}
        result = builder.build_context_string(ctx)
        assert "Name: Foo" in result
        assert "Custom Attribute: bar" in result

    def test_build_context_string_empty(self) -> None:
        """Test context string with empty context."""
        builder = PromptBuilder()
        result = builder.build_context_string({})
        assert result == ""

    def test_substitute_variables(self) -> None:
        """Test variable substitution in user prompts."""
        builder = PromptBuilder()
        ctx = {
            "name": "Eldrath",
            "type": "Sorcerer",
            "existing_description": "A wanderer.",
            "lore_date": "42.0",
        }
        result = builder.substitute_variables(
            "Write about {name} the {type} on day {lore_date}", ctx
        )
        assert result == "Write about Eldrath the Sorcerer on day 42.0"

    def test_substitute_variables_missing_context(self) -> None:
        """Test that missing context values produce empty strings."""
        builder = PromptBuilder()
        result = builder.substitute_variables("About {name}: {type}", {})
        assert result == "About : "

    def test_construct_prompt_data_before_task(self) -> None:
        """Test that data blocks appear BEFORE the task instruction.

        This ordering reduces recency bias — the LLM reads data first,
        then receives the creative task as the final instruction.
        """
        builder = PromptBuilder()
        result = builder.construct_prompt(
            "Name: Eldrath", "Write a backstory"
        )
        user_msg = result["user"]

        entity_pos = user_msg.index("[Entity]")
        task_pos = user_msg.index("[Task]")

        # Data block should come before Task
        assert entity_pos < task_pos

    def test_construct_prompt_with_rag_placeholder(self) -> None:
        """Test that RAG placeholder is included when requested."""
        builder = PromptBuilder()
        result = builder.construct_prompt(
            "Name: Foo", "Describe this",
            include_rag_placeholder=True,
        )
        assert "{{RAG_CONTEXT}}" in result["user"]

    def test_construct_prompt_without_rag_placeholder(self) -> None:
        """Test that RAG placeholder is excluded when not requested."""
        builder = PromptBuilder()
        result = builder.construct_prompt(
            "Name: Foo", "Describe this",
            include_rag_placeholder=False,
        )
        assert "{{RAG_CONTEXT}}" not in result["user"]

    def test_construct_prompt_contains_delimiters(self) -> None:
        """Test that prompt contains expected section markers."""
        builder = PromptBuilder()
        result = builder.construct_prompt("ctx", "task")
        user_msg = result["user"]
        assert "[Entity]" in user_msg
        assert "[Task]" in user_msg
        assert "task" in user_msg

    def test_default_system_prompt_narrative_temporal(self) -> None:
        """Test that default system prompt uses narrative-friendly temporal guidance.

        The prompt should instruct the LLM to translate numeric dates into
        natural language, rather than repeating raw float values.
        """
        assert "narrative" in DEFAULT_SYSTEM_PROMPT.lower()
        assert (
            "translate" in DEFAULT_SYSTEM_PROMPT.lower()
            or "natural" in DEFAULT_SYSTEM_PROMPT.lower()
        )
        # Should NOT contain the old robotic instruction
        assert "IMPORTANT: Time in this world is represented" not in DEFAULT_SYSTEM_PROMPT
