"""Tests for SentenceTransformersProvider thread-safety environment variables.

Regression test for Windows heap corruption (0xc0000374) caused by
HuggingFace tokenizer and OpenMP spawning uncontrolled native threads
on the background QThread where the embedding model runs.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestSentenceTransformersThreadSafety:
    """Verify that thread-safety env vars are set before model loading."""

    def test_tokenizers_parallelism_set_before_import(self):
        """TOKENIZERS_PARALLELISM must be 'false' after provider init."""
        # Remove if already set so we can verify the provider sets it
        old_val = os.environ.pop("TOKENIZERS_PARALLELISM", None)
        try:
            from src.services.search_service import (
                SentenceTransformersProvider,
            )

            with patch(
                "sentence_transformers.SentenceTransformer"
            ) as mock_st:
                mock_model = MagicMock()
                mock_model.get_sentence_embedding_dimension.return_value = 384
                mock_st.return_value = mock_model

                SentenceTransformersProvider(model="test-model")

                assert os.environ.get("TOKENIZERS_PARALLELISM") == "false"
        finally:
            # Restore original value
            if old_val is not None:
                os.environ["TOKENIZERS_PARALLELISM"] = old_val
            else:
                os.environ.pop("TOKENIZERS_PARALLELISM", None)

    def test_omp_num_threads_set_before_import(self):
        """OMP_NUM_THREADS must be '1' after provider init."""
        old_val = os.environ.pop("OMP_NUM_THREADS", None)
        try:
            from src.services.search_service import SentenceTransformersProvider

            with patch("sentence_transformers.SentenceTransformer") as mock_st:
                mock_model = MagicMock()
                mock_model.get_sentence_embedding_dimension.return_value = 384
                mock_st.return_value = mock_model

                SentenceTransformersProvider(model="test-model")

                assert os.environ.get("OMP_NUM_THREADS") == "1"
        finally:
            if old_val is not None:
                os.environ["OMP_NUM_THREADS"] = old_val
            else:
                os.environ.pop("OMP_NUM_THREADS", None)

    def test_setdefault_does_not_override_existing(self):
        """If the user already set OMP_NUM_THREADS, the provider must not override."""
        old_val = os.environ.get("OMP_NUM_THREADS")
        try:
            os.environ["OMP_NUM_THREADS"] = "4"

            from src.services.search_service import SentenceTransformersProvider

            with patch("sentence_transformers.SentenceTransformer") as mock_st:
                mock_model = MagicMock()
                mock_model.get_sentence_embedding_dimension.return_value = 384
                mock_st.return_value = mock_model

                SentenceTransformersProvider(model="test-model")

                # Must NOT have overwritten the user's custom value
                assert os.environ.get("OMP_NUM_THREADS") == "4"
        finally:
            if old_val is not None:
                os.environ["OMP_NUM_THREADS"] = old_val
            else:
                os.environ.pop("OMP_NUM_THREADS", None)
