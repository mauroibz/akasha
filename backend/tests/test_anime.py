"""Anime: what this domain declares, and what its recognizer answers.

The conformance suite already holds every domain to the shared contract by
parametrization, so nothing here repeats it. What this file covers is the part only
this domain can be wrong about: the vocabulary it chose, the identity rule DEC-088
measured, and the three URL shapes a reader will paste.
"""

from book_tracker.domain.providers import SearchCandidate
from book_tracker.domain.spec import PASSAGE_FIELDS, UrlMatch
from book_tracker.domains.anime import DOMAIN, mal_identity, recognize_anime_url


def candidate(source: str = "anilist", **overrides: object) -> SearchCandidate:
    fields: dict[str, object] = {
        "source": source,
        "source_id": "20613",
        "source_refs": (),
        "title": "Akame ga Kill!",
        "subtitle": None,
        "creators": ("WHITE FOX",),
        "year": 2014,
        "cover_url": None,
        "identifiers": {},
        "language": None,
        "metadata": {},
    }
    fields.update(overrides)
    return SearchCandidate(**fields)  # type: ignore[arg-type]


class TestVocabulary:
    def test_it_speaks_myanimelists_status_vocabulary(self) -> None:
        """The owner's data is already in these words, so the domain uses them."""
        assert [status.value for status in DOMAIN.statuses] == [
            "unsorted",
            "watching",
            "completed",
            "on_hold",
            "dropped",
            "plan_to_watch",
        ]
        assert DOMAIN.default_status == "completed"
        assert DOMAIN.status("unsorted") is not None
        assert not DOMAIN.status("unsorted").choosable  # type: ignore[union-attr]

    def test_it_has_every_passage_field(self) -> None:
        """You can start an anime, finish it, and watch it again."""
        assert DOMAIN.entry_fields == PASSAGE_FIELDS

    def test_it_declares_how_a_copy_is_held(self) -> None:
        assert [row.value for row in DOMAIN.formats] == ["streaming", "digital", "bluray"]

    def test_metadata_names_do_not_collide_with_entry_concepts(self) -> None:
        """`kind` is not the entry's format axis and `airing_status` is not its status.

        Both were nearly called `format` and `status`. A metadata field wearing an
        entry concept's word reads as that concept on every screen that renders it.
        """
        names = {field.name for field in DOMAIN.fields}
        assert "kind" in names and "format" not in names
        assert "airing_status" in names and "status" not in names

    def test_it_offers_no_cover_chooser(self) -> None:
        """The shared chooser is Open Library's work-editions path (DEC-067 row 7)."""
        assert DOMAIN.chooses_covers is False


class TestIdentity:
    """DEC-088: the first domain since books with a real cross-provider identity."""

    def test_two_providers_naming_one_mal_id_share_a_key(self) -> None:
        anilist = candidate("anilist", identifiers={"mal": "22199"})
        kitsu = candidate("kitsu", source_id="8270", identifiers={"mal": "22199"})
        assert mal_identity(anilist) == mal_identity(kitsu) == "mal:22199"

    def test_a_candidate_with_no_mapping_merges_with_nothing(self) -> None:
        """AniList returns `idMal: null` for real ONA entries. None means never merge."""
        assert mal_identity(candidate(identifiers={})) is None

    def test_a_blank_or_unparseable_mal_id_is_not_an_identity(self) -> None:
        assert mal_identity(candidate(identifiers={"mal": ""})) is None
        assert mal_identity(candidate(identifiers={"mal": "not-a-number"})) is None

    def test_anilist_wins_a_merge(self) -> None:
        assert DOMAIN.identity.source_preference == ("anilist", "kitsu")


class TestRecognizer:
    def test_it_reads_an_anilist_url(self) -> None:
        assert recognize_anime_url("https://anilist.co/anime/20613") == UrlMatch(
            "anilist", "fetch", "20613"
        )

    def test_it_reads_an_anilist_url_with_a_slug(self) -> None:
        assert recognize_anime_url("https://anilist.co/anime/20613/Akame-ga-Kill/") == UrlMatch(
            "anilist", "fetch", "20613"
        )

    def test_a_myanimelist_url_is_spent_on_anilist(self) -> None:
        """Jikan is not registered (DEC-088), and AniList queries by `idMal` directly."""
        assert recognize_anime_url("https://myanimelist.net/anime/22199/Akame_ga_Kill") == UrlMatch(
            "anilist", "fetch", "mal:22199"
        )

    def test_it_reads_a_kitsu_url(self) -> None:
        assert recognize_anime_url("https://kitsu.io/anime/akame-ga-kill") == UrlMatch(
            "kitsu", "fetch", "akame-ga-kill"
        )
        assert recognize_anime_url("https://kitsu.app/anime/8270") == UrlMatch(
            "kitsu", "fetch", "8270"
        )

    def test_it_declines_a_manga_url(self) -> None:
        """Manga is a different domain if it is ever wanted, not a mode of this one."""
        assert recognize_anime_url("https://myanimelist.net/manga/13/One_Piece") is None
        assert recognize_anime_url("https://anilist.co/manga/30013") is None

    def test_it_declines_everything_else_without_raising(self) -> None:
        for probe in ("", "   ", "http://[", "https://", "//", "9780000000000", "a" * 4000):
            assert recognize_anime_url(probe) is None


class TestEntryFieldLabels:
    """The entry panel's last book-shaped word.

    `entry_panel_label` fixed the heading in Sprint 028, but the three passage fields
    under it kept labels written for books, so an anime read `Rereads`. The labels are
    the domain's copy for the same reason the heading is.
    """

    def test_anime_rewatches_rather_than_rereads(self) -> None:
        assert DOMAIN.entry_field_labels["reread_count"] == "Rewatches"

    def test_the_neutral_dates_are_left_alone(self) -> None:
        """`Started` and `Finished` read correctly for a series and for a book, so a
        domain that overrides them is adding noise rather than clarity."""
        assert set(DOMAIN.entry_field_labels) == {"reread_count"}


class TestEnrichment:
    """Sprint 039: an imported row is a `mal` id and little else, so this domain does
    enrich — on a key that is not an ISBN, which is the seam DEC-067 row 3 reserved."""

    def test_it_enriches_on_the_myanimelist_id(self) -> None:
        assert DOMAIN.enrichment is not None
        assert DOMAIN.enrichment.identity_kind == "mal"

    def test_it_names_the_providers_that_answer_that_key(self) -> None:
        assert DOMAIN.enrichment is not None
        assert DOMAIN.enrichment.provider_order == ("anilist", "kitsu")

    def test_incompleteness_is_this_domain_s_own_fields(self) -> None:
        """The rule used to be `publisher`/`page_count`/`description` for every domain,
        which an anime has none of — so every anime would have looked incomplete for
        ever and been re-queued on every backfill."""
        assert DOMAIN.enrichment is not None
        declared = {field.name for field in DOMAIN.fields}
        assert set(DOMAIN.enrichment.completeness_fields) <= declared
        assert "synopsis" in DOMAIN.enrichment.completeness_fields

    def test_enriches_still_reads_as_a_yes_or_no(self) -> None:
        assert DOMAIN.enriches is True
