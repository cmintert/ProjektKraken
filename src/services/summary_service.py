"""Summary Service Module.

Manages AI-generated natural language summaries for Entities and Events.
Handles LLM provider integration and summary persistence.
"""

import logging
import re
import time
from typing import TYPE_CHECKING, Any, Optional, Union, cast

from src.core.entities import Entity
from src.core.events import Event
from src.core.summary_data import (
    DEFAULT_SUMMARY_PROMPT,
    SUMMARY_SHORT_SOURCE_WORDS,
    SummaryData,
    calculate_summary_source_hash,
    calculate_summary_target_words,
    calculate_summary_word_limit,
    count_summary_words,
    normalize_summary_prompt_template,
)
from src.services.llm_provider import create_provider, log_ai_interaction

if TYPE_CHECKING:
    from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


class SummaryService:
    """Service for managing natural language summaries of Entities and Events."""

    def __init__(self, db_service: "DatabaseService") -> None:
        """Initialize the SummaryService.

        Args:
            db_service: Database service instance for persisting summaries.

        """
        self.db_service = db_service
        # We delay provider creation until needed or create it here.
        # For now, let's create a default provider or look up settings.
        # Ideally, this should rely on `create_provider` dynamically based on config.
        self._llm_provider: Any | None = None

    def _get_provider(self) -> Any:
        """Get or create the LLM provider for text generation.

        Lazily initializes the provider based on settings priority:
        LM Studio > OpenAI > Anthropic > Google.

        Returns:
            Provider: Configured LLM provider instance.

        Raises:
            ValueError: If no AI provider is enabled in settings.

        """
        if not self._llm_provider:
            from PySide6.QtCore import QSettings

            from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

            # Determine provider based on priority
            # Priority: LM Studio (local) > OpenAI > Anthropic > Google
            provider_id = None

            if settings.value("ai_gen_lmstudio_enabled", True, type=bool):
                provider_id = "lmstudio"
            elif settings.value("ai_gen_openai_enabled", False, type=bool):
                provider_id = "openai"
            elif settings.value("ai_gen_anthropic_enabled", False, type=bool):
                provider_id = "anthropic"
            elif settings.value("ai_gen_google_enabled", False, type=bool):
                provider_id = "google"

            if not provider_id:
                raise ValueError(
                    "No AI provider is enabled for text generation. "
                    "Please configure settings in Tools > AI Settings."
                )

            logger.info(f"SummaryService using provider: {provider_id}")
            self._llm_provider = create_provider(provider_id)

        return self._llm_provider

    def reset_provider(self) -> None:
        """Reset the cached LLM provider.

        Forces re-creation with current settings on next use.
        Call this when AI provider/model settings change.
        """
        self._llm_provider = None
        logger.info("SummaryService: LLM provider cache cleared")

    def _calculate_hash(self, item: Union[Entity, Event]) -> str:
        """Calculate a SHA-256 hash of the item's summarizable content.

        Args:
            item: Entity or Event to hash.

        Returns:
            str: SHA-256 hex digest of the item's content.

        """
        return calculate_summary_source_hash(item)

    def is_stale(self, item: Union[Entity, Event]) -> bool:
        """Check if the cached summary is missing or stale.

        Args:
            item: Entity or Event to check.

        Returns:
            bool: True if summary is missing or content has changed.

        """
        summary_data = item.attributes.get("_summary_data")
        if not summary_data:
            return True

        try:
            stored_hash = summary_data.get("hash")
            current_hash = self._calculate_hash(item)
            return stored_hash != current_hash
        except Exception:
            return True

    def get_summary(self, item: Union[Entity, Event]) -> Optional[SummaryData]:
        """Get the cached summary if valid, otherwise None.

        Args:
            item: Entity or Event to retrieve summary for.

        Returns:
            Optional[SummaryData]: Cached summary if valid, None if stale or missing.

        """
        if self.is_stale(item):
            return None

        try:
            data = item.attributes["_summary_data"]
            return SummaryData.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to parse summary data: {e}")
            return None

    def generate_summary(self, item: Union[Entity, Event]) -> SummaryData:
        """Generate a new summary using the LLM and update the item.

        Args:
            item: Entity or Event to summarize.

        Returns:
            SummaryData: Generated summary with metadata.

        Raises:
            RuntimeError: If AI provider times out, connection fails,
                          or generation fails.

        """
        try:
            provider = self._get_provider()
            prompt = self._build_prompt(item)
            logger.info(f"Generating summary for {item.name}. Prompt:\n{prompt}")

            # Read configured summary max tokens from settings
            from PySide6.QtCore import QSettings

            from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            summary_max_tokens = cast(
                int,
                settings.value("ai_gen_summary_max_tokens", 2048, type=int),
            )
            # Retrieve temperature (0-200 int -> 0.0-2.0 float)
            # Default to 0.0 for deterministic summaries
            summary_temp_int = cast(
                int,
                settings.value("ai_gen_summary_temperature", 0, type=int),
            )
            summary_temp = summary_temp_int / 100.0

            response = provider.generate(
                prompt, max_tokens=summary_max_tokens, temperature=summary_temp
            )
            text = self._extract_visible_text(response, settings)
            model = response.get("model", "unknown")

            word_limit = calculate_summary_word_limit(item.description)
            if count_summary_words(text) > word_limit:
                retry_prompt = (
                    "Compress the draft below to no more than "
                    f"{word_limit} words. Preserve its essential facts and any "
                    "proper names, removing the least essential details or complete "
                    "sentences first. Use plain names; special link markup need not "
                    "be preserved. Return only the shortened summary.\n\n"
                    "--- DRAFT TO COMPRESS ---\n"
                    f"{text}\n"
                    "--- END DRAFT ---"
                )
                logger.info(
                    "Summary exceeded %s words; retrying once with a stricter prompt.",
                    word_limit,
                )
                response = provider.generate(
                    retry_prompt,
                    max_tokens=summary_max_tokens,
                    temperature=summary_temp,
                )
                text = self._extract_visible_text(response, settings)
                model = response.get("model", model)

            actual_words = count_summary_words(text)
            if actual_words > word_limit:
                sentence_trimmed = self._trim_complete_sentences(text, word_limit)
                if sentence_trimmed is None:
                    raise RuntimeError(
                        "The AI returned an overlong summary twice "
                        f"({actual_words} words; limit {word_limit}), and it could "
                        "not be shortened safely at a sentence boundary. "
                        "The existing summary was kept unchanged."
                    )
                logger.warning(
                    "Summary retry exceeded %s words; removed complete trailing "
                    "sentences to enforce the limit.",
                    word_limit,
                )
                text = sentence_trimmed

            summary = SummaryData(
                text=text,
                hash=self._calculate_hash(item),
                timestamp=time.time(),
                model=model,
            )

            # Audit log prompt and response (per-world file when available)
            from src.core.logging_config import get_world_audit_log_path

            audit_path = get_world_audit_log_path(self.db_service.db_path)

            log_ai_interaction(
                prompt=prompt,
                response_text=text,
                model=model,
                source="SummaryService",
                audit_path=audit_path,
            )

            # Update item in memory (caller is responsible for persisting)
            item.attributes["_summary_data"] = summary.to_dict()

            return summary

        except TimeoutError:
            logger.error("Summary generation timed out.")
            raise RuntimeError(
                "The AI provider timed out. "
                "Check your network or increase the timeout setting."
            )
        except ConnectionError:
            logger.error("Connection to AI provider failed.")
            raise RuntimeError(
                "Could not connect to the AI provider. "
                "Is LM Studio (or your provider) running?"
            )
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            # Re-raise with a cleaner message if it's a known provider error
            if "Connection refused" in str(e):
                raise RuntimeError(
                    "Connection refused. "
                    "Please ensure your local AI server (e.g., LM Studio) is running."
                )
            raise RuntimeError(f"Generation failed: {str(e)}")

    def _build_prompt(self, item: Union[Entity, Event]) -> str:
        """Construct the prompt for the LLM.

        Loads the custom prompt template from QSettings and applies
        placeholder substitution for item properties.

        Args:
            item: Entity or Event to build prompt for.

        Returns:
            str: Formatted prompt string ready for LLM.

        """
        from PySide6.QtCore import QSettings

        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

        word_limit = calculate_summary_word_limit(item.description)
        if word_limit < 1:
            raise ValueError(
                "The description is too short to summarize. Add at least two "
                "words of source detail before generating."
            )
        target_words = calculate_summary_target_words(item.description)

        template = normalize_summary_prompt_template(
            str(settings.value("ai_gen_summary_prompt", DEFAULT_SUMMARY_PROMPT))
        )

        # Apply placeholder substitution
        lore_date = getattr(item, "lore_date", "")
        prompt = template.format(
            type=item.type,
            name=item.name,
            description=item.description,
            lore_date=lore_date,
        )

        if count_summary_words(item.description) < SUMMARY_SHORT_SOURCE_WORDS:
            length_requirement = (
                f"Return exactly one sentence of no more than {word_limit} words, "
                "with no heading or bullet list."
            )
        else:
            length_requirement = (
                f"Aim for no more than {target_words} words. The mandatory hard "
                f"maximum is {word_limit} words."
            )

        return (
            f"{prompt}\n\n"
            f"MANDATORY OUTPUT RULE: Return only the summary. {length_requirement} "
            "Use ordinary prose and plain names; special link markup need not be "
            "preserved."
        )

    @staticmethod
    def _extract_visible_text(response: dict[str, Any], settings: Any) -> str:
        """Extract visible response text after optional reasoning-tag filtering."""
        text = response.get("text", "").strip()
        logger.info(f"Summary generation raw response:\n{text}")

        if settings.value("ai_gen_filter_reasoning", True, type=bool):
            from src.services.reasoning_filter import filter_reasoning_tags

            text = filter_reasoning_tags(text).strip()
            logger.info(f"Summary after reasoning filter:\n{text}")

        return text

    @staticmethod
    def _trim_complete_sentences(text: str, word_limit: int) -> str | None:
        """Remove complete trailing sentences until text meets the hard limit."""
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", text.strip())
            if sentence.strip()
        ]
        if len(sentences) < 2:
            return None

        while len(sentences) > 1:
            sentences.pop()
            candidate = " ".join(sentences)
            if count_summary_words(candidate) <= word_limit:
                return candidate
        return None
