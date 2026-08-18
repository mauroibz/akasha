"""Search ranking and completeness, pinned against recorded provider results.

`merge_and_rank` used to sort merged results alphabetically by title, which threw away
the relevance ordering the providers had already computed. These tests use real search
responses so the ordering they assert is the ordering a person actually gets.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from recordings import recording, replay

from book_tracker.application.providers import search_providers
from book_tracker.domain.providers import SearchCandidate, SourceRef, merge_and_rank
from book_tracker.domains.album import ALBUM_IDENTITY
from book_tracker.domains.book import BOOK_IDENTITY
from book_tracker.domains.book.providers import OpenLibraryProvider
from book_tracker.infrastructure.providers import create_provider_client

RAYUELA_ROUTES = {"/search.json": (200, recording("search_rayuela.json"))}
# The provider ranks the intended edition first; five unrelated titles sort before
# "Rayuela" alphabetically once accents are stripped.
INTENDED_EDITION = "OL47684105M"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def stub(
    source: str,
    source_id: str,
    title: str,
    *,
    isbn: str | None = None,
    identifiers: dict[str, str] | None = None,
) -> SearchCandidate:
    return SearchCandidate(
        source=source,
        source_id=source_id,
        source_refs=(SourceRef(source, source_id),),
        title=title,
        subtitle=None,
        creators=("Someone",),
        year=2000,
        cover_url="https://cover",
        identifiers=identifiers if identifiers is not None else ({"isbn13": isbn} if isbn else {}),
        language="es",
        metadata={},
    )


@pytest.mark.anyio
async def test_the_intended_edition_survives_alphabetically_earlier_noise() -> None:
    async with create_provider_client(transport=replay(RAYUELA_ROUTES)) as client:
        rows = await OpenLibraryProvider(client, "test@example.invalid").search("Rayuela Cortázar")

    ranked = merge_and_rank("Rayuela Cortázar", rows, identity=BOOK_IDENTITY)
    top = [row.source_id for row in ranked[:3]]
    assert INTENDED_EDITION in top, [row.title for row in ranked[:3]]
    # The titles that used to win purely by sorting early.
    displacers = {"Claves de una novelística existencial", 'Cuaderno de bitácora de "Rayuela"'}
    assert not displacers & {row.title for row in ranked[: top.index(INTENDED_EDITION)]}


def test_ranking_keeps_provider_order_and_does_not_sort_by_title() -> None:
    candidates = [
        stub("openlibrary", "OL1M", "Zzz the provider's best answer"),
        stub("openlibrary", "OL2M", "Aaa an unrelated earlier title"),
    ]
    assert [
        row.source_id for row in merge_and_rank("query", candidates, identity=BOOK_IDENTITY)
    ] == ["OL1M", "OL2M"]


def test_two_providers_interleave_by_position_rather_than_concatenating() -> None:
    candidates = [
        stub("openlibrary", "OL1M", "ol first"),
        stub("openlibrary", "OL2M", "ol second"),
        stub("googlebooks", "g1", "gb first"),
        stub("googlebooks", "g2", "gb second"),
    ]
    assert [
        row.source_id for row in merge_and_rank("query", candidates, identity=BOOK_IDENTITY)
    ] == [
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
    merged = merge_and_rank("Rayuela", candidates, identity=BOOK_IDENTITY)
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
    assert [
        row.source_id for row in merge_and_rank("Rayuela", candidates, identity=BOOK_IDENTITY)
    ] == ["g1", "OL1M"]


def test_an_identity_that_declines_to_key_never_merges_two_candidates() -> None:
    """Albums' answer to cross-provider identity is *never merge*, and it is complete.

    DEC-052 observed barcode `888837168625` on three distinct releases, so a shared
    barcode is not shared identity. ISBN's global uniqueness is the only reason books
    can be grouped across providers at all.
    """
    shared_barcode = {"barcode": "888837168625"}
    candidates = [
        stub("musicbrainz", "r1", "Random Access Memories", identifiers=shared_barcode),
        stub("musicbrainz", "r2", "Random Access Memories", identifiers=shared_barcode),
    ]
    merged = merge_and_rank("Random Access Memories", candidates, identity=ALBUM_IDENTITY)
    assert [row.source_id for row in merged] == ["r1", "r2"]
    assert [row.source_refs for row in merged] == [
        (SourceRef("musicbrainz", "r1"),),
        (SourceRef("musicbrainz", "r2"),),
    ]


def test_the_merged_primary_follows_the_source_preference_not_a_hardcoded_source() -> None:
    """`_merge_group` used to name `openlibrary` outright, which a second domain cannot use."""
    reversed_preference = replace(BOOK_IDENTITY, source_preference=("googlebooks", "openlibrary"))
    candidates = [
        stub("openlibrary", "OL1M", "Rayuela", isbn="9788437604572"),
        stub("googlebooks", "g1", "Rayuela (Google)", isbn="9788437604572"),
    ]
    merged = merge_and_rank("Rayuela", candidates, identity=reversed_preference)
    assert len(merged) == 1
    assert merged[0].source == "googlebooks"
    assert merged[0].title == "Rayuela (Google)"


QUIJOTE_ROUTES = {
    "/search.json": (200, recording("search_don_quijote.json")),
    # Result 7 has no datable edition anywhere; result 14 does, and is the one the
    # `and not enriched` gate never reached.
    "/works/OL17741305W/editions.json": (200, recording("editions_OL17741305W.json")),
    "/works/OL34762840W/editions.json": (200, recording("editions_OL34762840W.json")),
}


@pytest.mark.anyio
async def test_every_result_resolves_an_edition_year_not_only_the_first() -> None:
    async with create_provider_client(transport=replay(QUIJOTE_ROUTES)) as client:
        rows = await OpenLibraryProvider(client, "test@example.invalid").search(
            "Don Quijote de la Mancha"
        )

    assert [row.title for row in rows if row.year is None] == []
    # 19 of the 20 recorded works resolve to an edition. The twentieth carries no
    # edition identity at all and is dropped rather than shown without one.
    assert len(rows) == 19


@pytest.mark.anyio
async def test_a_prose_publish_date_still_yields_a_year() -> None:
    """The recorded editions publish as "Mar 09, 2005"; a four-character slice fails."""
    async with create_provider_client(transport=replay(QUIJOTE_ROUTES)) as client:
        rows = await OpenLibraryProvider(client, "test@example.invalid").search(
            "Don Quijote de la Mancha"
        )
    resolved = next(row for row in rows if row.title == "Don Quijote de La Mancha")
    recorded_years = {
        int(entry["publish_date"][-4:])
        for entry in recording("editions_OL34762840W.json")["entries"]
        if entry.get("publish_date")
    }
    assert resolved.year in recorded_years


@pytest.mark.anyio
async def test_search_providers_preserves_ranking_end_to_end() -> None:
    async with create_provider_client(transport=replay(RAYUELA_ROUTES)) as client:
        provider = OpenLibraryProvider(client, "test@example.invalid")
        ranked = await search_providers("Rayuela Cortázar", [provider])
    assert ranked[0].source_id == INTENDED_EDITION
