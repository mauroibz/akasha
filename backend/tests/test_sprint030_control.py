"""Sprint 030's control: the MusicBrainz re-measurement, pinned.

DEC-052's method is that a provider claim is measured against the live API, and a
measurement nobody can re-run is a claim, not evidence. Sprint 030 re-requested the
two MusicBrainz captures on 2026-08-20 — the provider was already measured in Sprint
026, so the question was whether the finding still held. It did, and these tests are
what keep that answer pinned: the 2026-08-20 recordings must agree with the
2026-08-15 ones the adapter suite replays, row for row, on the fields the finding
rests on.
"""

from recordings import recording


def _tracks(payload: dict) -> list[tuple[str, str, int | None, str]]:
    return [
        (track["number"], track["title"], track.get("length"), track["recording"]["id"])
        for medium in payload["media"]
        for track in medium["tracks"]
    ]


def test_the_tracklist_is_unchanged_since_sprint_026() -> None:
    """One `inc=recordings` parameter, no extra request, same five rows.

    The 2026-08-20 capture answers the exact request the adapter makes
    (`inc=artist-credits+labels+media+release-groups+recordings`), and its tracklist
    is identical to the 2026-08-15 one in (number, title, length, recording.id) —
    so "a tracklist costs one parameter and no extra request" is still true.
    """
    before = recording("musicbrainz_release_kind_of_blue.json")
    after = recording("musicbrainz_release_kind_of_blue_recordings_only_20260820.json")

    assert _tracks(before) == _tracks(after)
    assert len(_tracks(after)) == 5
    # A track's identity is its own recording MBID, not a position on this release.
    assert _tracks(after)[0][3] == "60f750f4-d222-46b7-ad5c-905334c9a48a"


def test_the_release_group_is_still_one_work_with_many_editions() -> None:
    """25 releases in one group: release-group ≈ work, release ≈ edition."""
    group = recording("musicbrainz_release_group_kind_of_blue_releases_20260820.json")

    assert group["id"] == "8e8a594f-2175-38c7-a871-abb68ec363e7"
    assert len(group["releases"]) == 25
