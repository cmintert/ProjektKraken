"""Prompt Builder Service Module.

Encapsulates prompt construction, variable substitution, and context formatting
for LLM generation. Extracted from LLMGenerationWidget to enforce separation
of concerns between UI and business logic.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default system prompt used for LLM content generation.
# Defines the LLM's role, tone, and behavior for worldbuilding tasks.
# Used as a fallback when no custom persona is configured in QSettings
# (key: 'ai_gen_system_prompt', managed via Settings → AI Settings).
DEFAULT_SYSTEM_PROMPT = (
    "You are an expert fantasy world-builder assisting a user in creating a "
    "rich and immersive setting. Your tone is descriptive, evocative, and "
    "consistent with high-fantasy literature.\n\n"
    "CONTEXT: This world tracks time using a numeric calendar where whole "
    "numbers represent days and decimals represent portions of the day "
    "(for example, 0.5 is midday). When you encounter these numeric dates "
    "in the data below, translate them into natural, narrative-appropriate "
    "language — do not repeat the raw numbers in your prose."
)


class PromptBuilder:
    """Builds structured prompts for LLM generation.

    Encapsulates prompt assembly, variable substitution, and context
    formatting logic. Produces a dict with 'system' and 'user' keys
    suitable for chat-based LLM APIs.
    """

    def __init__(self, system_prompt: Optional[str] = None) -> None:
        """Initialize PromptBuilder.

        Args:
            system_prompt: Custom system prompt / persona. Falls back to
                DEFAULT_SYSTEM_PROMPT if not provided.

        """
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    def build_context_string(self, context: Dict[str, Any]) -> str:
        """Build a formatted context string from editor context data.

        Args:
            context: Context dictionary from the editor, typically
                containing keys like 'name', 'type', 'lore_date',
                'existing_description'.

        Returns:
            str: Newline-separated context lines.

        """
        context_lines: List[str] = []

        if "name" in context:
            context_lines.append(f"Name: {context['name']}")
        if "type" in context:
            context_lines.append(f"Type: {context['type']}")
        if "lore_date" in context:
            context_lines.append(f"Lore Date: {context['lore_date']}")
        if "existing_description" in context:
            context_lines.append(f"Description: {context['existing_description']}")

        # Add any additional context fields not already handled
        known_keys = {
            "name",
            "type",
            "lore_date",
            "existing_description",
            "description",
            # Metadata keys consumed by spatial-context lookup — not LLM-facing.
            "object_id",
            "object_type",
        }
        context_lines.extend(
            f"{k.replace('_', ' ').title()}: {v}"
            for k, v in context.items()
            if k not in known_keys
        )

        return "\n".join(context_lines)

    def substitute_variables(self, user_prompt: str, context: Dict[str, Any]) -> str:
        """Substitute variables like {name} in the user prompt.

        Args:
            user_prompt: Raw user instruction with variable placeholders.
            context: Context dictionary from editor.

        Returns:
            str: Prompt with variables replaced by context values.

        """
        subst_context = {
            "name": context.get("name", ""),
            "type": context.get("type", ""),
            "description": context.get("existing_description", ""),
            "lore_date": context.get("lore_date", ""),
        }

        result = user_prompt
        for key, val in subst_context.items():
            result = result.replace(f"{{{key}}}", str(val))

        return result

    def construct_prompt(
        self,
        context_str: str,
        user_prompt: str,
        include_rag_placeholder: bool = False,
        include_spatial_placeholder: bool = False,
    ) -> Dict[str, str]:
        """Construct the final structured prompt with persona and context.

        Uses the ordering: Data blocks BEFORE Task instruction. This reduces
        recency bias — the LLM reads the data first, then receives the
        creative task as the final instruction it must follow.

        Args:
            context_str: Formatted context string with entity/event details.
            user_prompt: User's custom prompt/task (already substituted).
            include_rag_placeholder: Whether to include the {{RAG_CONTEXT}}
                placeholder for later injection by the worker.
            include_spatial_placeholder: Whether to include the
                {{SPATIAL_CONTEXT}} placeholder for later injection by the
                worker.

        Returns:
            Dict[str, str]: Structured prompt with 'system' and 'user' keys.

        """
        user_message_parts: List[str] = []

        # -- DATA: ENTITY/EVENT DETAILS -- (placed first)
        if context_str:
            user_message_parts.append(f"[Entity]\n{context_str}")

        # -- DATA: RAG CONTEXT -- (optional placeholder)
        if include_rag_placeholder:
            user_message_parts.append("{{RAG_CONTEXT}}")

        # -- DATA: SPATIAL CONTEXT -- (optional placeholder)
        if include_spatial_placeholder:
            user_message_parts.append("{{SPATIAL_CONTEXT}}")

        # -- TASK -- (placed last to reduce recency bias)
        user_message_parts.append(f"[Task]\n{user_prompt}")

        # Filter out empty parts and assemble
        final_user_message = "\n\n".join(filter(None, user_message_parts))

        return {"system": self.system_prompt, "user": final_user_message}
