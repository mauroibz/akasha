"""Hosted language models behind one port (Sprint 135, DEC-187).

The `model` recommendation source asks a hosted model one question and reads one
answer. Which API answers is configuration: the Claude Messages API, Gemini's
`generateContent`, or any OpenAI-compatible `chat/completions` endpoint. Each adapter
here is a thin HTTP call over the app's shared provider client (its byte bound,
retry policy and streaming read), so no SDK is added for any of them: the same
prompt goes in, the reply's text comes out, and every failure is a `SourceError`
with a stable code and a message a person can act on.

**The key never leaves the request headers.** It is sent as a header (never in a URL,
which httpx logs), it appears in no exception message, and an error body from the
provider is not copied into a message either, because some echo the request.

Nothing here runs a model locally (the owner, 2026-11-23).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

import httpx

from book_tracker.domain.recommendations import SourceError
from book_tracker.infrastructure.providers import (
    INTERACTIVE_ATTEMPTS,
    ProviderPayloadError,
    bounded_json_object,
)

ANTHROPIC = "anthropic"
GEMINI = "gemini"
OPENAI = "openai"

#: The cheapest current model of each kind that writes a short JSON list well.
#: Claude's comes from the `claude-api` skill's model table (2026-11-23): Claude
#: Haiku 5.5, $0.10 / $0.50 per million tokens. The other two are the owner's to
#: confirm against their account; `AKASHA_RECS_MODEL` overrides any of them.
DEFAULT_MODELS: Mapping[str, str] = {
    ANTHROPIC: "claude-haiku-5-5",
    GEMINI: "gemini-2.5-flash",
    OPENAI: "gpt-5-mini",
}
#: What a screen calls each kind.
PROVIDER_LABELS: Mapping[str, str] = {
    ANTHROPIC: "Claude",
    GEMINI: "Gemini",
    OPENAI: "OpenAI-compatible",
}
#: Where each kind lives, unless configured otherwise.
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
#: The API version the `claude-api` skill documents for raw HTTP (2026-11-23).
ANTHROPIC_VERSION = "2026-10-21"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OPENAI_URL = "https://api.openai.com/v1"

#: A model writes for a while; the shared client's 5 s would cut most replies off.
MODEL_TIMEOUT_SECONDS = 60.0
#: Room for eight short suggestions and, on Claude, a little adaptive thinking.
MAX_OUTPUT_TOKENS = 4096

#: The answer's shape, for the APIs that can hold a reply to a schema (Claude's
#: structured outputs). Unknown fields are `0` and `""` rather than null: a plain
#: shape every provider's schema dialect accepts. The others are asked in the prompt.
REPLY_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "creator": {"type": "string"},
                    "year": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["title", "creator", "year", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["suggestions"],
    "additionalProperties": False,
}


@runtime_checkable
class ModelClient(Protocol):
    """One hosted model: a system prompt and a question in, the reply's text out."""

    provider: str
    model: str

    async def complete(self, system: str, prompt: str) -> str: ...


def _label(provider: str) -> str:
    return PROVIDER_LABELS.get(provider, provider)


async def _post(
    client: httpx.AsyncClient,
    provider: str,
    url: str,
    headers: Mapping[str, str],
    body: Mapping[str, Any],
    attempts: int,
) -> Mapping[str, Any]:
    """POST through the shared boundary, every failure mapped to a `SourceError`."""
    name = _label(provider)
    try:
        return await bounded_json_object(
            client,
            url,
            params={},
            headers={"Content-Type": "application/json", **headers},
            timeout=MODEL_TIMEOUT_SECONDS,
            attempts=attempts,
            method="POST",
            json_body=body,
        )
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        if status in (401, 403):
            raise SourceError(
                f"{name} refused the key; check AKASHA_RECS_MODEL_KEY", code="unauthorized"
            ) from None
        if status == 404:
            raise SourceError(
                f"{name} does not know that model; check AKASHA_RECS_MODEL", code="not_found"
            ) from None
        if status == 429:
            raise SourceError(
                f"{name} asked us to slow down, or the account is out of credit; try later",
                code="busy",
            ) from None
        if status == 400:
            raise SourceError(f"{name} refused the request (400)", code="refused") from None
        raise SourceError(f"{name} answered {status}", code="unavailable") from None
    except (httpx.TransportError, httpx.TimeoutException):
        raise SourceError(f"{name} could not be reached", code="unavailable") from None
    except ProviderPayloadError:
        raise SourceError(f"{name} answered something unreadable", code="malformed") from None


def _unreadable(provider: str) -> SourceError:
    return SourceError(f"{_label(provider)} answered without any text", code="malformed")


