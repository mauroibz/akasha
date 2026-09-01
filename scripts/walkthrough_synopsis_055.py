"""Sprint 055's conditional walkthrough: enrich one real series, read its synopsis.

Deliverable 1 changed what a person sees on a series detail page, so the sprint's
own rule applies: run the flow against a live backend with the provider boundary
live, and read the synopsis that actually lands.

Adds the series through the real add path (search), lets the background
enrichment finish, and reads the stored synopsis back. BoJack Horseman is the
measured series from Sprint 053's record — Wikidata's description is the one-line
"serie de televisión animada" and TVmaze has a real synopsis.

    BOOK_TRACKER_BASE_URL=http://127.0.0.1:<port> \
    uv run python ../scripts/walkthrough_synopsis_055.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("BOOK_TRACKER_BASE_URL", "http://127.0.0.1:37555")
TIMEOUT_SECONDS = 60
FAILED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        FAILED.append(label)


def request(method: str, path: str, *, data: bytes | None = None) -> tuple[int, dict | list | None]:
    body = data if data is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(f"{BASE}{path}", data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
    except urllib.error.HTTPError as error:
        payload = error.read()
        return error.code, json.loads(payload) if payload else None


async def main() -> int:
    # 1. Add a real series through the add box's resolve path: an IMDb link.
    url = urllib.parse.quote("https://www.imdb.com/title/tt3398228/", safe="")
    status, rows = request("GET", f"/api/search/resolve?url={url}")
    check("resolve BoJack by its IMDb link", status == 200 and bool(rows), f"status {status}")
    if status != 200 or not rows:
        return 1
    candidate = rows[0] if isinstance(rows, list) else None
    assert candidate is not None
    print(f"    resolved: {candidate['title']!r} via {candidate['source']}")

    # 2. Add it as an entry, which creates the item and queues enrichment.
    status, added = request(
        "POST",
        "/api/entries",
        data=json.dumps({
            "source": candidate["source"],
            "source_id": candidate["source_id"],
            "status": "completed",
        }).encode(),
    )
    check("add 200/201", status in (200, 201), f"status {status}: {json.dumps(added)[:200] if added else ''}")
    if status not in (200, 201) or not isinstance(added, dict):
        return 1
    item_id = None
    if isinstance(added, dict):
        entry = added.get("entry") or {}
        item_id = (added.get("item") or {}).get("id") or entry.get("item_id") or added.get("item_id")
    print(f"    added item {item_id}")
    if item_id is None:
        check("the add response names the item", False, json.dumps(added)[:300])
        return 1

    # 3. Enrichment is a background job: poll until the synopsis arrives, bounded.
    synopsis = None
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        status, item = request("GET", f"/api/items/{item_id}")
        if status == 200 and isinstance(item, dict):
            synopsis = (item.get("metadata") or {}).get("synopsis")
            if synopsis:
                break
        await asyncio.sleep(1)

    check("enrichment produced a synopsis", synopsis is not None)
    if synopsis is None:
        return 1

    print(f"    synopsis ({len(synopsis)} chars): {synopsis[:200]!r}")
    # The whole point of Sprint 055: not Wikidata's one-line description.
    check(
        "the synopsis is not the one-line description",
        synopsis.strip() != "serie de televisión animada"
        and len(synopsis) > len("serie de televisión animada") + 40,
        f"length {len(synopsis)}",
    )
    check(
        "the synopsis is a real synopsis, not an identification sentence",
        len(synopsis.split(".")) >= 3 or len(synopsis) > 150,
        f"sentences {len(synopsis.split('.'))}",
    )

    # 4. The other fields kept their first provider's answer.
    status, item = request("GET", f"/api/items/{item_id}")
    metadata = (item or {}).get("metadata") or {} if isinstance(item, dict) else {}
    print(f"    episodes: {metadata.get('episodes')}  network: {metadata.get('network')!r}")
    check("episodes arrived from Wikidata", metadata.get("episodes") is not None)
    check("airing_status arrived", metadata.get("airing_status") is not None)

    print()
    if FAILED:
        print(f"WALKTHROUGH FAILED: {len(FAILED)} checks")
        return 1
    print("WALKTHROUGH PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
