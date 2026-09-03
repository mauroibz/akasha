"""The Spotify connector, against synthetic archives built here.

Nothing in this file comes from the owner's real export. The artists, titles and
ids below are invented; the *shapes* are the ones measured on 2026-09-02/03
(`docs/spotify-import-and-insights-viability.md`): a ZIP nesting every member one
directory deep, `YourLibrary.json`'s `albums` array carrying an exact
`spotify:album:` URI per saved album, and a second, structurally different bundle
(Technical Log Information) that must be refused by name rather than scavenged.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from book_tracker.domain.importers import ImportReadContext, ImportReadError, ImportSource
from book_tracker.domains.album.spotify import (
    IMPORTER,
    SpotifyError,
    records_from_library,
)


def account_data(
    members: dict[str, Any] | None = None, *, prefix: str = "Spotify Account Data"
) -> bytes:
    """A ZIP nested one directory deep, the shape both real bundles share."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        for name, payload in (members or {}).items():
            text = payload if isinstance(payload, str) else json.dumps(payload)
            zipped.writestr(f"{prefix}/{name}", text)
    return buffer.getvalue()


def your_library(albums: list[dict[str, Any]], tracks: list[dict[str, Any]] | None = None) -> bytes:
    return account_data(
        {"YourLibrary.json": {"albums": albums, "tracks": tracks or [], "artists": []}}
    )


def read(data: bytes) -> Any:
    return IMPORTER.read(
        ImportSource(data=data, filename="spotify.zip"), ImportReadContext(Path("."))
    )


def album_row(
    artist: str = "Gorillaz", album: str = "Plastic Beach", uri: str = "spotify:album:abc"
) -> dict[str, Any]:
    return {"artist": artist, "album": album, "uri": uri}


# ----------------------------------------------------------------------------------
# Deliverable 1: which bundle is readable, and what a saved album produces
# ----------------------------------------------------------------------------------


class TestAccountData:
    def test_a_saved_album_produces_a_record_with_a_spotify_identifier(self) -> None:
        snapshot = read(your_library([album_row(uri="spotify:album:2dIGnmEIy1WZIcZCFSj6i8")]))
        assert len(snapshot.records) == 1
        record = snapshot.records[0]
        assert record.item.title == "Plastic Beach"
        assert record.item.metadata["creators"] == ["Gorillaz"]
        assert record.item.identifiers == {"spotify": "2dIGnmEIy1WZIcZCFSj6i8"}
        assert record.item_type is None  # the connector's one declared domain

    def test_every_saved_album_becomes_its_own_row(self) -> None:
        snapshot = read(
            your_library(
                [
                    album_row(uri="spotify:album:aaaaaaaaaaaaaaaaaaaaaa"),
                    album_row(
                        artist="Radiohead",
                        album="In Rainbows",
                        uri="spotify:album:bbbbbbbbbbbbbbbbbbbbbb",
                    ),
                ]
            )
        )
        assert [row.item.title for row in snapshot.records] == ["Plastic Beach", "In Rainbows"]

    def test_a_row_with_no_album_uri_is_silently_dropped(self) -> None:
        """`YourLibrary.tracks` and `.artists` carry no album URI; a malformed or
        future album row without one is not something this reader can identify."""
        snapshot = read(your_library([{"artist": "A", "album": "B", "uri": "spotify:track:x"}]))
        assert snapshot.records == ()

    def test_the_nested_folder_name_is_not_assumed(self) -> None:
        """Both real bundles nest one directory deep; the reader matches by
        basename, not by a fixed root, so a future rename of that folder does
        not break the import."""
        snapshot = read(your_library([album_row()]))
        assert len(snapshot.records) == 1
        # A differently-named root still works, proving the basename match.
        differently_named = account_data(
            {"YourLibrary.json": {"albums": [album_row()], "tracks": [], "artists": []}},
            prefix="Some Other Export Folder",
        )
        assert len(read(differently_named).records) == 1


