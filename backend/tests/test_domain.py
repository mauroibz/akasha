import pytest

from book_tracker.domain.identity import InvalidIdentifier, normalize_identifier
from book_tracker.domain.matching import MatchKind, decide_match
from book_tracker.domain.merge import fill_empty
from book_tracker.domain.normalization import creator_sort_name, normalize_text, strip_html
from book_tracker.domain.registry import (
    ALL_FORMATS,
    ALL_STATUSES,
    DOMAINS,
    EntryFormat,
    EntryStatus,
    ItemTypeName,
)
from book_tracker.domain.spec import (
    InvalidEntryField,
    InvalidFormat,
    InvalidProgress,
    InvalidStatus,
    validate_entry_fields,
    validate_entry_values,
    validate_formats,
    validate_status,
)
from book_tracker.domains.album import DOMAIN as ALBUM
from book_tracker.domains.book import DOMAIN as BOOK


@pytest.mark.parametrize(
    ("value", "canonical"),
    [("0-306-40615-2", "9780306406157"), ("978-0-306-40615-7", "9780306406157")],
)
def test_isbn_normalizes_to_canonical_isbn13(value: str, canonical: str) -> None:
    assert normalize_identifier("isbn", value).normalized_value == canonical


def test_invalid_isbn_is_rejected() -> None:
    with pytest.raises(InvalidIdentifier):
        normalize_identifier("isbn", "9780306406158")


def test_text_normalization_is_accent_and_punctuation_insensitive() -> None:
    assert normalize_text("  Cien años—de SOLEDAD! ") == "cien anos de soledad"


def test_title_author_match_is_ambiguity_only() -> None:
    decision = decide_match(exact_item_ids=set(), title_author_item_ids={3})
    assert decision.kind is MatchKind.AMBIGUOUS
    assert decision.item_id is None
    assert decision.candidates == (3,)


def test_fill_empty_preserves_non_empty_values() -> None:
    assert fill_empty(
        {"title": "Existing", "subtitle": "", "metadata": {"creators": ["A"]}},
        {"title": "Incoming", "subtitle": "Filled", "metadata": {"creators": ["B"]}},
    ) == {"title": "Existing", "subtitle": "Filled", "metadata": {"creators": ["A"]}}


# --------------------------------------------------------------------------------------
# Provider descriptions arrive as markup (Sprint 020)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # The exact shapes the Sprint 019 walkthrough saw on the detail page.
        (
            "<p>To stay competitive, companies <b>must</b> innovate.</p>",
            "To stay competitive, companies must innovate.",
        ),
        ("<p> <b>Cien años</b> de soledad</p>", "Cien años de soledad"),
        # Paragraphs stay separated rather than running together into one wall.
        ("<p>First.</p><p>Second.</p>", "First.\n\nSecond."),
        # Entities are decoded whether or not any tag is present.
        ("Tom &amp; Jerry", "Tom & Jerry"),
        ("<p>Tom &amp; Jerry</p>", "Tom & Jerry"),
        # Prose that never had markup is returned untouched.
        ("A plain description.", "A plain description."),
        # Malformed markup degrades to text rather than losing the description.
        ("Unclosed <p>tag", "Unclosed\n\ntag"),
        # Nothing renders this as HTML, but script content is not prose either.
        ("<script>alert(1)</script>Real text", "Real text"),
        ("", ""),
        ("<p></p>", ""),
    ],
)
def test_strip_html_reduces_provider_markup_to_prose(raw: str, expected: str) -> None:
    assert strip_html(raw) == expected


def test_strip_html_collapses_whitespace_without_joining_words() -> None:
    """`<b>` inside a sentence is a word boundary, not a paragraph break."""
    assert strip_html("<p>one <b>two</b> three</p>") == "one two three"


