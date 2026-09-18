"""Gemini embeddings: batchEmbedContents, estimated tokens, no fallback model."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

import httpx
import httpx2

from mdcopilot_blog.llm.routes import parse_choice
from mdcopilot_blog.settings import Settings

EMBED_BATCH_SIZE: Final = 100
EMBED_TIMEOUT_SECONDS: Final = 30.0

_RETRYABLE_STATUS: Final = frozenset({408, 429})


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    provider: str
    model: str
    input_tokens: int
    usage_details: dict[str, str | int | None]


class EmbeddingProviderError(RuntimeError):
    """An embedding provider call failed; picklable so DBOS steps can carry it."""

    def __init__(self, provider: str, error_class: str, status_code: int | None, message: str, retryable: bool) -> None:
        super().__init__(provider, error_class, status_code, message, retryable)
        self.provider = provider
        self.error_class = error_class
        self.status_code = status_code
        self.message = message
        self.retryable = retryable

    def __str__(self) -> str:
        prefix = (
            f"{self.error_class} (HTTP {self.status_code}): "
            if self.status_code is not None
            else f"{self.error_class}: "
        )
        return f"{prefix}{self.message}"

    def __reduce__(self) -> tuple[object, ...]:
        return (
            EmbeddingProviderError,
            (self.provider, self.error_class, self.status_code, self.message, self.retryable),
        )


def estimate_embedding_tokens(text: str) -> int:
    """Gemini returns no token usage for embeddings: ceil(chars / 4), at least 1."""
    return max(1, math.ceil(len(text) / 4))


def batched(texts: Sequence[str], size: int) -> list[list[str]]:
    return [list(texts[start : start + size]) for start in range(0, len(texts), size)]


class GeminiEmbeddingProvider:
    """``batchEmbedContents`` with one vector per text; the gateway owns pricing."""

    name = "google"
    model: str

    def __init__(self, settings: Settings) -> None:
        choice = parse_choice(settings.embedding_model)
        if choice.provider != "google":
            from mdcopilot_blog.llm.gateway import ProviderNotAvailable

            raise ProviderNotAvailable(f"embedding model must be a google: entry, got '{choice.ref()}'")
        if settings.gemini_api_key is None:
            from mdcopilot_blog.llm.gateway import ProviderNotAvailable

            raise ProviderNotAvailable("GEMINI_API_KEY is not set")
        from google import genai
        from google.genai import types

        self.model = choice.model
        self._client = genai.Client(
            vertexai=False,
            api_key=settings.gemini_api_key.get_secret_value(),
            http_options=types.HttpOptions(
                httpx_async_client=httpx2.AsyncClient(timeout=httpx2.Timeout(EMBED_TIMEOUT_SECONDS)),
                retry_options=types.HttpRetryOptions(attempts=1),
                timeout=int(EMBED_TIMEOUT_SECONDS * 1000),
            ),
        )

    async def embed(self, texts: Sequence[str], *, dimensions: int) -> EmbeddingBatch:
        if not texts:
            raise ValueError("texts must not be empty")
        from google.genai import types

        try:
            contents: Any = [types.Content(parts=[types.Part(text=text)]) for text in texts]
            response = await self._client.aio.models.embed_content(
                model=self.model,
                contents=contents,
                config=types.EmbedContentConfig(output_dimensionality=dimensions),
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

        embeddings = response.embeddings or []
        values: list[list[float] | None] = [e.values for e in embeddings]
        if (
            len(embeddings) != len(texts)
            or any(v is None for v in values)
            or any(v is not None and len(v) != dimensions for v in values)
        ):
            raise EmbeddingProviderError(
                "google",
                "UnexpectedEmbeddingShape",
                None,
                f"expected {len(texts)} vectors of {dimensions} dimensions, "
                f"got {len(embeddings)} with lengths {[len(v) if v is not None else None for v in values]}",
                retryable=False,
            )

        metadata = getattr(response, "metadata", None)
        billable = getattr(metadata, "billable_character_count", None) if metadata is not None else None
        return EmbeddingBatch(
            vectors=[v for v in values if v is not None],
            provider="google",
            model=self.model,
            input_tokens=sum(estimate_embedding_tokens(text) for text in texts),
            usage_details={
                "token_source": "estimate_chars_div_4",
                "billable_character_count": billable,
            },
        )

    def _map_error(self, exc: Exception) -> Exception:
        from google.genai import errors as genai_errors

        if isinstance(exc, genai_errors.APIError):
            code = getattr(exc, "code", None)
            retryable = code is not None and (code in _RETRYABLE_STATUS or code >= 500)
            return EmbeddingProviderError("google", type(exc).__name__, code, str(exc)[:500], retryable=retryable)
        if isinstance(exc, httpx2.TransportError | httpx.TransportError):
            return EmbeddingProviderError("google", type(exc).__name__, None, str(exc)[:500], retryable=True)
        return exc