class TestTechnicalLogRefusal:
    def test_the_technical_log_bundle_is_refused_by_name(self) -> None:
        technical_log = account_data(
            {"ReadMeFirst_TechnicalLogInformation.pdf": "not really a pdf"},
            prefix="Spotify Technical Log Information",
        )
        with pytest.raises(SpotifyError) as error:
            read(technical_log)
        assert error.value.code == "wrong_export"
        assert error.value.action is not None
        assert "Account data" in error.value.action

    def test_a_zip_with_neither_shape_is_refused(self) -> None:
        empty = account_data({"SomethingElse.json": {}})
        with pytest.raises(SpotifyError) as error:
            read(empty)
        assert error.value.code == "invalid_archive"


# ----------------------------------------------------------------------------------
# Deliverable 5: track roll-up, opt-in and threshold-gated, defaulting to off
# ----------------------------------------------------------------------------------


class TestTrackRollup:
    def test_rollup_is_off_by_default(self) -> None:
        library = {
            "albums": [],
            "tracks": [
                {"artist": "A", "album": "Solo Song Album", "track": t, "uri": f"spotify:track:{t}"}
                for t in ("t1", "t2", "t3", "t4")
            ],
        }
        records = records_from_library(library)
        assert records == []

    def test_rollup_on_honours_the_minimum_track_threshold(self) -> None:
        library = {
            "albums": [],
            "tracks": [
                # Two saved tracks from "Below Threshold": stays below a
                # threshold of 3.
                {
                    "artist": "A",
                    "album": "Below Threshold",
                    "track": "t1",
                    "uri": "spotify:track:1",
                },
                {
                    "artist": "A",
                    "album": "Below Threshold",
                    "track": "t2",
                    "uri": "spotify:track:2",
                },
                # Three saved tracks from "At Threshold": meets it.
                {"artist": "B", "album": "At Threshold", "track": "t1", "uri": "spotify:track:3"},
                {"artist": "B", "album": "At Threshold", "track": "t2", "uri": "spotify:track:4"},
                {"artist": "B", "album": "At Threshold", "track": "t3", "uri": "spotify:track:5"},
            ],
        }
        records = records_from_library(library, rollup=True, rollup_min_tracks=3)
        assert [row.item.title for row in records] == ["At Threshold"]
        # A rolled-up row carries no identity: it is not something Spotify's
        # export names an exact album for, so it never merges and is never
        # queued for enrichment (the same rule a search-added album follows).
        assert records[0].item.identifiers == {}

    def test_rollup_never_duplicates_an_already_saved_album(self) -> None:
        library = {
            "albums": [album_row(artist="Gorillaz", album="Plastic Beach")],
            "tracks": [
                {
                    "artist": "Gorillaz",
                    "album": "Plastic Beach",
                    "track": t,
                    "uri": f"spotify:track:{t}",
                }
                for t in ("t1", "t2", "t3")
            ],
        }
        records = records_from_library(library, rollup=True, rollup_min_tracks=1)
        assert len(records) == 1
        assert records[0].item.identifiers == {"spotify": "abc"}


# ----------------------------------------------------------------------------------
# Deliverable: re-import matches exactly, no provider traffic, no duplicates
# ----------------------------------------------------------------------------------


def library(tmp_path: Path) -> tuple[Any, Any]:
    """`(DomainRepository, add)`, the same shape the Trakt tests use."""
    from sqlalchemy import text

    from book_tracker.config import Settings
    from book_tracker.database import create_engine
    from book_tracker.infrastructure.repositories import DomainRepository
    from book_tracker.migrations import upgrade

    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    engine = create_engine(configured)

    def add(title: str, item_type: str, **identifiers: str) -> int:
        with engine.begin() as connection:
            item_id = connection.execute(
                text(
                    "INSERT INTO items(type,title,identifiers,metadata,created_at,updated_at) "
                    "VALUES(:type,:title,'{}','{}','n','n') RETURNING id"
                ),
                {"type": item_type, "title": title},
            ).scalar_one()
            for kind, value in identifiers.items():
                connection.execute(
                    text(
                        "INSERT INTO item_identifiers(item_id,kind,normalized_value,value,"
                        "created_at,updated_at) VALUES(:item,:kind,:value,:value,'n','n')"
                    ),
                    {"item": item_id, "kind": kind, "value": value},
                )
        return item_id

    return DomainRepository(engine), add


