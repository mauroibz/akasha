"""The StoryGraph import (Sprint 099, proposal §7).

Built from StoryGraph's published export header (Title, Authors, Contributors,
ISBN/UID, Format, Read Status, Date Added, Last Date Read, Dates Read, Read Count,
…, Star Rating, Review, …, Tags, Owned?), not from a recorded export: no real
StoryGraph file was available when it was written. The reader therefore requires only
the columns it maps and ignores the rest, so a column StoryGraph adds or reorders does
not refuse the file. Confirm against a real export when one is to hand.
"""

from pathlib import Path

import pytest

from book_tracker.domain.importers import ImportReadContext, ImportSource
from book_tracker.domain.registry import DOMAINS, IMPORTERS
from book_tracker.domains.book.storygraph import (
    IMPORTER,
    SUGGESTED_STATUS,
    StoryGraphCSVError,
    parse_storygraph,
)

HEADER = (
    "Title,Authors,Contributors,ISBN/UID,Format,Read Status,Date Added,Last Date Read,"
    "Dates Read,Read Count,Moods,Pace,Character- or Plot-Driven?,"
    "Strong Character Development?,Loveable Characters?,Diverse Characters?,"
    "Flawed Characters?,Star Rating,Review,Content Warnings,Content Warning Description,"
    "Tags,Owned?"
)
SAMPLE = (
    HEADER
    + "\n"
    + "Rayuela,Julio Cortázar,,9788437604572,paperback,read,2024/01/02,2024/03/02,"
    + '2024/02/01-2024/03/02,2,reflective,slow,Character,Yes,Yes,No,Yes,4.25,"Excelente",'
    + ',,"favoritos, argentina",Yes\n'
    + "Ficciones,Jorge Luis Borges,,,ebook,currently-reading,2024/05/05,,,0,,,,,,,,,,,,,No\n"
    + "Pedro Páramo,Juan Rulfo,,storygraph-uid-123,paperback,did-not-finish,2024/06/06,,,0,"
    + ",,,,,,,,,,,,No\n"
).encode()


def test_rows_map_onto_the_book_domain() -> None:
    rows = parse_storygraph(SAMPLE)
    rayuela, ficciones, paramo = rows
    assert rayuela["title"] == "Rayuela"
    assert rayuela["creators"] == ["Julio Cortázar"]
    assert rayuela["isbn"] == "9788437604572"
    assert rayuela["score"] == 9  # 4.25 stars, doubled and rounded
    assert rayuela["score_provisional"] is True
    assert rayuela["suggested_status"] == "read"
    assert rayuela["date_added"] == "2024-01-02"
    assert rayuela["date_finished"] == "2024-03-02"
    assert rayuela["reread_count"] == 1
    assert rayuela["shelves"] == ["favoritos", "argentina"]
    assert rayuela["review"] == "Excelente"
    assert ficciones["suggested_status"] == "reading"
    assert ficciones["score"] is None
    assert paramo["suggested_status"] == "dropped"
    # A StoryGraph UID is not an ISBN, and is not reported as a broken one either.
    assert paramo["isbn"] is None
    assert paramo["errors"] == []


def test_every_suggested_status_is_one_the_book_domain_has() -> None:
    statuses = {status.value for status in DOMAINS["book"].statuses}
    assert set(SUGGESTED_STATUS.values()) <= statuses


def test_a_file_without_the_mapped_columns_is_refused_with_a_way_out() -> None:
    with pytest.raises(StoryGraphCSVError) as refused:
        parse_storygraph(b"Book Id,Title,Author\n1,Rayuela,Cortazar\n")
    assert refused.value.code == "missing_columns"
    assert refused.value.action


def test_it_is_registered_reads_a_snapshot_and_recognises_its_own_file() -> None:
    assert IMPORTERS["storygraph"] is IMPORTER
    snapshot = IMPORTER.read(
        ImportSource(data=SAMPLE, filename="storygraph.csv"),
        ImportReadContext(path_root=Path("/")),
    )
    assert [record.item.title for record in snapshot.records] == [
        "Rayuela",
        "Ficciones",
        "Pedro Páramo",
    ]
    assert IMPORTER.sniff(SAMPLE[:4096], "storygraph.csv") > 0.9
    assert IMPORTER.sniff(b"Book Id,Title,Author\n", "goodreads.csv") == 0.0
