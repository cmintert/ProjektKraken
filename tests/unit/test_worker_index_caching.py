"""Provider snapshots are initialized and reused by the inference runner."""

from threading import Event
from unittest.mock import MagicMock

import numpy as np

from src.services.semantic_index_task import EmbeddingRunner


def test_runner_reuses_provider_and_captured_configuration(monkeypatch):
    provider = MagicMock()
    provider.get_model_name.return_value = "test:model"
    provider.get_dimension.return_value = 3
    provider.embed.return_value = np.ones((1, 3))
    create = MagicMock(return_value=provider)
    monkeypatch.setattr("src.services.semantic_index_task.create_provider", create)
    settings = {
        "provider": "lmstudio",
        "lm_model": "saved-model",
        "st_model": "",
        "lm_url": "http://localhost:1234",
        "lm_api_key": "",
        "lm_timeout": 10,
    }
    runner = EmbeddingRunner(settings, Event())
    assert runner.run([])["dimension"] == 3
    assert runner.run(["Text"])["model"] == "test:model"
    create.assert_called_once()
    assert create.call_args.kwargs["model"] == "saved-model"
    assert create.call_args.kwargs["settings"] == settings
    provider.embed.assert_called_once_with(["Text"])


def test_cancelled_runner_never_loads_model(monkeypatch):
    create = MagicMock()
    monkeypatch.setattr("src.services.semantic_index_task.create_provider", create)
    cancelled = Event()
    cancelled.set()
    assert EmbeddingRunner({}, cancelled).run(["ignored"]) == {"cancelled": True}
    create.assert_not_called()
