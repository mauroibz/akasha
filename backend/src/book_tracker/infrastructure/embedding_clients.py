"""Hosted embedding endpoints behind one port (Sprint 136, DEC-187 point 3).

An item's stored text (title, creator, year and what its domain declares as
descriptive) goes in; one vector per text comes out. Which API answers is
configuration: Gemini's `batchEmbedContents`, or any OpenAI-compatible
`/embeddings` endpoint (OpenAI itself, Voyage, a server elsewhere). The Claude API
has no embeddings endpoint, so with only a Claude key embeddings are off.

Each adapter is a thin HTTP call over the app's shared provider client, through
`model_clients._post` (the byte bound, the retry policy, the failures mapped to a
`SourceError`), so no SDK is added. The key travels in a header only and appears in
no message. Nothing here runs a model locally (the owner, 2026-11-23).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

import httpx

from book_tracker.domain.recommendations import SourceError
from book_tracker.infrastructure.model_clients import _post
from book_tracker.infrastructure.providers import INTERACTIVE_ATTEMPTS

GEMINI = "gemini"
OPENAI = "openai"
PROVIDERS = (GEMINI, OPENAI)

#: Each kind's default model. Gemini's current general embedding model, asked for
#: `GEMINI_DIMENSIONS` (it is trained to be cut short); OpenAI's small model at its
#: own 1,536. `AKASHA_RECS_EMBEDDINGS_MODEL` overrides either (Voyage: `voyage-3.5`).
DEFAULT_MODELS: Mapping[str, str] = {
    GEMINI: "gemini-embedding-001",
    OPENAI: "text-embedding-3-small",
}
PROVIDER_LABELS: Mapping[str, str] = {GEMINI: "Gemini", OPENAI: "OpenAI-compatible"}
#: 768 keeps a 10,000-item library's similarity under the 300 ms budget in plain
#: Python (measured: about 130 ms at 768, 230 ms at 1,536 on the workstation).
GEMINI_DIMENSIONS = 768
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
OPENAI_URL = "https://api.openai.com/v1"
#: Texts per request. 32 vectors of 1,536 floats written as JSON is about 0.75 MB,
#: well inside the shared client's 2 MB bound; Gemini allows 100, OpenAI 2,048.
BATCH_SIZE = 32
#: An embedding request is quick, but a batch is not instant; the shared 5 s is short.
EMBEDDING_TIMEOUT_SECONDS = 30.0
#: What a refusal tells a person to check.
_KEY_SETTING = "AKASHA_RECS_EMBEDDINGS_KEY"
_MODEL_SETTING = "AKASHA_RECS_EMBEDDINGS_MODEL"


@runtime_checkable
class EmbeddingClient(Protocol):
    """One hosted embedding model: texts in, one vector per text out, in order."""

    provider: str
    model: str

    @property
    def identity(self) -> str:
        """What a stored vector records it came from; vectors of two identities never mix."""
        ...

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def _malformed(provider: str) -> SourceError:
    return SourceError(
        f"{PROVIDER_LABELS.get(provider, provider)} answered something other than"
        " one vector per text",
        code="malformed",
    )


def _vector(value: object, provider: str) -> list[float]:
    if not isinstance(value, list) or not value:
        raise _malformed(provider)
    try:
        return [float(number) for number in value]
    except (TypeError, ValueError):
        raise _malformed(provider) from None


async def _post_embeddings(
    client: httpx.AsyncClient,
    provider: str,
    url: str,
    headers: Mapping[str, str],
    body: Mapping[str, Any],
    attempts: int,
) -> Mapping[str, Any]:
    return await _post(
        client,
        provider,
        url,
        headers,
        body,
        attempts,
        timeout=EMBEDDING_TIMEOUT_SECONDS,
        key_setting=_KEY_SETTING,
        model_setting=_MODEL_SETTING,
    )


class GeminiEmbeddings:
    """Gemini's `models/{model}:batchEmbedContents`, key in `x-goog-api-key`.

    One request carries every text as its own `EmbedContentRequest`, asked for
    `SEMANTIC_SIMILARITY` at `GEMINI_DIMENSIONS`; the reply is `embeddings[].values`
    in the order asked.
    """

    provider = GEMINI

    def __init__(
        self,
        client: httpx.AsyncClient,
        key: str,
        model: str = DEFAULT_MODELS[GEMINI],
        *,
        url: str = GEMINI_URL,
        dimensions: int = GEMINI_DIMENSIONS,
        attempts: int = INTERACTIVE_ATTEMPTS,
    ) -> None:
        self.client = client
        self._key = key
        self.model = model
        self.url = url
        self.dimensions = dimensions
        self.attempts = attempts

    def __repr__(self) -> str:  # never the key
        return f"GeminiEmbeddings(model={self.model!r})"

    @property
    def identity(self) -> str:
        return f"{self.provider}:{self.model}@{self.dimensions}"

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        body = await _post_embeddings(
            self.client,
            self.provider,
            self.url.format(model=self.model),
            {"x-goog-api-key": self._key},
            {
                "requests": [
                    {
                        "model": f"models/{self.model}",
                        "content": {"parts": [{"text": text}]},
                        "taskType": "SEMANTIC_SIMILARITY",
                        "outputDimensionality": self.dimensions,
                    }
                    for text in texts
                ]
            },
            self.attempts,
        )
        rows = body.get("embeddings")
        if not isinstance(rows, list) or len(rows) != len(texts):
            raise _malformed(self.provider)
        return [
            _vector(row.get("values") if isinstance(row, Mapping) else None, self.provider)
            for row in rows
        ]


class OpenAICompatibleEmbeddings:
    """`POST {base}/embeddings` with a Bearer key: OpenAI, Voyage and their look-alikes.

    Only `model` and `input` are sent, which every compatible server accepts (a
    `dimensions` or `encoding_format` some refuse); the reply is `data[].embedding`,
    put back in order by each row's `index`.
    """

    provider = OPENAI

    def __init__(
        self,
        client: httpx.AsyncClient,
        key: str,
        model: str = DEFAULT_MODELS[OPENAI],
        *,
        url: str = OPENAI_URL,
        attempts: int = INTERACTIVE_ATTEMPTS,
    ) -> None:
        self.client = client
        self._key = key
        self.model = model
        self.url = (url or OPENAI_URL).rstrip("/")
        self.attempts = attempts

    def __repr__(self) -> str:  # never the key
        return f"OpenAICompatibleEmbeddings(model={self.model!r}, url={self.url!r})"

    @property
    def identity(self) -> str:
        # The endpoint is part of it: two servers may name different models alike.
        return f"{self.provider}:{self.model}@{self.url}"

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        body = await _post_embeddings(
            self.client,
            self.provider,
            f"{self.url}/embeddings",
            {"Authorization": f"Bearer {self._key}"},
            {"model": self.model, "input": list(texts)},
            self.attempts,
        )
        rows = body.get("data")
        if not isinstance(rows, list) or len(rows) != len(texts):
            raise _malformed(self.provider)
        ordered: list[list[float] | None] = [None] * len(texts)
        for position, row in enumerate(rows):
            if not isinstance(row, Mapping):
                raise _malformed(self.provider)
            index = row.get("index", position)
            if not isinstance(index, int) or not 0 <= index < len(texts) or ordered[index]:
                raise _malformed(self.provider)
            ordered[index] = _vector(row.get("embedding"), self.provider)
        return [vector for vector in ordered if vector is not None]


def build_embedding_client(
    http: httpx.AsyncClient, provider: str, key: str, model: str = "", url: str = ""
) -> EmbeddingClient:
    """The adapter configuration names, with its default model when none is set."""
    chosen = model.strip() or DEFAULT_MODELS[provider]
    if provider == OPENAI:
        return OpenAICompatibleEmbeddings(http, key, chosen, url=url.strip() or OPENAI_URL)
    return GeminiEmbeddings(http, key, chosen)
