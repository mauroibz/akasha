"""Embedding endpoints replayed in their documented shapes (Sprint 136, DEC-187 point 4).

`fixture_transport` answers the committed reply for the six books of
`embedding_library.py`, and refuses any request whose texts are not exactly the ones
the fixture was written for. `worded_transport` answers any texts with a vector made
from their words (each word adds to a few hashed dimensions), so that texts sharing
words are alike; it stands in for a hosted model where a test needs arbitrary texts
and a stable answer, and is never a model run locally.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Sequence
from typing import Any

import httpx
from recordings import FIXTURES, recording

GEMINI_PATH = "/v1beta/models/gemini-embedding-001:batchEmbedContents"
OPENAI_PATH = "/v1/embeddings"
FILES = {
    "gemini": "embeddings_gemini_batch_library.json",
    "openai": "embeddings_openai_library.json",
}
_WORD = re.compile(r"\w+", re.UNICODE)


def fixture_texts() -> list[str]:
    sidecar = json.loads((FIXTURES / "embedding_fixtures.json").read_text(encoding="utf-8"))
    return list(sidecar["texts"])


def texts_of(request: httpx.Request) -> list[str]:
    body = json.loads(request.content)
    if "requests" in body:
        return [row["content"]["parts"][0]["text"] for row in body["requests"]]
    return list(body["input"])


def worded_vector(text: str, dims: int = 64) -> list[float]:
    vector = [0.0] * dims
    for word in _WORD.findall(text.casefold()):
        digest = hashlib.sha256(word.encode()).digest()
        for offset in range(3):
            index = int.from_bytes(digest[offset * 4 : offset * 4 + 4], "big") % dims
            vector[index] += 1.0 if digest[12 + offset] % 2 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def shaped(provider: str, vectors: Sequence[Sequence[float]]) -> dict[str, Any]:
    if provider == "gemini":
        return {"embeddings": [{"values": list(vector)} for vector in vectors]}
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": index, "embedding": list(vector)}
            for index, vector in enumerate(vectors)
        ],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    }


class Endpoint:
    """One provider kind's endpoint, keeping every request it was sent."""

    def __init__(self, provider: str, *, worded: bool = False, status: int = 200) -> None:
        self.provider = provider
        self.worded = worded
        self.status = status
        self.requests: list[httpx.Request] = []

    @property
    def batches(self) -> list[list[str]]:
        return [texts_of(request) for request in self.requests]

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json=recording("embeddings_openai_error_401.json"))
        texts = texts_of(request)
        if self.worded:
            return httpx.Response(
                200, json=shaped(self.provider, [worded_vector(text) for text in texts])
            )
        if texts != fixture_texts():
            raise AssertionError(f"no recording for these texts: {texts}")
        return httpx.Response(200, json=recording(FILES[self.provider]))

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)