class AnthropicClient:
    """The Claude Messages API (`POST /v1/messages`), as the `claude-api` skill documents.

    Headers `x-api-key` and `anthropic-version`; the reply's `content` is a list of
    blocks, of which only `text` blocks are read (a `thinking` block may come first:
    Haiku 5.5 thinks adaptively by default, held low with `effort`). The answer is
    held to `REPLY_SCHEMA` with `output_config.format`. No sampling parameters are
    sent: the API version above refuses them.
    """

    provider = ANTHROPIC

    def __init__(
        self,
        client: httpx.AsyncClient,
        key: str,
        model: str = DEFAULT_MODELS[ANTHROPIC],
        *,
        url: str = ANTHROPIC_URL,
        attempts: int = INTERACTIVE_ATTEMPTS,
    ) -> None:
        self.client = client
        self._key = key
        self.model = model
        self.url = url
        self.attempts = attempts

    def __repr__(self) -> str:  # never the key
        return f"AnthropicClient(model={self.model!r})"

    async def complete(self, system: str, prompt: str) -> str:
        body = await _post(
            self.client,
            self.provider,
            self.url,
            {"x-api-key": self._key, "anthropic-version": ANTHROPIC_VERSION},
            {
                "model": self.model,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
                "output_config": {
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": REPLY_SCHEMA},
                },
            },
            self.attempts,
        )
        stop = body.get("stop_reason")
        if stop == "refusal":
            raise SourceError("Claude declined to answer", code="refused")
        blocks = body.get("content")
        texts = [
            block["text"]
            for block in (blocks if isinstance(blocks, list) else [])
            if isinstance(block, Mapping)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ]
        if not texts:
            raise _unreadable(self.provider)
        if stop == "max_tokens":
            raise SourceError("Claude's answer was cut off before it ended", code="malformed")
        return "".join(texts)


class GeminiClient:
    """Gemini's `models/{model}:generateContent`, key in `x-goog-api-key`.

    The reply is `candidates[0].content.parts[].text`; `responseMimeType` asks for
    JSON, and the prompt says which JSON.
    """

    provider = GEMINI

    def __init__(
        self,
        client: httpx.AsyncClient,
        key: str,
        model: str = DEFAULT_MODELS[GEMINI],
        *,
        url: str = GEMINI_URL,
        attempts: int = INTERACTIVE_ATTEMPTS,
    ) -> None:
        self.client = client
        self._key = key
        self.model = model
        self.url = url
        self.attempts = attempts

    def __repr__(self) -> str:  # never the key
        return f"GeminiClient(model={self.model!r})"

    async def complete(self, system: str, prompt: str) -> str:
        body = await _post(
            self.client,
            self.provider,
            self.url.format(model=self.model),
            {"x-goog-api-key": self._key},
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "maxOutputTokens": MAX_OUTPUT_TOKENS,
                },
            },
            self.attempts,
        )
        candidates = body.get("candidates")
        first = candidates[0] if isinstance(candidates, list) and candidates else None
        if not isinstance(first, Mapping):
            blocked = body.get("promptFeedback")
            if isinstance(blocked, Mapping) and blocked.get("blockReason"):
                raise SourceError("Gemini declined to answer", code="refused")
            raise _unreadable(self.provider)
        content = first.get("content")
        parts = content.get("parts") if isinstance(content, Mapping) else None
        texts = [
            part["text"]
            for part in (parts if isinstance(parts, list) else [])
            if isinstance(part, Mapping) and isinstance(part.get("text"), str)
        ]
        if not texts:
            if first.get("finishReason") in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"):
                raise SourceError("Gemini declined to answer", code="refused")
            raise _unreadable(self.provider)
        if first.get("finishReason") == "MAX_TOKENS":
            raise SourceError("Gemini's answer was cut off before it ended", code="malformed")
        return "".join(texts)


class OpenAICompatibleClient:
    """`POST {base}/chat/completions` with a Bearer key: OpenAI and its look-alikes.

    `response_format: json_object` is the JSON mode most compatible servers accept;
    the reply is `choices[0].message.content`. No token limit is sent, because
    OpenAI's newer models and older compatible servers disagree on its name.
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
        return f"OpenAICompatibleClient(model={self.model!r}, url={self.url!r})"

    async def complete(self, system: str, prompt: str) -> str:
        body = await _post(
            self.client,
            self.provider,
            f"{self.url}/chat/completions",
            {"Authorization": f"Bearer {self._key}"},
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            },
            self.attempts,
        )
        choices = body.get("choices")
        first = choices[0] if isinstance(choices, list) and choices else None
        message = first.get("message") if isinstance(first, Mapping) else None
        if not isinstance(message, Mapping):
            raise _unreadable(self.provider)
        if message.get("refusal"):
            raise SourceError("The model declined to answer", code="refused")
        text = message.get("content")
        if not isinstance(text, str) or not text.strip():
            raise _unreadable(self.provider)
        if isinstance(first, Mapping) and first.get("finish_reason") == "length":
            raise SourceError("The model's answer was cut off before it ended", code="malformed")
        return text


CLIENTS: Mapping[str, type[AnthropicClient] | type[GeminiClient] | type[OpenAICompatibleClient]] = {
    ANTHROPIC: AnthropicClient,
    GEMINI: GeminiClient,
    OPENAI: OpenAICompatibleClient,
}


def build_model_client(
    http: httpx.AsyncClient, provider: str, key: str, model: str = "", url: str = ""
) -> ModelClient:
    """The adapter configuration names, with its default model when none is set."""
    chosen = model.strip() or DEFAULT_MODELS[provider]
    if provider == OPENAI:
        return OpenAICompatibleClient(http, key, chosen, url=url.strip() or OPENAI_URL)
    return CLIENTS[provider](http, key, chosen)
