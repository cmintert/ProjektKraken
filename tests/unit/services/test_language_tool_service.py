"""Unit tests for ``src.services.language_tool_service``."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.services.language_tool_service import (
    ENDPOINT,
    MAX_TEXT_BYTES,
    LanguageToolWorker,
    LTMatch,
    _truncate_to_byte_limit,
)


@pytest.fixture
def worker(qapp) -> LanguageToolWorker:
    """Create a worker running in the main thread for direct call-based testing."""
    return LanguageToolWorker()


def _make_response(payload: dict, status: int = 200) -> MagicMock:
    """Build a fake ``requests.Response``-like object returning ``payload``."""
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    if status >= 400:
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            f"{status} error"
        )
    else:
        response.raise_for_status.return_value = None
    return response


def _collect(worker: LanguageToolWorker) -> list[list]:
    """Connect to ``results_ready`` and return a list that receives every emission."""
    results: list[list] = []
    worker.results_ready.connect(lambda matches: results.append(matches))
    return results


class TestTruncation:
    """Tests for ``_truncate_to_byte_limit``."""

    def test_short_text_unchanged(self) -> None:
        assert _truncate_to_byte_limit("hello", limit=100) == "hello"

    def test_long_ascii_truncated_to_limit(self) -> None:
        text = "a" * 50_000
        truncated = _truncate_to_byte_limit(text, limit=100)
        assert len(truncated.encode("utf-8")) <= 100
        assert text.startswith(truncated)

    def test_multibyte_boundary_preserved(self) -> None:
        # "ü" encodes to 2 bytes; truncating to 3 bytes must not split mid-codepoint.
        text = "üüüüü"  # 10 bytes in UTF-8
        truncated = _truncate_to_byte_limit(text, limit=3)
        # Either "ü" (2 bytes) or "" — anything in between would be invalid UTF-8.
        assert truncated.encode("utf-8") in (b"\xc3\xbc", b"")

    def test_empty_string_handled(self) -> None:
        assert _truncate_to_byte_limit("", limit=100) == ""

    def test_default_limit_matches_public_api(self) -> None:
        assert MAX_TEXT_BYTES <= 20_000


class TestWorkerEarlyReturn:
    """Tests that short-circuit before any HTTP call is made."""

    def test_empty_text_emits_empty_list(self, worker: LanguageToolWorker) -> None:
        results = _collect(worker)
        with patch("src.services.language_tool_service.requests.post") as post:
            worker.check("", "en-US")
        post.assert_not_called()
        assert results == [[]]

    def test_whitespace_only_text_emits_empty_list(
        self, worker: LanguageToolWorker
    ) -> None:
        results = _collect(worker)
        with patch("src.services.language_tool_service.requests.post") as post:
            worker.check("   \n\t  ", "en-US")
        post.assert_not_called()
        assert results == [[]]


class TestWorkerRequestShape:
    """Tests verifying the outgoing HTTP request."""

    def test_posts_to_public_endpoint(self, worker: LanguageToolWorker) -> None:
        with patch("src.services.language_tool_service.requests.post") as post:
            post.return_value = _make_response({"matches": []})
            worker.check("Hello world.", "en-US")
        url = post.call_args.args[0]
        assert url == ENDPOINT

    def test_sends_text_and_language_as_form_data(
        self, worker: LanguageToolWorker
    ) -> None:
        with patch("src.services.language_tool_service.requests.post") as post:
            post.return_value = _make_response({"matches": []})
            worker.check("Hello world.", "en-US")
        kwargs = post.call_args.kwargs
        assert kwargs["data"]["text"] == "Hello world."
        assert kwargs["data"]["language"] == "en-US"
        # Credentials must NOT appear when not provided.
        assert "username" not in kwargs["data"]
        assert "apiKey" not in kwargs["data"]

    def test_blank_language_defaults_to_auto(
        self, worker: LanguageToolWorker
    ) -> None:
        with patch("src.services.language_tool_service.requests.post") as post:
            post.return_value = _make_response({"matches": []})
            worker.check("Hello world.", "")
        assert post.call_args.kwargs["data"]["language"] == "auto"

    def test_premium_credentials_sent_when_both_provided(
        self, worker: LanguageToolWorker
    ) -> None:
        with patch("src.services.language_tool_service.requests.post") as post:
            post.return_value = _make_response({"matches": []})
            worker.check("Hello world.", "en-US", username="a@b.c", api_key="K")
        data = post.call_args.kwargs["data"]
        assert data["username"] == "a@b.c"
        assert data["apiKey"] == "K"

    def test_premium_credentials_omitted_when_only_one_provided(
        self, worker: LanguageToolWorker
    ) -> None:
        with patch("src.services.language_tool_service.requests.post") as post:
            post.return_value = _make_response({"matches": []})
            worker.check("Hello world.", "en-US", username="a@b.c", api_key="")
        data = post.call_args.kwargs["data"]
        assert "username" not in data
        assert "apiKey" not in data

    def test_oversize_text_truncated_before_send(
        self, worker: LanguageToolWorker
    ) -> None:
        big = "a" * (MAX_TEXT_BYTES + 5_000)
        with patch("src.services.language_tool_service.requests.post") as post:
            post.return_value = _make_response({"matches": []})
            worker.check(big, "en-US")
        sent = post.call_args.kwargs["data"]["text"]
        assert len(sent.encode("utf-8")) <= MAX_TEXT_BYTES

    def test_timeout_applied(self, worker: LanguageToolWorker) -> None:
        with patch("src.services.language_tool_service.requests.post") as post:
            post.return_value = _make_response({"matches": []})
            worker.check("Hello world.", "en-US")
        assert post.call_args.kwargs["timeout"] == worker.timeout


class TestResponseParsing:
    """Tests that the JSON response is converted into LTMatch objects."""

    def test_full_match_parsed(self, worker: LanguageToolWorker) -> None:
        payload = {
            "matches": [
                {
                    "offset": 10,
                    "length": 4,
                    "message": "Possible spelling mistake found.",
                    "replacements": [{"value": "test"}, {"value": "text"}],
                    "rule": {
                        "id": "MORFOLOGIK_RULE_EN_US",
                        "issueType": "misspelling",
                    },
                }
            ]
        }
        results = _collect(worker)
        with patch("src.services.language_tool_service.requests.post") as post:
            post.return_value = _make_response(payload)
            worker.check("This is an tset example.", "en-US")

        assert len(results) == 1
        (match,) = results[0]
        assert isinstance(match, LTMatch)
        assert match.offset == 10
        assert match.length == 4
        assert match.replacements == ["test", "text"]
        assert match.rule_id == "MORFOLOGIK_RULE_EN_US"
        assert match.issue_type == "misspelling"
        assert "spelling mistake" in match.message

    def test_multiple_matches_preserve_order(self, worker: LanguageToolWorker) -> None:
        payload = {
            "matches": [
                {
                    "offset": 0,
                    "length": 1,
                    "message": "A",
                    "replacements": [],
                    "rule": {"id": "R1", "issueType": "grammar"},
                },
                {
                    "offset": 5,
                    "length": 2,
                    "message": "B",
                    "replacements": [],
                    "rule": {"id": "R2", "issueType": "typographical"},
                },
            ]
        }
        results = _collect(worker)
        with patch("src.services.language_tool_service.requests.post") as post:
            post.return_value = _make_response(payload)
            worker.check("dummy text long enough", "en-US")
        assert [m.rule_id for m in results[0]] == ["R1", "R2"]

    def test_missing_replacements_handled(self, worker: LanguageToolWorker) -> None:
        payload = {
            "matches": [
                {
                    "offset": 0,
                    "length": 1,
                    "message": "msg",
                    "rule": {"id": "R", "issueType": "grammar"},
                }
            ]
        }
        results = _collect(worker)
        with patch("src.services.language_tool_service.requests.post") as post:
            post.return_value = _make_response(payload)
            worker.check("dummy", "en-US")
        assert results[0][0].replacements == []

    def test_missing_rule_defaults_applied(self, worker: LanguageToolWorker) -> None:
        payload = {"matches": [{"offset": 0, "length": 1}]}
        results = _collect(worker)
        with patch("src.services.language_tool_service.requests.post") as post:
            post.return_value = _make_response(payload)
            worker.check("dummy", "en-US")
        match = results[0][0]
        assert match.rule_id == ""
        assert match.issue_type == "unknown"
        assert match.replacements == []

    def test_empty_matches_list_emits_empty_list(
        self, worker: LanguageToolWorker
    ) -> None:
        results = _collect(worker)
        with patch("src.services.language_tool_service.requests.post") as post:
            post.return_value = _make_response({"matches": []})
            worker.check("dummy", "en-US")
        assert results == [[]]


class TestErrorHandling:
    """Tests that network and parsing failures are swallowed into empty lists."""

    def test_connection_error_emits_empty_list(
        self, worker: LanguageToolWorker
    ) -> None:
        results = _collect(worker)
        with patch("src.services.language_tool_service.requests.post") as post:
            post.side_effect = requests.exceptions.ConnectionError("no network")
            worker.check("dummy text", "en-US")
        assert results == [[]]

    def test_timeout_emits_empty_list(self, worker: LanguageToolWorker) -> None:
        results = _collect(worker)
        with patch("src.services.language_tool_service.requests.post") as post:
            post.side_effect = requests.exceptions.Timeout("slow")
            worker.check("dummy text", "en-US")
        assert results == [[]]

    def test_http_error_emits_empty_list(self, worker: LanguageToolWorker) -> None:
        results = _collect(worker)
        with patch("src.services.language_tool_service.requests.post") as post:
            post.return_value = _make_response({}, status=429)
            worker.check("dummy text", "en-US")
        assert results == [[]]

    def test_invalid_json_emits_empty_list(
        self, worker: LanguageToolWorker
    ) -> None:
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.side_effect = json.JSONDecodeError("boom", "doc", 0)
        results = _collect(worker)
        with patch("src.services.language_tool_service.requests.post") as post:
            post.return_value = response
            worker.check("dummy text", "en-US")
        assert results == [[]]

    def test_unexpected_exception_emits_empty_list(
        self, worker: LanguageToolWorker
    ) -> None:
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"matches": [{"offset": "not-an-int"}]}
        results = _collect(worker)
        with patch("src.services.language_tool_service.requests.post") as post:
            post.return_value = response
            worker.check("dummy text", "en-US")
        # The offset "not-an-int" will raise ValueError inside _parse_match — the
        # catch-all exception handler must still produce an empty result emission.
        assert results == [[]]