# --------------------------------------------------------------------------------------
# Creator sort names (Sprint 023)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # The three the roadmap names. A last-space split gets the first two wrong
        # and the third right, which is exactly why the heuristic is not that.
        ("Gabriel García Márquez", "García Márquez, Gabriel"),
        ("Adolfo Bioy Casares", "Bioy Casares, Adolfo"),
        ("Juan Rulfo", "Rulfo, Juan"),
        # An initial belongs to the given name, not to the surname.
        ("Ursula K. Le Guin", "Le Guin, Ursula K."),
        ("J. R. R. Tolkien", "Tolkien, J. R. R."),
        # Already inverted: Calibre and Goodreads both emit this form, and
        # re-inverting it would produce "Gabriel, García Márquez".
        ("García Márquez, Gabriel", "García Márquez, Gabriel"),
        # A mononym has no surname to move.
        ("Homero", "Homero"),
        ("", ""),
        ("   ", ""),
        # Whitespace is collapsed; the display form is what the owner reads.
        ("  Juan   Rulfo  ", "Rulfo, Juan"),
    ],
)
def test_creator_sort_name_moves_the_surname_first(name: str, expected: str) -> None:
    assert creator_sort_name(name) == expected


def test_creator_sort_name_keeps_every_token_after_the_first_as_the_surname() -> None:
    """The documented failure, asserted so it is a decision rather than a surprise.

    Spanish double surnames are the library this serves, so the first token is
    treated as the only given name. An English name carrying two given names sorts
    wrong until the owner corrects it by hand.
    """
    assert creator_sort_name("John Ronald Reuel Tolkien") == "Ronald Reuel Tolkien, John"


# --------------------------------------------------------------------------------------
# The domain registry: what an *entry* on this domain can be (seam 5b, DEC-057/DEC-059)
# --------------------------------------------------------------------------------------


def test_every_domain_declares_a_usable_status_vocabulary() -> None:
    """Written against the registry rather than against books or albums by name.

    A third domain added after this sprint inherits the same rules without anyone
    remembering to extend a list here, which is the whole point of seam 5b.
    """
    for domain in DOMAINS.values():
        values = [status.value for status in domain.statuses]
        assert values, f"{domain.item_type} declares no statuses"
        assert len(values) == len(set(values)), f"{domain.item_type} repeats a status"
        # Imports land in the inbox whatever the domain, and the default library view
        # hides it — so it exists everywhere and is never offered as a choice.
        assert "unsorted" in values
        assert not next(row for row in domain.statuses if row.value == "unsorted").choosable
        assert domain.default_status in values
        assert all(status.label for status in domain.statuses)
        keys = [status.hotkey for status in domain.statuses if status.hotkey]
        assert len(keys) == len(set(keys)), f"{domain.item_type} binds one key twice"
        assert all(status.hotkey for status in domain.statuses if status.choosable)


def test_every_domain_declares_a_format_vocabulary() -> None:
    for domain in DOMAINS.values():
        values = [row.value for row in domain.formats]
        assert values, f"{domain.item_type} declares no formats"
        assert len(values) == len(set(values))
        assert all(row.label for row in domain.formats)


def test_the_two_domains_disagree_about_what_a_status_means() -> None:
    """DEC-057: an album's status is possession, a book's is consumption."""
    assert [row.value for row in ALBUM.statuses] == ["unsorted", "wishlist", "pending", "owned"]
    assert ALBUM.default_status == "owned"
    assert BOOK.default_status == "read"
    assert "read" not in {row.value for row in ALBUM.statuses}
    # ...and they still share the one status that means the same thing in both.
    assert "wishlist" in {row.value for row in BOOK.statuses}


def test_a_status_is_validated_against_the_domain_that_owns_the_item() -> None:
    assert validate_status(BOOK, "read") == "read"
    assert validate_status(ALBUM, "owned") == "owned"
    with pytest.raises(InvalidStatus) as refused:
        validate_status(ALBUM, "read")
    # The message names the domain: "that is not a status" is unactionable when the
    # value is perfectly valid one row further down the library.
    assert "Album" in str(refused.value)
    with pytest.raises(InvalidStatus):
        validate_status(BOOK, "owned")


def test_a_format_is_validated_against_the_domain_that_owns_the_item() -> None:
    assert validate_formats(ALBUM, ["vinyl", "digital"]) == ["vinyl", "digital"]
    with pytest.raises(InvalidFormat) as refused:
        validate_formats(ALBUM, ["borrowed"])
    assert "Album" in str(refused.value)
    with pytest.raises(InvalidFormat):
        validate_formats(BOOK, ["vinyl"])


