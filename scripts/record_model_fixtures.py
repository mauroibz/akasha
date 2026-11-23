#!/usr/bin/env python3
"""Record real model replies for the model source's tests (Sprint 135, DEC-187 point 4).

For each provider kind whose key is in the environment (ANTHROPIC_API_KEY,
GEMINI_API_KEY, OPENAI_API_KEY; AKASHA_RECS_MODEL_URL for an OpenAI-compatible
endpoint other than OpenAI's), this asks the same question the tests replay -- more
books like *Rayuela*, with a short taste profile -- through the application's own
adapter, writes the provider's raw reply over its fixture, and marks it
`"recorded": true` in `model_fixtures.json`. A provider without a key is skipped and
keeps its documented-shape fixture.

The key is read from the environment only, sent as a header by the adapter, and
never printed or written: the script checks every file it writes for it. One round
costs one request per provider (well under a cent on the default models).

Run from backend/:

    ANTHROPIC_API_KEY=... uv run python ../scripts/record_model_fixtures.py [--only anthropic]

Then rerun `uv run pytest tests/test_model_recommendations.py`. A real reply may name
other books than the documented one did; if so the test's expected titles and the
recorded Open Library searches change with it, deliberately and in their own commit
(tests/fixtures/providers/README.md: never re-record silently).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import date
from pathlib import Path

import httpx

from book_tracker.domain.recommendations import Seed, TasteEntry, TasteProfile
from book_tracker.infrastructure.model_clients import build_model_client
from book_tracker.infrastructure.model_recommendations import (
    MAX_SUGGESTIONS,
    build_prompt,
    parse_reply,
)
from book_tracker.infrastructure.providers import create_provider_client

FIXTURES = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures" / "providers"
SIDECAR = FIXTURES / "model_fixtures.json"
KEYS = {"anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}
FILES = {
    "anthropic": "model_anthropic_messages_rayuela.json",
    "gemini": "model_gemini_generate_content_rayuela.json",
    "openai": "model_openai_chat_completions_rayuela.json",
}

SEED = Seed(
    item_type="book",
    entry_id=1,
    title="Rayuela",
    year=1963,
    creators=("Julio Cortázar",),
    options={"kind": "books", "creator": "author"},
)
PROFILE = TasteProfile(
    item_type="book",
    top_scored=(
        TasteEntry("Rayuela", 1963, "Julio Cortázar", 9),
        TasteEntry("Bestiario", 1951, "Julio Cortázar", 8),
    ),
)


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


async def record(provider: str, key: str) -> bool:
    capture = Capture()
    client = build_model_client(
        create_provider_client(capture),
        provider,
        key,
        os.environ.get("AKASHA_RECS_MODEL", ""),
        os.environ.get("AKASHA_RECS_MODEL_URL", "") if provider == "openai" else "",
    )
    system, prompt = build_prompt(SEED, PROFILE, MAX_SUGGESTIONS)
    try:
        reply = await client.complete(system, prompt)
    except Exception as error:  # noqa: BLE001 - reported, never with the key
        status = capture.bodies[-1][0] if capture.bodies else "no answer"
        print(f"{provider}: failed ({type(error).__name__}: {error}; HTTP {status})")
        return False
    status, body = capture.bodies[-1]
    if key.encode() in body:
        print(f"{provider}: the reply echoes the key; not written")
        return False
    decoded = json.loads(body)
    target = FIXTURES / FILES[provider]
    target.write_text(json.dumps(decoded, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    titles = [candidate.title for candidate in parse_reply(reply, MAX_SUGGESTIONS)]
    print(f"{provider}: HTTP {status}, model {client.model}, {len(titles)} picks: {titles}")
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", choices=sorted(KEYS), action="append")
    args = parser.parse_args()
    sidecar = json.loads(SIDECAR.read_text(encoding="utf-8"))
    recorded_any = False
    for provider in args.only or sorted(KEYS):
        key = os.environ.get(KEYS[provider], "").strip()
        if not key:
            print(f"{provider}: no {KEYS[provider]} in the environment; fixture left unrecorded")
            continue
        if await record(provider, key):
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