class TestReimportIsIdempotent:
    def test_a_previously_imported_album_matches_exactly_on_its_spotify_id(
        self, tmp_path: Path
    ) -> None:
        matcher, add = library(tmp_path)
        existing = add("Plastic Beach", "album", spotify="2dIGnmEIy1WZIcZCFSj6i8")
        record = read(
            your_library([album_row(uri="spotify:album:2dIGnmEIy1WZIcZCFSj6i8")])
        ).records[0]
        decision = IMPORTER.match(record, matcher)
        assert decision.kind.value == "exact"
        assert decision.item_id == existing

    def test_a_different_album_is_a_new_candidate(self, tmp_path: Path) -> None:
        matcher, add = library(tmp_path)
        add("Plastic Beach", "album", spotify="2dIGnmEIy1WZIcZCFSj6i8")
        record = read(
            your_library(
                [album_row(artist="Radiohead", album="In Rainbows", uri="spotify:album:different")]
            )
        ).records[0]
        decision = IMPORTER.match(record, matcher)
        assert decision.kind.value == "new"


# ----------------------------------------------------------------------------------
# Archive safety: the same shape Trakt's reader is held to.
# ----------------------------------------------------------------------------------


class TestArchiveSafety:
    def test_a_missing_file_is_refused(self) -> None:
        with pytest.raises(ImportReadError):
            IMPORTER.read(ImportSource(data=None), ImportReadContext(Path(".")))

    def test_a_non_zip_upload_is_refused(self) -> None:
        with pytest.raises(SpotifyError) as error:
            read(b"not a zip")
        assert error.value.code == "invalid_archive"

    @pytest.mark.parametrize(
        "name",
        [
            "Spotify Account Data/../escape.json",
            "/absolute.json",
            "Spotify Account Data/nested/../../escape.json",
            "Spotify Account Data/.hidden/x.json",
        ],
    )
    def test_a_member_that_tries_to_escape_is_refused(self, name: str) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            zipped.writestr(name, "{}")
        with pytest.raises(SpotifyError) as error:
            read(buffer.getvalue())
        assert error.value.code == "unsafe_archive"

    def test_an_encrypted_member_is_refused(self) -> None:
        """The flag bit is set directly on the raw bytes: the stdlib `zipfile`
        module offers no way to *write* an encrypted member, only to read one."""
        data = bytearray(your_library([album_row()]))
        data[data.find(b"PK\x03\x04") + 6] |= 0x1
        data[data.find(b"PK\x01\x02") + 8] |= 0x1
        with pytest.raises(SpotifyError) as error:
            read(bytes(data))
        assert error.value.code == "unsafe_archive"

    def test_an_archive_naming_one_member_twice_is_refused(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            zipped.writestr("Spotify Account Data/YourLibrary.json", "{}")
            zipped.writestr("Spotify Account Data/YourLibrary.json", "{}")
        with pytest.raises(SpotifyError) as error:
            read(buffer.getvalue())
        assert error.value.code == "unsafe_archive"

    def test_an_archive_that_claims_to_expand_enormously_is_refused(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipped:
            zipped.writestr(
                "Spotify Account Data/YourLibrary.json",
                json.dumps({"albums": [album_row()], "tracks": [], "artists": []}),
            )
            zipped.writestr("Spotify Account Data/bomb.txt", b"\0" * (17 * 1024 * 1024))
        with pytest.raises(SpotifyError) as error:
            read(buffer.getvalue())
        assert error.value.code == "export_too_large"

    def test_a_member_that_lies_about_its_size_is_refused_while_read(self) -> None:
        """The declared sizes are checked on the way in; a member whose real
        expansion exceeds its declaration is refused mid-read."""
        from book_tracker.domains.album import spotify as module

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipped:
            payload = b"0" * (module.MAX_MEMBER_BYTES + 1)
            info = zipfile.ZipInfo("Spotify Account Data/YourLibrary.json")
            zipped.writestr(info, payload)
        with pytest.raises(SpotifyError) as error:
            read(buffer.getvalue())
        assert error.value.code == "export_too_large"

    def test_a_member_that_is_not_valid_json_is_refused(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            zipped.writestr("Spotify Account Data/YourLibrary.json", "not json")
        with pytest.raises(SpotifyError) as error:
            read(buffer.getvalue())
        assert error.value.code == "invalid_archive"