def test_an_album_has_no_reread_count_and_no_dates() -> None:
    """DEC-057: those date a passage through a book an album does not have."""
    assert BOOK.entry_fields == frozenset({"date_started", "date_finished", "reread_count"})
    assert ALBUM.entry_fields == frozenset()
    assert validate_entry_fields(BOOK, {"reread_count": 2}) == {"reread_count": 2}
    with pytest.raises(InvalidEntryField) as refused:
        validate_entry_fields(ALBUM, {"reread_count": 2})
    assert "Album" in str(refused.value)
    # Fields every domain has are never refused by this check.
    assert validate_entry_fields(ALBUM, {"score": 8, "notes": "x"}) == {"score": 8, "notes": "x"}


def test_entry_values_are_allowlisted_by_the_domain_that_owns_them() -> None:
    from book_tracker.domains.anime import DOMAIN as ANIME

    values = {"notes": "kept", "date_finished": "2026-08-27", "progress": 20}
    assert validate_entry_values(ANIME, values) == values

    with pytest.raises(InvalidEntryField, match="Album"):
        validate_entry_values(ALBUM, {"date_finished": "2026-08-27"})
    with pytest.raises(InvalidProgress, match="Book"):
        validate_entry_values(BOOK, {"progress": 1})

    # Clearing is recovery, even if a domain no longer declares the value.
    assert validate_entry_values(BOOK, {"progress": None}) == {"progress": None}

    with pytest.raises(InvalidEntryField, match="Book"):
        validate_entry_values(BOOK, {"future_domain_value": "silent without an allowlist"})


def test_the_status_union_is_ordered_and_covers_every_domain() -> None:
    assert set(ALL_STATUSES) == {
        value for domain in DOMAINS.values() for value in (row.value for row in domain.statuses)
    }
    assert ALL_STATUSES[0] == "unsorted"
    assert len(ALL_STATUSES) == len(set(ALL_STATUSES))
    assert set(ALL_FORMATS) == {row.value for domain in DOMAINS.values() for row in domain.formats}


def test_the_published_enums_agree_with_the_registry() -> None:
    """The drift assertion for the API surface.

    `EntryStatus` and `EntryFormat` are what OpenAPI publishes and therefore what a
    client may send. They are spelled out for the type checker, so this is the thing
    that fails when a domain declares a value nobody added to them.
    """
    assert {member.value for member in EntryStatus} == set(ALL_STATUSES)
    assert {member.value for member in EntryFormat} == set(ALL_FORMATS)
    # The domain names themselves are a published union too, since Sprint 027 made
    # `type` a query parameter. Same reason, same failure mode: a third domain that
    # nobody adds here is a domain the library cannot be filtered to.
    assert {member.value for member in ItemTypeName} == set(DOMAINS)


def test_only_a_domain_that_declares_progress_may_record_it() -> None:
    """The fourth validator, beside status, formats and metadata (DEC-077).

    A book has no partial-progress concept: a page count is not something the entry
    records. So the value is refused on write rather than merely hidden, for the same
    reason a reread count on a record is (DEC-057).
    """
    from book_tracker.domain.spec import InvalidProgress, validate_progress
    from book_tracker.domains.anime import DOMAIN as ANIME

    assert validate_progress(ANIME, 20) == 20
    # Zero is a recorded value, not an absence: the owner's own library holds a row
    # sitting at 0 of 1 episodes, `Plan to Watch`.
    assert validate_progress(ANIME, 0) == 0
    # Not recorded at all, which is a different fact from zero.
    assert validate_progress(ANIME, None) is None
    # Clearing it is always allowed, even on a domain that has no progress.
    assert validate_progress(BOOK, None) is None

    for domain in (BOOK, ALBUM):
        with pytest.raises(InvalidProgress) as refused:
            validate_progress(domain, 3)
        assert domain.label in str(refused.value)


def test_a_negative_progress_is_refused_but_a_large_one_is_not() -> None:
    """The total is display only and never a bound (owner decision, 2026-08-27).

    AniList returns `episodes: null` for an airing show and a weekly series' cached
    total is stale by definition, so refusing a number above it would reject the
    reader's own data because our cache is behind.
    """
    from book_tracker.domain.spec import InvalidProgress, validate_progress
    from book_tracker.domains.anime import DOMAIN as ANIME

    with pytest.raises(InvalidProgress):
        validate_progress(ANIME, -1)
    assert validate_progress(ANIME, 100_000) == 100_000
