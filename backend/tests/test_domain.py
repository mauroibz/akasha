import pytest

from book_tracker.domain.identity import InvalidIdentifier, normalize_identifier
from book_tracker.domain.matching import MatchKind, decide_match
from book_tracker.domain.merge import fill_empty
from book_tracker.domain.normalization import creator_sort_name, normalize_text, strip_html


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
        {"title": "Existing", "subtitle": "", "metadata": {"authors": ["A"]}},
        {"title": "Incoming", "subtitle": "Filled", "metadata": {"authors": ["B"]}},
    ) == {"title": "Existing", "subtitle": "Filled", "metadata": {"authors": ["A"]}}


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
