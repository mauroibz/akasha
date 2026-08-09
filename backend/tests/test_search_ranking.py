"""Search ranking and completeness, pinned against recorded provider results.

`merge_and_rank` used to sort merged results alphabetically by title, which threw away
the relevance ordering the providers had already computed. These tests use real search
responses so the ordering they assert is the ordering a person actually gets.
"""

from __future__ import annotations

import pytest
from recordings import recording, replay

from book_tracker.application.providers import search_providers
from book_tracker.domain.providers import SearchCandidate, SourceRef, merge_and_rank
from book_tracker.infrastructure.providers import OpenLibraryProvider, create_provider_client

RAYUELA_ROUTES = {"/search.json": (200, recording("search_rayuela.json"))}
# The provider ranks the intended edition first; five unrelated titles sort before
# "Rayuela" alphabetically once accents are stripped.
INTENDED_EDITION = "OL47684105M"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def stub(source: str, source_id: str, title: str, *, isbn: str | None = None) -> SearchCandidate:
    return SearchCandidate(
        source=source,
        source_id=source_id,
        source_refs=(SourceRef(source, source_id),),
        title=title,
        subtitle=None,
        authors=("Someone",),
        year=2000,
        cover_url="https://cover",
        identifiers={"isbn13": isbn} if isbn else {},
        language="es",
        metadata={},
    )


@pytest.mark.anyio
async def test_the_intended_edition_survives_alphabetically_earlier_noise() -> None:
    async with create_provider_client(transport=replay(RAYUELA_ROUTES)) as client:
        rows = await OpenLibraryProvider(client, "test@example.invalid").search("Rayuela Cortázar")

    ranked = merge_and_rank("Rayuela Cortázar", rows)
    top = [row.source_id for row in ranked[:3]]
    assert INTENDED_EDITION in top, [row.title for row in ranked[:3]]
    # The titles that used to win purely by sorting early.
    displacers = {"Claves de una novelística existencial", "Cuaderno de bitácora de \"Rayuela\""}
    assert not displacers & {row.title for row in ranked[: top.index(INTENDED_EDITION)]}


def test_ranking_keeps_provider_order_and_does_not_sort_by_title() -> None:
    candidates = [
        stub("openlibrary", "OL1M", "Zzz the provider's best answer"),
        stub("openlibrary", "OL2M", "Aaa an unrelated earlier title"),
    ]
    assert [row.source_id for row in merge_and_rank("query", candidates)] == ["OL1M", "OL2M"]


def test_two_providers_interleave_by_position_rather_than_concatenating() -> None:
    candidates = [
        stub("openlibrary", "OL1M", "ol first"),
        stub("openlibrary", "OL2M", "ol second"),
        stub("googlebooks", "g1", "gb first"),
        stub("googlebooks", "g2", "gb second"),
    ]
    assert [row.source_id for row in merge_and_rank("query", candidates)] == [
        "OL1M",
        "g1",
        "OL2M",
        "g2",
    ]


def test_a_duplicate_isbn_across_providers_stays_one_card_with_both_refs() -> None:
    candidates = [
        stub("openlibrary", "OL1M", "Rayuela", isbn="9788437604572"),
        stub("googlebooks", "g1", "Rayuela", isbn="9788437604572"),
    ]
    merged = merge_and_rank("Rayuela", candidates)
    assert len(merged) == 1
    assert merged[0].source == "openlibrary"
    assert set(merged[0].source_refs) == {
        SourceRef("openlibrary", "OL1M"),
        SourceRef("googlebooks", "g1"),
    }


def test_signals_only_break_ties_between_equally_ranked_results() -> None:
    """At the same provider position the dumb signals still decide (product spec 4.3)."""
    candidates = [
        stub("openlibrary", "OL1M", "An unrelated title"),
        stub("googlebooks", "g1", "Rayuela"),
    ]
    assert [row.source_id for row in merge_and_rank("Rayuela", candidates)] == ["g1", "OL1M"]


@pytest.mark.anyio
async def test_search_providers_preserves_ranking_end_to_end() -> None:
    async with create_provider_client(transport=replay(RAYUELA_ROUTES)) as client:
        provider = OpenLibraryProvider(client, "test@example.invalid")
        ranked = await search_providers("Rayuela Cortázar", [provider])
    assert ranked[0].source_id == INTENDED_EDITION
