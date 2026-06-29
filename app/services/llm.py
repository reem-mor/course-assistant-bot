"""Multi-provider model registry (Section 7).

Maps a task ``role`` to a (provider, model) pair, read from config so any role can be
re-pointed without code changes. Provider adapters are built lazily and only for providers
whose API key is set; if a role's configured provider is unavailable the registry falls
back to any available provider and logs it, and only raises when no provider is configured.

All real provider calls happen behind the ``ChatModel`` protocol and are mocked in tests.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

from app.core.errors import ConfigurationError
from app.core.logging import get_logger
from app.core.settings import Settings, get_settings

_log = get_logger("llm")


class ModelRole(StrEnum):
    """Task roles that map to specific models in the registry (Section 7)."""

    ROUTER = "router"
    CONVERSATIONAL = "conversational"
    SUMMARIZER = "summarizer"
    EMAIL_WRITER = "email_writer"
    RECOMMENDATIONS = "recommendations"
    SCAFFOLD = "scaffold"
    EMBEDDINGS = "embeddings"


class Provider(StrEnum):
    """Supported chat-LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


@runtime_checkable
class ChatModel(Protocol):
    """Minimal provider-agnostic chat completion contract."""

    async def complete(self, *, system: str, prompt: str, max_tokens: int) -> str: ...


@runtime_checkable
class ModelRegistry(Protocol):
    """Resolves a role to a concrete chat model, with fallback."""

    def for_role(self, role: ModelRole) -> ChatModel: ...


# Section 7 defaults (treated as config; names churn). role -> (provider, model).
_DEFAULTS: dict[ModelRole, tuple[Provider, str]] = {
    ModelRole.ROUTER: (Provider.OPENAI, "gpt-5.4-nano"),
    ModelRole.CONVERSATIONAL: (Provider.OPENAI, "gpt-5.4-mini"),
    ModelRole.SUMMARIZER: (Provider.ANTHROPIC, "claude-sonnet-4-6"),
    ModelRole.EMAIL_WRITER: (Provider.ANTHROPIC, "claude-sonnet-4-6"),
    ModelRole.RECOMMENDATIONS: (Provider.OPENAI, "gpt-5.4"),
    ModelRole.SCAFFOLD: (Provider.ANTHROPIC, "claude-sonnet-4-6"),
}

# A reasonable default chat model per provider, used when falling back across providers.
_FALLBACK_MODEL: dict[Provider, str] = {
    Provider.ANTHROPIC: "claude-sonnet-4-6",
    Provider.OPENAI: "gpt-5.4-mini",
    Provider.GOOGLE: "gemini-3.1-flash",
}

# Preference order when choosing a fallback provider.
_PROVIDER_PREFERENCE: tuple[Provider, ...] = (
    Provider.ANTHROPIC,
    Provider.OPENAI,
    Provider.GOOGLE,
)

_ROLE_ENV_OVERRIDE: dict[ModelRole, str] = {
    ModelRole.ROUTER: "model_router",
    ModelRole.CONVERSATIONAL: "model_conversational",
    ModelRole.SUMMARIZER: "model_summarizer",
    ModelRole.EMAIL_WRITER: "model_email_writer",
    ModelRole.RECOMMENDATIONS: "model_recommendations",
}


class AnthropicChatModel:
    """ChatModel adapter over the async Anthropic SDK."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client: Any = None

    def _ensure(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def complete(self, *, system: str, prompt: str, max_tokens: int) -> str:
        client = self._ensure()
        resp = await client.messages.create(
            model=self._model,
            system=system,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return str(resp.content[0].text)


class OpenAIChatModel:
    """ChatModel adapter over the async OpenAI SDK."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client: Any = None

    def _ensure(self) -> Any:
        if self._client is None:
            import openai

            self._client = openai.AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def complete(self, *, system: str, prompt: str, max_tokens: int) -> str:
        client = self._ensure()
        resp = await client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return str(resp.choices[0].message.content or "")


class GoogleChatModel:
    """ChatModel adapter over the async google-genai SDK."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client: Any = None

    def _ensure(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def complete(self, *, system: str, prompt: str, max_tokens: int) -> str:
        client = self._ensure()
        resp = await client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config={"system_instruction": system, "max_output_tokens": max_tokens},
        )
        return str(resp.text or "")


def _available_providers(settings: Settings) -> dict[Provider, str]:
    """Return provider -> api_key for every configured chat provider."""
    available: dict[Provider, str] = {}
    if settings.anthropic_api_key:
        available[Provider.ANTHROPIC] = settings.anthropic_api_key.get_secret_value()
    if settings.openai_api_key:
        available[Provider.OPENAI] = settings.openai_api_key.get_secret_value()
    if settings.google_api_key:
        available[Provider.GOOGLE] = settings.google_api_key.get_secret_value()
    return available


def _parse_override(value: str) -> tuple[Provider, str] | None:
    """Parse a 'provider:model' override into (Provider, model)."""
    if ":" not in value:
        return None
    provider_str, model = value.split(":", 1)
    try:
        return Provider(provider_str.strip().lower()), model.strip()
    except ValueError:
        return None


def _build_adapter(provider: Provider, model: str, api_key: str) -> ChatModel:
    if provider is Provider.ANTHROPIC:
        return AnthropicChatModel(api_key, model)
    if provider is Provider.OPENAI:
        return OpenAIChatModel(api_key, model)
    return GoogleChatModel(api_key, model)


class DefaultModelRegistry:
    """Resolves roles to provider-backed chat models with graceful fallback."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._available = _available_providers(settings)
        self._cache: dict[ModelRole, ChatModel] = {}

    @property
    def has_provider(self) -> bool:
        """True if any chat provider is configured."""
        return bool(self._available)

    def _target_for(self, role: ModelRole) -> tuple[Provider, str]:
        env_attr = _ROLE_ENV_OVERRIDE.get(role)
        if env_attr is not None:
            raw = getattr(self._settings, env_attr, None)
            if raw:
                parsed = _parse_override(raw)
                if parsed is not None:
                    return parsed
        return _DEFAULTS.get(role, _DEFAULTS[ModelRole.CONVERSATIONAL])

    def for_role(self, role: ModelRole) -> ChatModel:
        """Return a chat model for the role, falling back across providers."""
        if role in self._cache:
            return self._cache[role]
        if not self._available:
            raise ConfigurationError(
                "No LLM provider is configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, "
                "or GOOGLE_API_KEY."
            )
        provider, model = self._target_for(role)
        if provider not in self._available:
            fallback = next(p for p in _PROVIDER_PREFERENCE if p in self._available)
            _log.warning(
                "model_provider_fallback",
                role=role,
                requested=provider,
                using=fallback,
            )
            provider, model = fallback, _FALLBACK_MODEL[fallback]
        adapter = _build_adapter(provider, model, self._available[provider])
        self._cache[role] = adapter
        return adapter


@lru_cache(maxsize=1)
def get_model_registry() -> DefaultModelRegistry:
    """Return a cached registry built from settings."""
    return DefaultModelRegistry(get_settings())


def try_get_model_registry() -> DefaultModelRegistry | None:
    """Return the registry, or None if no provider is configured."""
    registry = get_model_registry()
    return registry if registry.has_provider else None
