#!/usr/bin/env python3
"""Measure what each provider actually returns, against the live APIs.

Sprint 020, Phase A. The gate this feeds asks whether cross-provider field
completion is worth its cost, and that question has no honest answer from
recordings alone: recordings say what two providers said about one book on one
day. This script asks both providers about a sample of real books and reports
how often the second one carries something the first one lacks.

Run from `backend/` so the package resolves, with the owner's key exported —
`make dev-backend` does not read `.env`, and an anonymous Google Books request
is answered 429 immediately:

    cd backend && set -a && . ../.env && set +a \\
      && USER_AGENT_CONTACT=you@example.com \\
         UV_CACHE_DIR=/tmp/akasha-uv-cache \\
         uv run python ../scripts/assess_provider_completeness.py --sample 60

**The ISBN sample is harvested from provider search, never invented.** An
invented ISBN passes its checksum and resolves to a real but unrelated edition,
which silently turns every downstream measurement into noise. This is a
documented repeat offender in `docs/agent/HANDOFF.md`.

Nothing here writes to the database. Results are written as JSON so the verdict
in `docs/decisions.md` can quote numbers that were actually observed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

import httpx  # noqa: E402

from book_tracker.application.providers import search_providers  # noqa: E402
from book_tracker.infrastructure.providers import (  # noqa: E402
    EDITION_CONFIRMED,
    EDITION_CONTRADICTED,
    EDITION_UNVERIFIABLE,
    GoogleBooksProvider,
    OpenLibraryProvider,
    ProviderPayloadError,
    create_provider_client,
)

# Deliberately Spanish-heavy with an English tail: the library this is measured for
# is mostly Spanish-language, and Google Books' better Spanish coverage is the whole
# reason it is consulted at all (product spec 4.2).
QUERIES = (
    "Cien años de soledad García Márquez",
    "Rayuela Cortázar",
    "Pedro Páramo Rulfo",
    "Ficciones Borges",
    "La invención de Morel Bioy Casares",
    "Los detectives salvajes Bolaño",
    "El túnel Sabato",
    "Boquitas pintadas Puig",
    "Respiración artificial Piglia",
    "La casa de los espíritus Allende",
    "Escaping the Build Trap Perri",
    "The Shadow of the Wind Zafón",
    "Designing Data-Intensive Applications",
    "The Pragmatic Programmer",
    "Thinking Fast and Slow Kahneman",
)

# Fields enrichment actually fills. Split because the two halves carry different
# risk: an edition-specific field attached to the wrong edition is a factual error,
# where a work-level one is merely the wrong flavour of true.
EDITION_FIELDS = ("year", "publisher", "page_count", "cover")
WORK_FIELDS = ("description", "subjects", "authors", "language")


def _non_empty(value: object) -> bool:
    return value not in (None, "", [], {})


def _fields(payload: Any) -> dict[str, bool]:
    metadata = dict(payload.metadata)
    present = {
        "year": payload.year is not None,
        "publisher": _non_empty(metadata.get("publisher")),
        "page_count": _non_empty(metadata.get("page_count")),
        "cover": _non_empty(payload.cover_url),
        "description": _non_empty(metadata.get("description")),
        "subjects": _non_empty(metadata.get("subjects")),
        "authors": _non_empty(list(payload.authors)),
        "language": _non_empty(payload.language),
    }
    return present


def _describes_html(payload: Any) -> bool:
    description = str(dict(payload.metadata).get("description") or "")
    return "<" in description and ">" in description


async def harvest_isbns(providers: list[Any], wanted: int) -> list[dict[str, Any]]:
    """Collect ISBN13s from real search results until the sample is full."""
    sample: dict[str, dict[str, Any]] = {}
    for query in QUERIES:
        if len(sample) >= wanted:
            break
        try:
            candidates = await search_providers(query, providers, limit=20)
        except Exception as error:  # a failed query costs the sample, not the run
            print(f"  ! search failed for {query!r}: {type(error).__name__}")
            continue
        added = 0
        for candidate in candidates:
            isbn = candidate.identifiers.get("isbn13")
            if not isbn or isbn in sample:
                continue
            sample[isbn] = {
                "isbn": isbn,
                "query": query,
                "title": candidate.title,
                "search_source": candidate.source,
            }
            added += 1
            if len(sample) >= wanted:
                break
        print(f"  {query[:44]:<46} +{added:<3} (sample {len(sample)})")
    return list(sample.values())


async def probe(provider: Any, isbn: str) -> dict[str, Any]:
    """Fetch one ISBN from one provider and record everything worth measuring."""
    started = time.perf_counter()
    try:
        payload = await provider.fetch_by_isbn(isbn)
    except ProviderPayloadError as error:
        return {
            "ok": False,
            "ms": (time.perf_counter() - started) * 1000,
            "code": error.code,
        }
    except (TimeoutError, httpx.HTTPError, OSError) as error:
        return {
            "ok": False,
            "ms": (time.perf_counter() - started) * 1000,
            "code": type(error).__name__,
        }
    elapsed = (time.perf_counter() - started) * 1000
    # `fetch_by_isbn` classifies against the raw provider row, which carries every
    # identifier the record holds; the payload's own `identifiers` slot keeps only one.
    return {
        "ok": True,
        "ms": elapsed,
        "edition": payload.edition_match or EDITION_UNVERIFIABLE,
        "fields": _fields(payload),
        "html_description": _describes_html(payload),
        "title": payload.title,
        "cover_url": payload.cover_url,
    }


def summarize(rows: list[dict[str, Any]], sample_size: int) -> None:
    print("\n" + "=" * 78)
    print(f"PROVIDER COMPLETENESS — {sample_size} ISBNs harvested from live search")
    print("=" * 78)

    for name in ("openlibrary", "googlebooks"):
        results = [row[name] for row in rows if name in row]
        hits = [row for row in results if row["ok"]]
        latencies = [row["ms"] for row in results]
        print(f"\n{name}")
        print(f"  answered            {len(hits)}/{len(results)}")
        if latencies:
            print(
                f"  latency ms          p50 {statistics.median(latencies):.0f}"
                f"  p95 {sorted(latencies)[min(len(latencies) - 1, int(0.95 * (len(latencies) - 1)))]:.0f}"
                f"  max {max(latencies):.0f}"
            )
        codes = Counter(row["code"] for row in results if not row["ok"])
        if codes:
            print(f"  failures            {dict(codes)}")
        if not hits:
            continue
        editions = Counter(row["edition"] for row in hits)
        print("  edition verification")
        for state in (EDITION_CONFIRMED, EDITION_CONTRADICTED, EDITION_UNVERIFIABLE):
            count = editions.get(state, 0)
            print(f"    {state:<14} {count:>4}  {100 * count / len(hits):5.1f}%")
        print("  field coverage (share of answered fetches)")
        for field in EDITION_FIELDS + WORK_FIELDS:
            filled = sum(1 for row in hits if row["fields"][field])
            marker = "edition" if field in EDITION_FIELDS else "work"
            print(f"    {field:<14} {100 * filled / len(hits):5.1f}%   [{marker}]")
        html = sum(1 for row in hits if row["html_description"])
        print(f"  descriptions containing HTML markup: {html}/{len(hits)}")

    # The question the gate actually asks.
    both = [row for row in rows if row.get("openlibrary", {}).get("ok")]
    print("\n" + "-" * 78)
    print("WHAT THE SECOND PROVIDER WOULD ADD")
    print(f"  Open Library answered for {len(both)} of {sample_size} sampled ISBNs.")
    print("  Of those, the share where Google Books holds a field Open Library left empty,")
    print("  split by whether attaching it to the wrong edition would be a factual error:")
    gains: Counter[str] = Counter()
    reachable = 0
    verified_reachable = 0
    for row in both:
        google = row.get("googlebooks")
        if not google or not google["ok"]:
            continue
        reachable += 1
        if google["edition"] == EDITION_CONFIRMED:
            verified_reachable += 1
        for field in EDITION_FIELDS + WORK_FIELDS:
            if google["fields"][field] and not row["openlibrary"]["fields"][field]:
                gains[field] += 1
    print(f"  Google Books also answered for {reachable} of them.")
    print(f"  Of those, {verified_reachable} could be verified as the same edition.")
    if reachable:
        for field in EDITION_FIELDS + WORK_FIELDS:
            marker = "edition" if field in EDITION_FIELDS else "work"
            print(
                f"    {field:<14} {gains.get(field, 0):>4} / {reachable}"
                f"  {100 * gains.get(field, 0) / reachable:5.1f}%   [{marker}]"
            )
    print("-" * 78)


async def run(sample_size: int, output: Path) -> int:
    contact = os.environ.get("USER_AGENT_CONTACT")
    key = os.environ.get("GOOGLE_BOOKS_API_KEY", "")
    if not contact:
        print("USER_AGENT_CONTACT must be set: Open Library throttles anonymous traffic.")
        return 2
    if not key:
        print("GOOGLE_BOOKS_API_KEY must be set: an anonymous request is answered 429.")
        return 2

    client = create_provider_client()
    try:
        openlibrary = OpenLibraryProvider(client, contact)
        google = GoogleBooksProvider(client, key)

        print("HARVESTING ISBNs FROM LIVE SEARCH")
        sample = await harvest_isbns([openlibrary, google], sample_size)
        print(f"\nsample: {len(sample)} ISBNs\n")

        print("FETCHING EACH ISBN FROM BOTH PROVIDERS")
        rows: list[dict[str, Any]] = []
        for index, entry in enumerate(sample, start=1):
            row: dict[str, Any] = dict(entry)
            row["openlibrary"] = await probe(openlibrary, entry["isbn"])
            row["googlebooks"] = await probe(google, entry["isbn"])
            rows.append(row)
            states = (
                f"{row['openlibrary']['edition']:<13}"
                if row["openlibrary"]["ok"]
                else f"{row['openlibrary']['code']:<13}"
            )
            google_state = (
                row["googlebooks"]["edition"]
                if row["googlebooks"]["ok"]
                else row["googlebooks"]["code"]
            )
            print(
                f"  {index:>3}/{len(sample)}  {entry['isbn']}  "
                f"OL {states}  GB {google_state:<13}  {entry['title'][:32]}"
            )

        summarize(rows, len(sample))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nwrote {output}")
        return 0
    finally:
        await client.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=int, default=60)
    parser.add_argument("--output", type=Path, default=Path("provider-assessment.json"))
    arguments = parser.parse_args()
    return asyncio.run(run(arguments.sample, arguments.output))


if __name__ == "__main__":
    raise SystemExit(main())
