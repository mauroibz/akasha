"""The attachment-cost instrument has to be trustworthy before its numbers are.

Sprint 021 Phase A hands the owner a table of storage strategies and their measured
cost, and that table decides whether attachments get built at all. Two of its numbers
are easy to get quietly wrong, so both are pinned here:

- **Deduplicated bytes.** Strategy E's whole claim is that seven nightly backups of an
  unchanging corpus cost about one copy rather than seven. That claim is only true if
  disk accounting counts a hardlinked file once, and a `Path.stat().st_size` sum counts
  it seven times and reports the naive number as if it were the clever one.
- **Compression.** An epub is a ZIP. If the corpus this instrument generates is
  compressible, `tar.gz` flatters every measurement and the entire assessment is wrong
  in the optimistic direction.

The restore assertions exist because a backup that no longer round-trips is not a
backup. A strategy that deliberately drops attachments has to *say* what it dropped;
returning less than the operator expected without telling them is the failure this
gate is meant to prevent.
"""

import sys
import zlib
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from assess_attachment_cost import (  # noqa: E402
    STRATEGIES,
    Strategy,
    admitted_by_cap,
    disk_usage,
    make_corpus,
    measure_strategy,
    restore_strategy,
)
from test_backup import populated_data_dir  # noqa: E402


def strategy(key: str) -> Strategy:
    for candidate in STRATEGIES:
        if candidate.key == key:
            return candidate
    raise AssertionError(f"no strategy {key}")


def test_generated_attachments_are_incompressible_like_the_epubs_they_stand_in_for(
    tmp_path: Path,
) -> None:
    """If the corpus compresses, every gzip measurement below is optimistic fiction."""
    corpus = tmp_path / "attachments"
    make_corpus(corpus, count=4, size_bytes=64 * 1024, seed=1)

    raw = b"".join(path.read_bytes() for path in sorted(corpus.iterdir()))
    compressed = zlib.compress(raw, 9)

    assert len(compressed) > len(raw) * 0.95


def test_disk_usage_counts_a_hardlinked_file_once(tmp_path: Path) -> None:
    """The measurement that strategy E lives or dies by."""
    first = tmp_path / "first"
    make_corpus(first, count=3, size_bytes=32 * 1024, seed=2)
    standalone = disk_usage(tmp_path)

    second = tmp_path / "second"
    second.mkdir()
    for source in sorted(first.iterdir()):
        (second / source.name).hardlink_to(source)

    assert disk_usage(tmp_path) == standalone


def test_disk_usage_counts_a_copy_twice(tmp_path: Path) -> None:
    """The other half of the same claim: without sharing, bytes really do double."""
    first = tmp_path / "first"
    make_corpus(first, count=3, size_bytes=32 * 1024, seed=3)
    standalone = disk_usage(tmp_path)

    second = tmp_path / "second"
    second.mkdir()
    for source in sorted(first.iterdir()):
        (second / source.name).write_bytes(source.read_bytes())

    assert disk_usage(tmp_path) == pytest.approx(standalone * 2, rel=0.02)


def test_a_full_copy_strategy_grows_by_a_whole_corpus_every_night(tmp_path: Path) -> None:
    data_dir = populated_data_dir(tmp_path)
    make_corpus(data_dir / "assess-corpus", count=4, size_bytes=48 * 1024, seed=4)

    measured = measure_strategy(strategy("A"), data_dir=data_dir, dest=tmp_path / "backups", keep=7)

    assert measured.incremental_bytes == pytest.approx(measured.first_backup_bytes, rel=0.05)
    assert measured.window_bytes == pytest.approx(measured.first_backup_bytes * 7, rel=0.05)
    assert measured.attachment_copies == pytest.approx(7, rel=0.05)
    assert measured.attachment_window_bytes == pytest.approx(
        measured.attachment_bytes * 7, rel=0.05
    )


def test_a_deduplicating_strategy_costs_about_one_copy_across_the_whole_window(
    tmp_path: Path,
) -> None:
    """Attachments do not change once uploaded, so the seventh copy should be free."""
    data_dir = populated_data_dir(tmp_path)
    make_corpus(data_dir / "assess-corpus", count=4, size_bytes=48 * 1024, seed=5)

    measured = measure_strategy(strategy("E"), data_dir=data_dir, dest=tmp_path / "backups", keep=7)

    assert measured.attachment_bytes > 0
    # The window pays for the attachment corpus about once; only the database,
    # covers and imports repeat nightly.
    assert measured.attachment_window_bytes == pytest.approx(measured.attachment_bytes, rel=0.05)
    assert measured.attachment_copies < 1.5


def test_a_size_cap_admits_the_boundary_and_refuses_one_byte_over() -> None:
    cap = 25 * 1024 * 1024

    assert admitted_by_cap([cap - 1, cap, cap + 1], cap=cap) == [cap - 1, cap]


@pytest.mark.parametrize("key", ["A", "B", "C", "D", "E"])
def test_a_strategy_that_archives_attachments_restores_their_bytes(
    tmp_path: Path, key: str
) -> None:
    data_dir = populated_data_dir(tmp_path)
    make_corpus(data_dir / "assess-corpus", count=3, size_bytes=32 * 1024, seed=6)
    expected = {
        path.name: path.read_bytes() for path in sorted((data_dir / "assess-corpus").iterdir())
    }

    measured = measure_strategy(strategy(key), data_dir=data_dir, dest=tmp_path / "backups", keep=7)
    outcome = restore_strategy(
        strategy(key), measured.first_backup_path, into=tmp_path / "restored"
    )

    assert outcome.missing == []
    restored = {path.name: path.read_bytes() for path in sorted(outcome.attachments_dir.iterdir())}
    assert restored == expected


@pytest.mark.parametrize("key", ["F", "G"])
def test_a_strategy_that_drops_attachments_names_what_it_did_not_carry(
    tmp_path: Path, key: str
) -> None:
    """Silently restoring less than the operator expected is the failure mode."""
    data_dir = populated_data_dir(tmp_path)
    make_corpus(data_dir / "assess-corpus", count=3, size_bytes=32 * 1024, seed=7)
    names = sorted(path.name for path in (data_dir / "assess-corpus").iterdir())

    measured = measure_strategy(strategy(key), data_dir=data_dir, dest=tmp_path / "backups", keep=7)
    outcome = restore_strategy(
        strategy(key), measured.first_backup_path, into=tmp_path / "restored"
    )

    assert measured.attachment_bytes == 0
    assert sorted(outcome.missing) == names


def test_every_strategy_still_restores_the_database_the_owner_would_actually_lose(
    tmp_path: Path,
) -> None:
    """Whatever happens to attachments, the scores and notes come back."""
    import sqlite3

    data_dir = populated_data_dir(tmp_path)
    make_corpus(data_dir / "assess-corpus", count=2, size_bytes=16 * 1024, seed=8)

    for index, candidate in enumerate(STRATEGIES):
        measured = measure_strategy(
            candidate, data_dir=data_dir, dest=tmp_path / f"backups-{index}", keep=7
        )
        outcome = restore_strategy(
            candidate, measured.first_backup_path, into=tmp_path / f"restored-{index}"
        )
        connection = sqlite3.connect(outcome.database_path)
        try:
            row = connection.execute("SELECT score, notes FROM entries").fetchone()
        finally:
            connection.close()
        assert row == (9, "The chapter order is the whole point."), candidate.key
