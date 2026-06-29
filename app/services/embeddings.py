"""Embedding provider (OpenAI ``text-embedding-3-small``).

Behind the ``Embedder`` protocol so tests can substitute a deterministic fake. Built only
when an OpenAI key is configured.
"""

from __future__ import annotations

from typing import Any

from app.core.settings import Settings, get_settings
from app.services.vectorstore import Embedder


class OpenAIEmbedder:
    """Embedder backed by the OpenAI embeddings API."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client: Any = None

    def _ensure(self) -> Any:
        if self._client is None:
            import openai

            self._client = openai.AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._ensure()
        resp = await client.embeddings.create(model=self._model, input=texts)
        return [list(item.embedding) for item in resp.data]


def build_embedder(settings: Settings) -> Embedder | None:
    """Return an embedder if OpenAI is configured, else None."""
    if settings.openai_api_key is None:
        return None
    return OpenAIEmbedder(
        settings.openai_api_key.get_secret_value(), settings.embeddings_model
    )


def get_embedder() -> Embedder | None:
    """Return an embedder built from the current settings."""
    return build_embedder(get_settings())
