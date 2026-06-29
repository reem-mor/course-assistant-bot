"""Unit tests for the model registry: provider selection and fallback."""

from __future__ import annotations

import pytest
from app.core.errors import ConfigurationError
from app.core.settings import Settings
from app.services.llm import (
    AnthropicChatModel,
    DefaultModelRegistry,
    ModelRole,
    OpenAIChatModel,
)


def test_configured_provider_selected() -> None:
    settings = Settings(anthropic_api_key="a")  # type: ignore[arg-type]
    registry = DefaultModelRegistry(settings)
    model = registry.for_role(ModelRole.SUMMARIZER)  # default provider anthropic
    assert isinstance(model, AnthropicChatModel)


def test_falls_back_when_provider_key_missing() -> None:
    # Summarizer defaults to anthropic; only openai is configured -> fallback to openai.
    settings = Settings(openai_api_key="o")  # type: ignore[arg-type]
    registry = DefaultModelRegistry(settings)
    model = registry.for_role(ModelRole.SUMMARIZER)
    assert isinstance(model, OpenAIChatModel)


def test_no_provider_raises() -> None:
    registry = DefaultModelRegistry(Settings())
    assert not registry.has_provider
    with pytest.raises(ConfigurationError):
        registry.for_role(ModelRole.ROUTER)


def test_env_override_repoints_role() -> None:
    settings = Settings(openai_api_key="o", model_summarizer="openai:custom-model")  # type: ignore[arg-type]
    registry = DefaultModelRegistry(settings)
    model = registry.for_role(ModelRole.SUMMARIZER)
    assert isinstance(model, OpenAIChatModel)
    assert model._model == "custom-model"


def test_role_model_is_cached() -> None:
    registry = DefaultModelRegistry(Settings(openai_api_key="o"))  # type: ignore[arg-type]
    first = registry.for_role(ModelRole.ROUTER)
    second = registry.for_role(ModelRole.ROUTER)
    assert first is second
