#!/usr/bin/env python3
"""Record real embedding replies for the embeddings' tests (Sprint 136, DEC-187 point 4).

For each provider kind whose key is in the environment (GEMINI_API_KEY,
OPENAI_API_KEY; AKASHA_RECS_EMBEDDINGS_URL and AKASHA_RECS_EMBEDDINGS_MODEL for an
OpenAI-compatible endpoint other than OpenAI's, such as Voyage), this embeds the six
books of `backend/tests/embedding_library.py` -- the exact texts listed in
`embedding_fixtures.json` -- through the application's own adapter, writes the
provider's raw reply over its fixture, and marks it `"recorded": true`. A provider
without a key is skipped and keeps its documented-shape fixture.

The key is read from the environment only, sent as a header by the adapter, and
never printed or written: the script checks every reply for it. One request per
provider, six short texts (a fraction of a cent).

Run from backend/:

    GEMINI_API_KEY=... uv run python ../scripts/record_embedding_fixtures.py [--only gemini]

Then rerun `uv run pytest tests/test_embeddings.py tests/test_library_source.py`. It
prints the order a real model puts the waiting books in from Rayuela; if it differs
from `NEAREST_TO_RAYUELA`, change that list deliberately, in its own commit
(tests/fixtures/providers/README.md: never re-record silently).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from datetime import date
from pathlib import Path

import httpx

from book_tracker.infrastructure.embedding_clients import build_embedding_client
from book_tracker.infrastructure.providers import create_provider_client

BACKEND = Path(__file__).resolve().parents[1] / "backend"
FIXTURES = BACKEND / "tests" / "fixtures" / "providers"
SIDECAR = FIXTURES / "embedding_fixtures.json"
KEYS = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}
FILES = {
    "gemini": "embeddings_gemini_batch_library.json",
    "openai": "embeddings_openai_library.json",
}


class Capture(httpx.AsyncBaseTransport):
    """Passes each request to the network and keeps the raw reply body."""

    def __init__(self) -> None:
        self.inner = httpx.AsyncHTTPTransport()
        self.bodies: list[tuple[int, bytes]] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self.inner.handle_async_request(request)
        body = await response.aread()
        self.bodies.append((response.status_code, body))
        headers = [
            (name, value)
            for name, value in response.headers.items()
            if name.lower() not in ("content-encoding", "content-length", "transfer-encoding")
        ]
        return httpx.Response(response.status_code, headers=headers, content=body, request=request)


def _order(texts: list[str], vectors: list[list[float]]) -> list[str]:
    def unit(vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    seed, *rest = [unit(vector) for vector in vectors]
    scored = sorted(
        zip(texts[1:], rest, strict=True),
        key=lambda pair: -sum(a * b for a, b in zip(seed, pair[1], strict=True)),
    )
    return [body.split("\n", 1)[0] for body, _vector in scored]


async def record(provider: str, key: str, texts: list[str]) -> bool:
    capture = Capture()
    client = build_embedding_client(
        create_provider_client(capture),
        provider,
        key,
        os.environ.get("AKASHA_RECS_EMBEDDINGS_MODEL", "") if provider == "openai" else "",
        os.environ.get("AKASHA_RECS_EMBEDDINGS_URL", "") if provider == "openai" else "",
    )
    try:
        vectors = await client.embed(texts)
    except Exception as error:  # noqa: BLE001 - reported, never with the key
        status = capture.bodies[-1][0] if capture.bodies else "no answer"
        print(f"{provider}: failed ({type(error).__name__}: {error}; HTTP {status})")
        return False
    status, body = capture.bodies[-1]
    if key.encode() in body:
        print(f"{provider}: the reply echoes the key; not written")
        return False
    target = FIXTURES / FILES[provider]
    target.write_text(json.dumps(json.loads(body), separators=(",", ":")) + "\n", "utf-8")
    print(
        f"{provider}: HTTP {status}, {client.identity}, {len(vectors)} x {len(vectors[0])};"
        f" nearest to Rayuela: {_order(texts, vectors)}"
    )
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", choices=sorted(KEYS), action="append")
    args = parser.parse_args()
    sidecar = json.loads(SIDECAR.read_text(encoding="utf-8"))
    texts = list(sidecar["texts"])
    recorded_any = False
    for provider in args.only or sorted(KEYS):
        key = os.environ.get(KEYS[provider], "").strip()
        if not key:
            print(f"{provider}: no {KEYS[provider]} in the environment; fixture left unrecorded")
            continue
        if await record(provider, key, texts):
            row = sidecar["files"][FILES[provider]]
            row["recorded"] = True
            row["recorded_on"] = date.today().isoformat()
            recorded_any = True
    if recorded_any:
        sidecar["recorded"] = all(
            row["recorded"] for name, row in sidecar["files"].items() if name in FILES.values()
        )
        SIDECAR.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
