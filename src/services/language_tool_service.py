"""LanguageTool spell/grammar checking service.

Provides async spell and grammar checking via the LanguageTool public HTTP API.
Matches are returned with offset/length positions for document highlighting.
"""

import json
import logging
from dataclasses import dataclass

import requests
from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.languagetool.org/v2/check"

# Public-API free tier caps each request at 20 KB. Leave a small margin so the
# encoded form payload (language + credentials) still fits.
MAX_TEXT_BYTES = 20_000 - 512


@dataclass
class LTMatch:
    """A single spelling/grammar match from LanguageTool.

    Attributes:
        offset: Character offset in the original text where the match starts.
        length: Number of characters spanned by the match.
        message: Human-readable error explanation.
        replacements: Ordered list of suggested corrections (may be empty).
        rule_id: Unique rule identifier (e.g. "UPPERCASE_SENTENCE_START").
        issue_type: Classification (e.g. "misspelling", "grammar", "typographical").

    """

    offset: int
    length: int
    message: str
    replacements: list[str]
    rule_id: str
    issue_type: str


def _truncate_to_byte_limit(text: str, limit: int = MAX_TEXT_BYTES) -> str:
    """Return a prefix of ``text`` whose UTF-8 encoding fits in ``limit`` bytes.

    The LanguageTool public API rejects requests larger than 20 KB. This
    truncates at a character boundary so the emitted offsets remain valid
    Python string indices.

    Args:
        text: Input text.
        limit: Maximum byte length of the UTF-8 encoding.

    Returns:
        A prefix of ``text`` that encodes to at most ``limit`` bytes.

    """
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text
    # Decode the limit-sized prefix, dropping any partial trailing codepoint.
    return encoded[:limit].decode("utf-8", errors="ignore")


class LanguageToolWorker(QObject):
    """Worker for async spell/grammar checking via LanguageTool API.

    Runs in a QThread and emits results via Qt signals.
    Designed to be moved to a QThread for non-blocking operation.

    Signals:
        results_ready: Emitted with list[LTMatch] when check completes.

    """

    results_ready = Signal(list)

    def __init__(self) -> None:
        """Initialize the worker."""
        super().__init__()
        self.timeout = 5

    @Slot(str, str, str, str)
    def check(
        self, text: str, language: str, username: str = "", api_key: str = ""
    ) -> None:
        """Check text for spelling and grammar errors.

        Runs synchronously (blocking) in the worker thread.
        Silently swallows connection/timeout errors and returns empty list.

        Args:
            text: Plain text to check.
            language: RFC 3066 language code (e.g. "en-US", "auto").
            username: Optional premium account email.
            api_key: Optional premium API key.

        """
        if not text.strip():
            self.results_ready.emit([])
            return

        # Enforce the public-API 20 KB-per-request size limit.
        text = _truncate_to_byte_limit(text)

        try:
            params = {
                "text": text,
                "language": language or "auto",
            }

            # Add premium credentials only when both are provided.
            if username and api_key:
                params["username"] = username
                params["apiKey"] = api_key

            response = requests.post(ENDPOINT, data=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            matches = [self._parse_match(m) for m in data.get("matches", [])]
            self.results_ready.emit(matches)

        except requests.exceptions.RequestException as e:
            logger.debug(f"LanguageTool check failed (connection): {e}")
            self.results_ready.emit([])
        except json.JSONDecodeError as e:
            logger.debug(f"LanguageTool check failed (JSON parse): {e}")
            self.results_ready.emit([])
        except Exception as e:
            logger.debug(f"LanguageTool check failed (unexpected): {e}")
            self.results_ready.emit([])

    @staticmethod
    def _parse_match(raw: dict) -> LTMatch:
        """Convert a raw match dict from the API into an ``LTMatch``.

        Args:
            raw: Single element from the ``matches`` array of the response.

        Returns:
            A populated ``LTMatch``. Missing fields fall back to sensible defaults.

        """
        replacements = [r.get("value", "") for r in raw.get("replacements", [])]
        rule = raw.get("rule") or {}
        return LTMatch(
            offset=int(raw.get("offset", 0)),
            length=int(raw.get("length", 0)),
            message=raw.get("message", ""),
            replacements=replacements,
            rule_id=rule.get("id", ""),
            issue_type=rule.get("issueType", "unknown"),
        )
