"""Summary Service Module.

Manages AI-generated natural language summaries for Entities and Events.
Handles LLM provider integration and summary persistence.
"""

import hashlib
import logging
import time
from typing import TYPE_CHECKING, Any, Optional, Union

from src.core.entities import Entity
from src.core.events import Event
from src.core.summary_data import SummaryData
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
        self._llm_provider = None

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
        content = f"{item.name}|{item.type}|{item.description}"
        # We can add more fields later (e.g. key attributes)
        if hasattr(item, "lore_date"):
            content += f"|{item.lore_date}"

        return hashlib.sha256(content.encode("utf-8")).hexdigest()

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
            summary_max_tokens = int(settings.value("ai_gen_summary_max_tokens", 2048))
            response = provider.generate(prompt, max_tokens=summary_max_tokens)
            text = response.get("text", "").strip()
            model = response.get("model", "unknown")
            logger.info(f"Summary generation raw response:\n{text}")

            # Apply reasoning tag filter if enabled
            filter_reasoning = settings.value(
                "ai_gen_filter_reasoning", True, type=bool
            )
            if filter_reasoning:
                from src.services.reasoning_filter import filter_reasoning_tags

                text = filter_reasoning_tags(text)
                logger.info(f"Summary after reasoning filter:\n{text}")

            summary = SummaryData(
                text=text,
                hash=self._calculate_hash(item),
                timestamp=time.time(),
                model=model,
            )

            # Audit log prompt and response
            log_ai_interaction(
                prompt=prompt,
                response_text=text,
                model=model,
                source="SummaryService",
            )

            # Update item
            item.attributes["_summary_data"] = summary.to_dict()

            # Persist summary immediately
            if isinstance(item, Entity):
                self.db_service.insert_entity(item)
            elif isinstance(item, Event):
                self.db_service.insert_event(item)

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

        # Default prompt template
        default_template = (
            "Summarize the following worldbuilding item neutrally, "
            "preserving all facts and the original tone. "
            "Crucially, PRESERVE any [[Wiki Links]] exactly as they appear.\n\n"
            "--- DATA: ENTITY/EVENT DETAILS ---\n"
            "Type: {type}\n"
            "Name: {name}\n"
            "Description: {description}\n"
            "--- END DATA ---"
        )

        template = settings.value("ai_gen_summary_prompt", default_template)

        # Apply placeholder substitution
        lore_date = getattr(item, "lore_date", "")
        prompt = template.format(
            type=item.type,
            name=item.name,
            description=item.description,
            lore_date=lore_date,
        )

        return prompt
